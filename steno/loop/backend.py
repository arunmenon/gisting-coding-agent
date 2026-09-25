"""The compute backend contract (steno-design.md section 2, "Compute backends").

    quote(request); provision(compute, idempotency_key); inspect(id); execute(id, stage_plan)
    transfer(id, manifest); cost(id); destroy(id); confirm_destroyed(id)

Wave 1 shipped only ``FakeBackend`` and a documented ``VastBackend`` stub.
Wave 2 (steno-design.md section 3, build order step 6) formalises this module
into the provider-neutral contract every backend must satisfy, moves each
concrete backend into its own module under ``steno/loop/backends/`` (so no
provider import ever needs to happen outside that provider's own file), and
implements ``LocalBackend`` and ``VastBackend`` for real.

This module re-exports ``FakeBackend`` and ``VastBackend`` from their new
homes so wave 1 imports (``from steno.loop.backend import FakeBackend``)
keep working unchanged. New code should import backends from
``steno.loop.backends`` (or via the registry in ``steno.loop.backends``)
instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .compute import ComputeOffer, ComputeRequest, ResourceHandle

# Backward-compatible alias: wave 1 called the provisioning result
# ProvisionResult; wave 2's provider-neutral name is ResourceHandle.
ProvisionResult = ResourceHandle

from dataclasses import dataclass, field


class BackendError(RuntimeError):
    """The one exception type a backend should raise for a failed provider
    call it cannot otherwise turn into a typed result (Codex review X-7).

    A backend MUST NOT let a raw SDK exception (or its __cause__/__context__
    chain, or a message built from that exception's own text) escape: an SDK
    exception can carry the API credential (for example in
    ``error.response.request.headers["Authorization"]``, confirmed
    empirically for vast.ai's HTTPError). Every backend call site that
    touches a provider SDK should catch broadly and raise
    ``BackendError(message) from None`` with a message built only from
    caller-known facts (which call, which resource id, the exception's
    *type* name) -- never from ``str(error)`` or the exception object itself.
    """


class AmbiguousProvisionError(BackendError):
    """Raised by provision() when a create call's outcome could not be
    confirmed (the request may or may not have succeeded server-side) and
    reconciliation could not resolve it within a bounded window (Codex
    review X-1). A caller must NOT respond to this by provisioning again
    with a fresh call; the safe response is to stop and let a human (or a
    later, deliberate resume) reconcile against the provider first, since a
    blind retry risks renting a second resource for work the first one may
    already be doing."""


def stage_plan_has_work(stage_plan: dict[str, Any]) -> bool:
    """The stage-plan contract every backend and the runner share (Codex
    review X-6): a plan is only legitimate if it carries an ``executor``
    callable (run in-process; how FakeBackend and the CLI's dry-run work) or
    a ``command`` (an argv list, run out-of-process; how LocalBackend and
    VastBackend work). A plan with neither is not a valid no-op: a backend
    that is not explicitly a test double must reject it (``ok=False,
    kind="infra_failure"``) rather than silently reporting success for work
    that never ran, which is what let a stage report success without a
    registered executor in the wave 2 review's offline probes.
    """
    return callable(stage_plan.get("executor")) or bool(stage_plan.get("command"))


@dataclass
class InspectResult:
    """What the provider currently reports about a resource (its ground truth)."""

    resource_id: str
    exists: bool
    reachable: bool
    status_text: str = ""


@dataclass
class ExecuteResult:
    """A typed stage outcome. exactly one of ok/infra_failure/task_failure/gate_failure."""

    ok: bool
    kind: str  # "ok" | "infra_failure" | "task_failure" | "gate_failure"
    detail: str = ""
    output_manifest: dict[str, str] = field(default_factory=dict)  # path -> content hash
    metrics: dict[str, float] = field(default_factory=dict)  # metric name -> value, checked against spec.gates


@dataclass
class TransferResult:
    ok: bool
    manifest: dict[str, str] = field(default_factory=dict)  # path -> content hash actually synced
    detail: str = ""


class ComputeBackend(ABC):
    """The provider-agnostic contract the runner drives every backend through.

    Every method below documents three things a backend author must get
    right: the semantics the runner relies on, what idempotency means for
    that call (if any), and what an exception vs. a returned value means.
    Unless a method's docstring says otherwise, an ordinary exception must
    never be raised for an expected outcome (like "not ready yet"); it should
    be reserved for a call that could not be completed at all (a network
    error, a malformed provider response). The runner (see runner.py's W-2)
    catches exceptions from every one of these calls once it owns a resource
    and turns them into typed failures, so a backend that raises instead of
    returning a typed "not ok" result does not crash the run, but it does
    lose the specific reason a typed result would have carried.

    ``name`` identifies the backend in ledger rows, logs and the registry.
    ``capabilities`` is a small dict of feature flags the runner/CLI can
    check before relying on optional behavior, for example
    ``{"credit_lookup": True}`` when the backend can report available
    provider credit for preflight (see runner.py's credit check).
    """

    name: str = "unnamed"
    capabilities: dict[str, Any] = {}

    @abstractmethod
    def quote(self, request: ComputeRequest) -> list[ComputeOffer]:
        """Return candidate offers matching ``request``, cheapest first.

        Read-only: must not reserve, rent or otherwise commit anything.
        Not idempotent in any meaningful sense (prices move); callers must
        not assume a later provision() will get the same offer or price.
        An empty list means no matching offer was found, not an error; raise
        only when the lookup itself could not be performed.
        """

    @abstractmethod
    def provision(self, compute: dict[str, Any], idempotency_key: str) -> ResourceHandle:
        """Provision one resource for this run and return a handle to it.

        Must be idempotent on ``idempotency_key``: calling this twice with
        the same key for a resource that already exists (by this backend's
        own bookkeeping, not a guess) returns the existing resource rather
        than creating a second one, so a crash-and-retry can never double
        rent. ``compute`` is the spec's ``compute`` mapping; a backend reads
        ``compute.get("request")`` (a ComputeRequest-shaped dict) and
        ``compute.get("backend_options")`` (its own opaque extras), falling
        back to treating the whole mapping as backend_options when neither
        key is present (wave 1 compatibility). Raise only when provisioning
        itself could not be attempted or confirmed; a provider-side rejection
        (out of stock, insufficient credit) should raise a clear exception
        since the runner cannot proceed without a resource either way.
        """

    @abstractmethod
    def inspect(self, resource_id: str) -> InspectResult:
        """Return the provider's current ground truth for ``resource_id``.

        Never idempotent in the sense of caching; must reflect live state (or
        the backend's best local reconciliation of it) on every call. An
        unknown id returns ``exists=False``, never an exception, so resume
        logic can treat "gone" and "never existed" alike. Reserve exceptions
        for a lookup that could not be performed at all (network/API error);
        the runner treats such an exception as "cannot confirm right now",
        never as confirmation of either existence or absence.
        """

    @abstractmethod
    def execute(self, resource_id: str, stage_plan: dict[str, Any]) -> ExecuteResult:
        """Run one stage's work against the resource and report a typed result.

        Must honor a deadline internally (a stage or launch timeout) rather
        than blocking forever; a timeout is reported as
        ``ExecuteResult(ok=False, kind="infra_failure", ...)``, not an
        exception, since it is an expected outcome the runner already knows
        how to handle. Not idempotent by contract: a retried stage may repeat
        side effects; stage-level retry policy (``max_attempts_per_stage``)
        lives in the runner, not here.
        """

    @abstractmethod
    def transfer(self, resource_id: str, manifest: dict[str, Any]) -> TransferResult:
        """Sync artifacts named in ``manifest`` (path -> expected content hash)
        off the resource and verify them against that hash.

        ``TransferResult.ok`` must be True only when every path in the
        manifest was actually retrieved and its hash matches; a partial or
        mismatched transfer is ``ok=False`` with the mismatching paths named
        in ``detail``, never silently accepted. Safe to retry (re-running a
        verified transfer must not corrupt or lose the already-verified
        copy).
        """

    @abstractmethod
    def cost(self, resource_id: str) -> float:
        """Return cumulative spend in USD for this resource so far.

        Must never raise for an ordinary "still running" resource; the
        runner treats any exception here as "assume budget exceeded" (fail
        safe), so a backend that raises when it simply doesn't know the exact
        figure yet will incorrectly abort a healthy run. Return the best
        available estimate instead (for example ``0.0`` before the first
        billing sample) rather than raising.
        """

    @abstractmethod
    def destroy(self, resource_id: str) -> bool:
        """Request destruction. Returns True only if the destroy *request*
        itself was accepted by the provider, not confirmation of actual
        teardown (see confirm_destroyed). Idempotent: calling destroy() on an
        already-destroyed or already-gone resource must return True rather
        than raising, so a retried destroy is always safe.
        """

    @abstractmethod
    def confirm_destroyed(self, resource_id: str) -> bool | None:
        """True: provider confirms the resource is gone. False: provider says
        it still exists. None: an API error occurred while checking, meaning
        unknown -- an "unknown" result must never be treated as "destroyed"
        by any caller. Idempotent and safe to call repeatedly until it
        returns True.
        """


class VastBackend:
    """Backward-compatible re-export; see steno.loop.backends.vast.VastBackend.

    Kept importable from this module for wave 1 call sites. Importing the
    real implementation requires the ``vastai`` package; if it is not
    installed, importing *this* module still succeeds (no provider import
    happens here), but constructing ``backend.VastBackend`` will raise
    ``ImportError`` at call time instead of at import time.
    """

    def __new__(cls, *args: Any, **kwargs: Any):  # pragma: no cover - thin re-export shim
        from .backends.vast import VastBackend as _RealVastBackend

        return _RealVastBackend(*args, **kwargs)


# Re-export FakeBackend from its new home so `from steno.loop.backend import
# FakeBackend` (wave 1's import path, and this wave's tests) keeps working.
from .backends.fake import FakeBackend  # noqa: E402  (import after class defs to avoid a cycle)

__all__ = [
    "AmbiguousProvisionError",
    "BackendError",
    "ComputeBackend",
    "ExecuteResult",
    "FakeBackend",
    "InspectResult",
    "ProvisionResult",
    "TransferResult",
    "VastBackend",
    "stage_plan_has_work",
]
