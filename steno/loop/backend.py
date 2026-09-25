"""The compute backend protocol (steno-design.md section 2, "Compute backends").

    quote(resources); provision(spec, idempotency_key); inspect(id); execute(id, stage_plan)
    transfer(id, manifest); cost(id); destroy(id); confirm_destroyed(id)

Local and vast.ai are the two backends the design calls for. This wave ships
only ``FakeBackend``, a test double used to exercise the runner and lifecycle
without any network or GPU access, and a documented ``VastBackend`` stub that
raises NotImplementedError so the interface is visible before wave 2 implements
it against experiments/vast/*.sh.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class Quote:
    """The estimated hourly price and specs for a requested resource."""

    hourly_usd: float
    gpu_name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvisionResult:
    resource_id: str
    host: str
    port: int


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


class ComputeBackend(Protocol):
    """The provider-agnostic contract the runner drives every backend through."""

    def quote(self, resources: dict[str, Any]) -> Quote: ...

    def provision(self, spec: dict[str, Any], idempotency_key: str) -> ProvisionResult:
        """Must be idempotent: calling twice with the same idempotency_key for a
        resource that already exists returns the existing resource rather than
        creating a second one."""
        ...

    def inspect(self, resource_id: str) -> InspectResult: ...

    def execute(self, resource_id: str, stage_plan: dict[str, Any]) -> ExecuteResult: ...

    def transfer(self, resource_id: str, manifest: dict[str, Any]) -> TransferResult: ...

    def cost(self, resource_id: str) -> float:
        """Cumulative spend in USD for this resource so far."""
        ...

    def destroy(self, resource_id: str) -> bool:
        """Request destruction. Returns True if the request itself succeeded
        (not confirmation of actual teardown; see confirm_destroyed)."""
        ...

    def confirm_destroyed(self, resource_id: str) -> bool | None:
        """True: provider confirms the resource is gone. False: provider says it
        still exists. None: an API error occurred, meaning unknown, never
        treated as destroyed."""
        ...


class VastBackend:
    """Documented stub for the vast.ai backend (build order step 6, wave 2).

    Intended shape, mapping onto experiments/vast/*.sh and experiments/vast/rsh.sh:
      - quote(): vastai search_offers, ranked by dph_total, filtered by the
        spec's compute.gpu_query.
      - provision(): vastai create instance, immediately write the ledger row
        (see experiments/vast/bench_provision.sh's "spend-safety rule"), keyed
        by idempotency_key so a resumed run never double-creates.
      - inspect(): vastai show instance, reconciled against local state.
      - execute(): rsh.sh run against the picked endpoint, honoring the
        launch/stage deadline independent of stage activity.
      - transfer(): rsh.sh get plus a checksum manifest comparison.
      - cost(): dph_total * elapsed hours from vastai show instance.
      - destroy() / confirm_destroyed(): vastai destroy instance, then poll
        show_instances to confirm it no longer appears (see bench_provision.sh
        "abort" cleanup logic for the shape of this check).
    This wave intentionally leaves the implementation undone: no network, no
    vast.ai calls, no GPU, are made by this package in wave 1.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "VastBackend is not implemented in wave 1; see the class docstring "
            "for the intended shape (build order step 6 in steno-design.md)."
        )


class FakeBackend:
    """A test double compute backend. Not for production use.

    Simulates cost accrual over an injected clock, and can be configured to
    fail specific operations so tests can exercise infra failure paths without
    any real provisioning:
      - fail_sync: transfer() returns ok=False once (or every time if 'always').
      - unreachable_hosts: set of resource_ids that inspect()/execute() report
        as unreachable until made reachable again.
      - fail_destroy: destroy() returns False (the destroy *request* fails).
      - fail_destroy_confirmation: confirm_destroyed() raises to simulate an
        API error (translated by callers into destroy_unknown, never destroyed).
    """

    def __init__(self, clock: Callable[[], float], hourly_usd: float = 1.0) -> None:
        self._clock = clock
        self._hourly_usd = hourly_usd
        self._resources: dict[str, dict[str, Any]] = {}
        self._provisioned_keys: dict[str, str] = {}  # idempotency_key -> resource_id
        self.fail_sync = False
        self.unreachable_hosts: set[str] = set()
        self.fail_destroy = False
        self.fail_destroy_confirmation = False
        self._destroyed: set[str] = set()

    def quote(self, resources: dict[str, Any]) -> Quote:
        return Quote(hourly_usd=self._hourly_usd, gpu_name=resources.get("gpu_name", "fake-gpu"))

    def provision(self, spec: dict[str, Any], idempotency_key: str) -> ProvisionResult:
        existing = self._provisioned_keys.get(idempotency_key)
        if existing is not None:
            record = self._resources[existing]
            return ProvisionResult(resource_id=existing, host=record["host"], port=record["port"])
        resource_id = f"fake-{uuid.uuid4().hex[:12]}"
        self._resources[resource_id] = {
            "host": f"{resource_id}.fake",
            "port": 22,
            "created_at": self._clock(),
            "destroyed": False,
            "artifacts": {},  # path -> hash, only what execute() actually "wrote" to this resource
        }
        self._provisioned_keys[idempotency_key] = resource_id
        return ProvisionResult(resource_id=resource_id, host=self._resources[resource_id]["host"], port=22)

    def inspect(self, resource_id: str) -> InspectResult:
        record = self._resources.get(resource_id)
        if record is None:
            return InspectResult(resource_id=resource_id, exists=False, reachable=False, status_text="unknown")
        reachable = resource_id not in self.unreachable_hosts and not record["destroyed"]
        return InspectResult(
            resource_id=resource_id,
            exists=not record["destroyed"],
            reachable=reachable,
            status_text="destroyed" if record["destroyed"] else ("unreachable" if not reachable else "ready"),
        )

    def execute(self, resource_id: str, stage_plan: dict[str, Any]) -> ExecuteResult:
        if resource_id in self.unreachable_hosts:
            return ExecuteResult(ok=False, kind="infra_failure", detail="host unreachable")
        record = self._resources.get(resource_id)
        if record is None or record["destroyed"]:
            return ExecuteResult(ok=False, kind="infra_failure", detail="resource does not exist")
        # A stage executor callable may be attached to the plan by the runner's
        # caller; FakeBackend just runs it (or no-ops) and reports the outcome.
        executor = stage_plan.get("executor")
        if executor is not None:
            result = executor(resource_id, stage_plan)
        else:
            outputs = stage_plan.get("outputs", {})
            result = ExecuteResult(ok=True, kind="ok", output_manifest=dict(outputs))
        if result.ok:
            # Model the output as actually written to this resource, so a
            # later transfer() can only hand back what really exists there
            # (never fabricate verification for a destroyed or empty box).
            record["artifacts"].update(result.output_manifest)
        return result

    def transfer(self, resource_id: str, manifest: dict[str, Any]) -> TransferResult:
        if resource_id in self.unreachable_hosts:
            return TransferResult(ok=False, detail="host unreachable during transfer")
        record = self._resources.get(resource_id)
        if record is None or record["destroyed"]:
            return TransferResult(ok=False, detail="resource no longer exists; cannot transfer from a destroyed box")
        if self.fail_sync:
            return TransferResult(ok=False, detail="simulated sync failure")
        stored = record["artifacts"]
        missing_or_mismatched = {k: v for k, v in manifest.items() if stored.get(k) != v}
        if missing_or_mismatched:
            return TransferResult(
                ok=False,
                detail=f"resource is missing or mismatches {list(missing_or_mismatched)}",
            )
        return TransferResult(ok=True, manifest={k: stored[k] for k in manifest})

    def cost(self, resource_id: str) -> float:
        record = self._resources.get(resource_id)
        if record is None:
            return 0.0
        end = record["created_at"] if record["destroyed"] else self._clock()
        elapsed_hours = max(0.0, (end - record["created_at"]) / 3600.0)
        return round(elapsed_hours * self._hourly_usd, 6)

    def destroy(self, resource_id: str) -> bool:
        if self.fail_destroy:
            return False
        record = self._resources.get(resource_id)
        if record is not None:
            record["destroyed"] = True
        return True

    def confirm_destroyed(self, resource_id: str) -> bool | None:
        if self.fail_destroy_confirmation:
            return None
        record = self._resources.get(resource_id)
        if record is None:
            return True
        return bool(record["destroyed"])
