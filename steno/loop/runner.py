"""The Steno run loop runner (steno-design.md section 2, "Stages" and "Lifecycle").

``run()`` drives one RunSpec through preflight, provisioning, the declared
stages in order, artifact sync and confirmed teardown, persisting the
lifecycle (see state.py) after every transition so a crash can resume without
double-provisioning or leaking a rented resource.

Design commitments enforced here:
  - span, when present, gates everything downstream: a span failure cancels
    the remaining stages without running them.
  - spend and wall-clock limits are checked independently of stage activity,
    including while the resource is unreachable.
  - "completed" tracks only resource cleanup (sync_verified AND
    destroy_confirmed); it is never treated as a success signal by itself.
    work_status/work_reason separately record whether the stages themselves
    succeeded, and are recomputed from persisted stage state on every call so
    a resume never loses a prior failure (see RunOutcome).
  - on resume, the resource is reconciled with backend.inspect() before any
    action; provisioning always goes through the same idempotency key, and a
    crash on either side of the provider call never double-provisions.
  - once this process owns the resource, ordinary exceptions from execute,
    transfer, cost or ledger calls are caught, recorded as a typed failure,
    and still run through cleanup: only a genuine process kill requires a
    restart to recover (via the idempotent provisioning path above).
  - a run directory has exactly one active owner at a time (a pid lock), and
    a resume is rejected if the spec's pair/inputs/stages/gates changed since
    the run directory was created.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from . import ledger as ledger_module
from .backend import ExecuteResult, TransferResult
from .spec import KNOWN_GATE_KEYS, RunSpec
from .state import (
    RESOURCE_ACTIVE,
    RESOURCE_DESTROY_CONFIRMED,
    RESOURCE_DESTROY_REQUESTED,
    RESOURCE_DESTROY_UNKNOWN,
    RESOURCE_PROVISIONING,
    RESOURCE_READY,
    RESOURCE_REQUESTED,
    RESOURCE_SYNCING,
    RESOURCE_SYNC_VERIFIED,
    STAGE_CANCELLED,
    STAGE_FAILED,
    STAGE_PENDING,
    STAGE_RUNNING,
    STAGE_SUCCEEDED,
    RunState,
    acquire_run_lock,
    release_run_lock,
)

DEFAULT_POLL_INTERVAL_SECONDS = 0.01
DEFAULT_MAX_UNREACHABLE_POLLS = 200
COMPUTE_RESOURCE_ID_KEY = "compute"

WORK_SUCCEEDED = "succeeded"
WORK_FAILED = "failed"
WORK_PREFLIGHT_FAILED = "preflight_failed"


class PreflightError(RuntimeError):
    """Raised (and caught internally) when a preflight check fails."""


class IncompatibleResumeError(RuntimeError):
    """Raised when a run directory's persisted identity does not match the
    spec being resumed with (W-6: reject an incompatible resume)."""


@dataclass
class RunOutcome:
    """A concise summary of a run() call, for the CLI and for tests.

    ``completed`` reflects resource cleanup ONLY (sync_verified AND
    destroy_confirmed): a caller must also check ``work_status`` to know
    whether the run actually did what it was asked. ``success`` combines
    both, and is the one flag a caller should treat as "this run succeeded."
    """

    state: RunState
    completed: bool
    sync_verified: bool
    destroy_confirmed: bool
    work_status: str
    work_reason: str | None
    abort_reason: str | None

    @property
    def success(self) -> bool:
        return self.completed and self.work_status == WORK_SUCCEEDED


def _hash_manifest(manifest: dict[str, str]) -> str:
    canonical = json.dumps(manifest, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_pair_path(spec: RunSpec) -> str | None:
    """Returns an existing path for spec.pair, checked as given and relative
    to the spec file's directory, or None if neither exists."""
    if os.path.exists(spec.pair):
        return spec.pair
    if spec.source_path:
        candidate = os.path.join(os.path.dirname(spec.source_path), spec.pair)
        if os.path.exists(candidate):
            return candidate
    return None


class _CreditLookupFailed:
    """Sentinel distinguishing "the backend has no credit_lookup capability"
    (None; the spec's asserted compute.available_credit is used instead,
    unchanged from before) from "the backend HAS the capability but the live
    lookup failed or returned garbage" (this sentinel; Codex review X-14:
    falling back to the spec's -- possibly stale -- asserted value in that
    case would defeat the point of live-checking, so preflight must fail
    closed instead)."""


CREDIT_LOOKUP_FAILED = _CreditLookupFailed()


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _backend_available_credit(backend: Any) -> float | _CreditLookupFailed | None:
    """Build order step 8: the credit check calls the backend's own credit
    lookup when it offers one (``capabilities.get("credit_lookup")`` and a
    ``get_available_credit`` method), rather than only trusting whatever the
    spec's ``compute.available_credit`` says.

    Returns ``None`` when the backend does not advertise the capability at
    all (the caller should use the spec's asserted value, as before).
    Returns ``CREDIT_LOOKUP_FAILED`` when the backend DOES advertise the
    capability but the lookup raised, returned something not coercible to
    ``float``, or returned a non-finite value (NaN/inf, which would
    otherwise silently pass a naive ``<`` comparison against the budget
    floor) -- the caller must treat this as a hard preflight failure, never
    fall back to a compute-time-authored value the live check exists to
    supersede.
    """
    capabilities = getattr(backend, "capabilities", {}) or {}
    if not capabilities.get("credit_lookup"):
        return None
    getter = getattr(backend, "get_available_credit", None)
    if getter is None:
        return None
    try:
        credit = float(getter())
    except Exception:
        return CREDIT_LOOKUP_FAILED
    if not _is_finite_number(credit):
        return CREDIT_LOOKUP_FAILED
    return credit


def _run_preflight(
    state: RunState,
    spec: RunSpec,
    backend: Any,
    *,
    stage_executors: dict[str, Callable[..., ExecuteResult]],
    effective_stages: list[str],
    dry_run: bool,
) -> None:
    """Runs the preflight checks the design names: spec valid, budget and
    credit floor, required inputs present, one allocated port recorded.

    Outside dry_run, this also fails closed on: missing/insufficient credit,
    a pair manifest that does not exist on disk, and a declared stage with no
    registered executor. dry_run (the CLI's dry-run command, and tests that
    exercise lifecycle mechanics against FakeBackend) exempts exactly these
    three infra-dependent checks; spec validity and required inputs are
    always enforced.
    """
    spec.validate()  # raises SpecValidationError, allowed to propagate as-is

    if not dry_run:
        backend_credit = _backend_available_credit(backend)
        if backend_credit is CREDIT_LOOKUP_FAILED:
            # X-14: the backend advertises a live credit lookup; a spec's
            # asserted compute.available_credit is not an acceptable
            # substitute for it when it fails, since that value could be
            # stale (or simply wrong) and the whole point of a live lookup
            # is to not trust it. Fail closed rather than authorizing
            # provisioning on unverifiable credit.
            raise PreflightError(
                "the backend advertises a live credit lookup (capabilities['credit_lookup']) but it "
                "failed or returned a non-finite value; refusing to fall back to compute.available_credit "
                "for a provisioning decision the live check exists to supersede"
            )
        available_credit = backend_credit if backend_credit is not None else spec.compute.get("available_credit")
        if available_credit is None or not _is_finite_number(available_credit) or available_credit < spec.budget["min_credit"]:
            raise PreflightError(
                f"available credit ({available_credit!r}) is below the budget floor "
                f"{spec.budget['min_credit']} (or not a finite number); set compute.available_credit or pass dry_run=True"
            )

        if _resolve_pair_path(spec) is None:
            raise PreflightError(
                f"pair manifest not found: {spec.pair!r} (checked as given and relative to the spec file)"
            )

        missing_executors = [
            stage for stage in effective_stages if stage != "preflight" and stage not in stage_executors
        ]
        if missing_executors:
            raise PreflightError(
                f"no stage executor registered for {missing_executors}; pass dry_run=True for a no-op dry run"
            )

    if state.allocated_port is None:
        state.allocated_port = int(spec.compute.get("port_base", 8000))
        state.save()


def _budget_exceeded(spec: RunSpec, backend: Any, resource_id: str | None, clock: Callable[[], float], start_time: float) -> bool:
    elapsed_hours = max(0.0, (clock() - start_time) / 3600.0)
    if elapsed_hours >= spec.budget["max_hours"]:
        return True
    if resource_id is not None:
        try:
            spend = backend.cost(resource_id)
        except Exception:
            # W-2: a cost-query failure must not be silently ignored while we
            # keep spending; fail safe and let the caller route to cleanup.
            return True
        spendable = spec.budget["max_usd"] - spec.budget["cleanup_reserve_usd"]
        if spend >= spendable:
            return True
    return False


def _safe_cost(backend: Any, resource_id: str) -> float:
    try:
        return backend.cost(resource_id)
    except Exception:
        return 0.0


def _safe_ledger_event(run_dir: str, event: str, *, resource_id: str, spend_usd_estimate: float, detail: str) -> None:
    try:
        ledger_module.append_event(run_dir, event, resource_id=resource_id, spend_usd_estimate=spend_usd_estimate, detail=detail)
    except Exception:
        pass  # the ledger is best-effort bookkeeping; it must never block cleanup


def _ensure_provisioned(state: RunState, backend: Any, spec: RunSpec, idempotency_key: str) -> str:
    """Provision the single compute resource this wave uses, reconciling with
    the backend on resume and never double-provisioning.

    W-1: a crash can land between calling backend.provision() and persisting
    the returned resource id, leaving the resource state at `provisioning`
    with no id on file. That is recovered here by treating `provisioning`
    with no id the same as a fresh provision attempt: calling provision()
    again is safe because the backend is keyed by idempotency_key, so a
    stranded live resource is recovered rather than orphaned, and no second
    resource is ever created.
    """
    if COMPUTE_RESOURCE_ID_KEY not in state.resources:
        state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_REQUESTED)

    meta = state.resource_meta.get(COMPUTE_RESOURCE_ID_KEY, {})
    resource_id = meta.get("backend_resource_id")
    status = state.resource_status(COMPUTE_RESOURCE_ID_KEY)

    if resource_id is None:
        if status not in (RESOURCE_REQUESTED, RESOURCE_PROVISIONING):
            raise RuntimeError(f"inconsistent state: resource has no id but status is {status!r}")
        if status == RESOURCE_REQUESTED:
            state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_PROVISIONING)
        result = backend.provision(spec.compute, idempotency_key)
        _safe_ledger_event(
            state.run_dir, "provision", resource_id=result.resource_id,
            spend_usd_estimate=_safe_cost(backend, result.resource_id), detail=f"host={result.host} port={result.port}",
        )
        state.transition_resource(
            COMPUTE_RESOURCE_ID_KEY, RESOURCE_READY,
            backend_resource_id=result.resource_id, host=result.host, port=result.port,
        )
        return result.resource_id

    # Resuming with a resource_id already on file: reconcile before acting.
    try:
        inspection = backend.inspect(resource_id)
    except Exception:
        # W-2: inspect() can fail like any other provider call once we own a
        # resource. We cannot safely guess whether it still exists, so we do
        # not re-provision (that could double-provision a resource that is
        # actually fine) and we do not claim readiness either: the status is
        # left at `provisioning`, a persisted, reconcilable state that the
        # caller (run()) recognizes and routes straight to a best-effort
        # cleanup attempt instead of running stages against an unconfirmed
        # resource.
        return resource_id
    if status == RESOURCE_PROVISIONING and not inspection.exists:
        result = backend.provision(spec.compute, idempotency_key)
        state.transition_resource(
            COMPUTE_RESOURCE_ID_KEY, RESOURCE_READY,
            backend_resource_id=result.resource_id, host=result.host, port=result.port,
        )
        return result.resource_id
    if status == RESOURCE_PROVISIONING and inspection.exists:
        state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_READY)
    return resource_id


def _await_reachable(
    state: RunState, backend: Any, resource_id: str, spec: RunSpec, clock: Callable[[], float],
    start_time: float, poll_interval_seconds: float, max_polls: int,
) -> str:
    """Waits (polling) until the resource is reachable, aborting the wait as
    soon as the budget or wall-clock cap trips, even though the resource is
    not doing anything useful while unreachable. Returns "ready",
    "budget_exceeded" or "unreachable_timeout"."""
    for _ in range(max_polls):
        if _budget_exceeded(spec, backend, resource_id, clock, start_time):
            return "budget_exceeded"
        try:
            inspection = backend.inspect(resource_id)
        except Exception:
            # W-2: an inspect() failure must not escape; treat this poll as
            # "not reachable yet" so the loop keeps enforcing the wall-clock
            # and budget caps until either they trip or a later poll succeeds.
            inspection = None
        if inspection is not None and inspection.reachable:
            return "ready"
        time.sleep(poll_interval_seconds)
    return "unreachable_timeout"


def _evaluate_gate(stage: str, gate_spec: dict[str, Any], metrics: dict[str, Any]) -> tuple[bool, str | None]:
    """Fail-closed gate evaluation (W-8). Every field of a stage's gate must be
    satisfied by a metric the stage reported, or the gate fails:

    - ``<metric>_min`` / ``<metric>_max`` with a finite number: the reported
      metric must be a finite number at or above / at or below it.
    - any other scalar field, for example ``invariance: all_calls``: the stage
      must report a metric of the same name with exactly that value.
    - a nested object or list (for example a ``teacher_reference`` block): not
      evaluable by this runner, so the gate fails with that reason rather than
      being skipped.

    A missing metric, a non-finite value, or an unmet threshold is a gate
    failure. Nothing in a declared gate is ever silently ignored.
    """
    for key, expected in gate_spec.items():
        if isinstance(expected, (dict, list)):
            return False, f"gate {stage}.{key}: structured gate values are not evaluable by the runner"
        numeric = isinstance(expected, (int, float)) and not isinstance(expected, bool)
        if numeric and (key.endswith("_min") or key.endswith("_max")):
            if not math.isfinite(expected):
                return False, f"gate {stage}.{key}: threshold {expected!r} is not a finite number"
            metric_name = key[:-4]
            value = metrics.get(metric_name)
            if value is None:
                return False, f"gate {stage}.{key}: required metric {metric_name!r} was not reported"
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return False, f"gate {stage}.{key}: metric {metric_name!r}={value!r} is not a finite number"
            if key.endswith("_min") and value < expected:
                return False, f"gate {stage}.{key}: {metric_name}={value} is below the required minimum {expected}"
            if key.endswith("_max") and value > expected:
                return False, f"gate {stage}.{key}: {metric_name}={value} is above the allowed maximum {expected}"
            continue
        if key not in metrics:
            return False, f"gate {stage}.{key}: required metric {key!r} was not reported"
        if metrics[key] != expected:
            return False, f"gate {stage}.{key}: expected {expected!r}, stage reported {metrics[key]!r}"
    return True, None


def _compute_work_outcome(state: RunState, effective_stages: list[str]) -> tuple[str, str | None]:
    """Recomputed fresh from persisted stage state every call (W-5): never
    relies on an abort_reason set only during the call that first saw the
    failure, so a resume never loses it."""
    non_preflight = [s for s in effective_stages if s != "preflight"]
    failures = state.extra.get("stage_failures", {})
    for stage in non_preflight:
        if state.stage_status(stage) == STAGE_FAILED:
            detail = failures.get(stage, {}).get("detail", "no detail recorded")
            return WORK_FAILED, f"stage {stage!r} failed: {detail}"
    if any(state.stage_status(stage) == STAGE_CANCELLED for stage in non_preflight):
        return WORK_FAILED, "one or more stages were cancelled (budget, wall-clock, or unreachable host)"
    if all(state.stage_status(stage) == STAGE_SUCCEEDED for stage in non_preflight):
        return WORK_SUCCEEDED, None
    return WORK_FAILED, "run did not reach a terminal state for all stages"


def run(
    spec: RunSpec,
    backend: Any,
    stage_executors: dict[str, Callable[[str, dict[str, Any]], ExecuteResult]],
    run_dir: str,
    clock: Callable[[], float],
    *,
    run_id: str | None = None,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_unreachable_polls: int = DEFAULT_MAX_UNREACHABLE_POLLS,
    dry_run: bool = False,
) -> RunOutcome:
    """Runs (or resumes) spec against backend, driving the persisted lifecycle
    in run_dir. stage_executors maps stage name -> callable(resource_id, plan)
    -> ExecuteResult; dry_run relaxes preflight's infra checks and allows a
    stage without an executor to run as a no-op success (used by the CLI's
    dry-run, never for a real backend).

    Only one process may hold run_dir at a time (see state.acquire_run_lock);
    this call raises RuntimeError immediately if another live process owns it.
    """
    lock_path = acquire_run_lock(run_dir)
    try:
        return _run_under_lock(
            spec, backend, stage_executors, run_dir, clock,
            run_id=run_id, poll_interval_seconds=poll_interval_seconds,
            max_unreachable_polls=max_unreachable_polls, dry_run=dry_run,
        )
    finally:
        release_run_lock(run_dir)


def _run_under_lock(
    spec: RunSpec,
    backend: Any,
    stage_executors: dict[str, Callable[[str, dict[str, Any]], ExecuteResult]],
    run_dir: str,
    clock: Callable[[], float],
    *,
    run_id: str | None,
    poll_interval_seconds: float,
    max_unreachable_polls: int,
    dry_run: bool,
) -> RunOutcome:
    effective_stages = list(spec.stages)
    if not effective_stages or effective_stages[0] != "preflight":
        effective_stages = ["preflight"] + effective_stages

    identity_digest = spec.identity_digest()

    if RunState.exists(run_dir):
        state = RunState.load(run_dir)
        existing_digest = state.extra.get("identity_digest")
        if existing_digest is not None and existing_digest != identity_digest:
            raise IncompatibleResumeError(
                f"run directory {run_dir!r} holds a run for a different pair/inputs/stages/gates; "
                "refusing to resume with an incompatible spec (W-6)"
            )
    else:
        # W-6: the run id must be unique per run, never derived from the pair
        # name, or two separate runs of the same pair would be handed the
        # same idempotency key and could share (or steal) one another's
        # rented resource.
        run_id = run_id or uuid.uuid4().hex[:12]
        state = RunState.new(run_id, run_dir, effective_stages)
        state.extra["identity_digest"] = identity_digest
        state.save()

    if "start_time" not in state.extra:
        state.extra["start_time"] = clock()
        state.save()
    start_time = state.extra["start_time"]

    if state.idempotency_key is None:
        state.idempotency_key = f"{state.run_id}:compute"
        state.save()

    abort_reason: str | None = None

    # --- preflight -----------------------------------------------------
    preflight_status = state.stage_status("preflight")
    if preflight_status in (STAGE_PENDING, STAGE_RUNNING):
        # W-7: rerun (idempotent) preflight from `running` too, so a crash
        # between saving `running` and finishing validation cannot skip it.
        if preflight_status == STAGE_PENDING:
            state.transition_stage("preflight", STAGE_RUNNING)
        try:
            _run_preflight(state, spec, backend, stage_executors=stage_executors, effective_stages=effective_stages, dry_run=dry_run)
        except Exception as error:
            state.transition_stage("preflight", STAGE_FAILED)
            state.extra["work_outcome"] = {"status": WORK_PREFLIGHT_FAILED, "reason": str(error)}
            state.save()
            return RunOutcome(
                state=state, completed=False, sync_verified=False, destroy_confirmed=False,
                work_status=WORK_PREFLIGHT_FAILED, work_reason=str(error), abort_reason=f"preflight: {error}",
            )
        state.transition_stage("preflight", STAGE_SUCCEEDED)
    elif preflight_status == STAGE_FAILED:
        reason = state.extra.get("work_outcome", {}).get("reason", "preflight previously failed")
        return RunOutcome(
            state=state, completed=False, sync_verified=False, destroy_confirmed=False,
            work_status=WORK_PREFLIGHT_FAILED, work_reason=reason, abort_reason=f"preflight: {reason}",
        )
    # else preflight_status == STAGE_SUCCEEDED: provisioning may proceed.

    # --- provisioning ------------------------------------------------------
    resource_id = _ensure_provisioned(state, backend, spec, state.idempotency_key)
    if state.resource_status(COMPUTE_RESOURCE_ID_KEY) == RESOURCE_READY:
        state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_ACTIVE)

    # From here on, this process owns a resource: ordinary exceptions from
    # backend calls must not escape uncaught (W-2). Only a real process kill
    # (which cannot be caught) requires a restart, recovered above via W-1's
    # idempotent provisioning and W-7/W-9's idempotent preflight/stage retry.
    max_attempts = spec.budget.get("max_attempts_per_stage", 1)
    stage_attempts = state.extra.setdefault("stage_attempts", {})

    # W-2: _ensure_provisioned leaves the resource at `provisioning` (rather
    # than raising) when it could not reconcile with the provider (inspect()
    # failed). That is a persisted, reconcilable state: a later run() call
    # may resolve it, but this call must not run stages against a resource it
    # cannot confirm, so it skips straight to a best-effort cleanup attempt.
    skip_downstream = state.resource_status(COMPUTE_RESOURCE_ID_KEY) == RESOURCE_PROVISIONING
    if skip_downstream:
        abort_reason = "could not reconcile provisioning state with the provider; attempting cleanup"
    remaining_stages = [s for s in effective_stages if s != "preflight"]
    for stage in remaining_stages:
        current_status = state.stage_status(stage)
        if current_status == STAGE_SUCCEEDED:
            continue
        if current_status in (STAGE_FAILED, STAGE_CANCELLED):
            skip_downstream = True
            continue
        if skip_downstream:
            if current_status == STAGE_PENDING:
                state.transition_stage(stage, STAGE_CANCELLED)
            continue
        if _budget_exceeded(spec, backend, resource_id, clock, start_time):
            abort_reason = "budget_or_wallclock_exceeded"
            if current_status == STAGE_PENDING:
                state.transition_stage(stage, STAGE_CANCELLED)
            skip_downstream = True
            continue

        wait_result = _await_reachable(
            state, backend, resource_id, spec, clock, start_time, poll_interval_seconds, max_unreachable_polls
        )
        if wait_result != "ready":
            abort_reason = wait_result
            if current_status == STAGE_PENDING:
                state.transition_stage(stage, STAGE_CANCELLED)
            skip_downstream = True
            continue

        # W-9: enforce max_attempts_per_stage across restarts. attempts_so_far
        # persists in state.extra, so a stage that was left `running` by a
        # real crash and keeps failing cannot retry forever.
        attempts_so_far = stage_attempts.get(stage, 0)
        if attempts_so_far >= max_attempts:
            state.extra.setdefault("stage_failures", {})[stage] = {
                "kind": "task_failure", "detail": f"max_attempts_per_stage ({max_attempts}) exceeded",
            }
            state.save()
            if current_status == STAGE_PENDING:
                state.transition_stage(stage, STAGE_RUNNING)
            state.transition_stage(stage, STAGE_FAILED)
            abort_reason = f"stage {stage} exceeded max_attempts_per_stage ({max_attempts})"
            skip_downstream = True
            continue

        # Persist the attempt BEFORE executing (W-9), so a crash mid-execution
        # still counts against the limit on the next restart.
        stage_attempts[stage] = attempts_so_far + 1
        state.save()

        if current_status == STAGE_PENDING:
            state.transition_stage(stage, STAGE_RUNNING)
        # else current_status == STAGE_RUNNING: resuming a stage a real crash
        # left mid-flight; retry its execution without re-entering RUNNING
        # (pending -> running is the only legal entry).

        stage_plan = {"stage": stage, "executor": stage_executors.get(stage), "inputs": spec.inputs, "outputs": {}}
        try:
            result = backend.execute(resource_id, stage_plan)
        except Exception as error:
            # W-2: an ordinary exception from execute() is caught here rather
            # than escaping run(); it becomes a typed stage failure and the
            # run still proceeds to sync + destroy below.
            result = ExecuteResult(ok=False, kind="infra_failure", detail=f"execute raised: {error}")

        if result.ok and stage in KNOWN_GATE_KEYS and spec.gates.get(stage):
            # W-8: gate evaluation. A stage's own success does not bypass its
            # gate; a missing metric or an unmet threshold turns this into a
            # gate_failure, which stops downstream work exactly like any
            # other stage failure below.
            gate_passed, gate_detail = _evaluate_gate(stage, spec.gates[stage], result.metrics)
            if not gate_passed:
                result = ExecuteResult(ok=False, kind="gate_failure", detail=gate_detail, output_manifest=result.output_manifest)

        if result.ok:
            manifest_hash = _hash_manifest(result.output_manifest)
            state.extra.setdefault("stage_manifests", {})[stage] = result.output_manifest
            state.extra.setdefault("stage_manifest_hashes", {})[stage] = manifest_hash
            state.transition_stage(stage, STAGE_SUCCEEDED)
        else:
            state.extra.setdefault("stage_failures", {})[stage] = {"kind": result.kind, "detail": result.detail}
            state.save()
            state.transition_stage(stage, STAGE_FAILED)
            abort_reason = f"stage {stage} failed ({result.kind}): {result.detail}"
            skip_downstream = True

    # --- sync artifacts ------------------------------------------------
    total_manifest: dict[str, str] = {}
    for stage_manifest in state.extra.get("stage_manifests", {}).values():
        total_manifest.update(stage_manifest)

    resource_status_before_sync = state.resource_status(COMPUTE_RESOURCE_ID_KEY)
    if resource_status_before_sync not in (RESOURCE_ACTIVE, RESOURCE_SYNCING):
        # A prior call already reached sync_verified (or moved on to destroy);
        # re-attempting transfer() here would re-query a resource that may
        # already be destroyed and could wrongly flip a verified sync to
        # failed. Reuse the persisted result instead (see W-3's resume test).
        sync_verified = bool(state.extra.get("sync_verified", False))
    else:
        if resource_status_before_sync == RESOURCE_ACTIVE:
            state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_SYNCING)
        try:
            transfer_result = backend.transfer(resource_id, total_manifest)
        except Exception as error:
            transfer_result = TransferResult(ok=False, detail=f"transfer raised: {error}")
        sync_verified = bool(transfer_result.ok and transfer_result.manifest == total_manifest)
        _safe_ledger_event(
            state.run_dir, "sync", resource_id=resource_id, spend_usd_estimate=_safe_cost(backend, resource_id),
            detail="verified" if sync_verified else f"not verified: {transfer_result.detail}",
        )
        if sync_verified:
            if state.resource_status(COMPUTE_RESOURCE_ID_KEY) == RESOURCE_SYNCING:
                state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_SYNC_VERIFIED)
        else:
            if state.resource_status(COMPUTE_RESOURCE_ID_KEY) == RESOURCE_SYNCING:
                state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_ACTIVE)
            if abort_reason is None:
                abort_reason = f"sync not verified: {transfer_result.detail}"
            # W-4: honor artifacts.emergency_policy explicitly and persist the
            # loss; validate() already rejects any policy this wave does not
            # implement, so terminate_and_record_loss is the only value here.
            policy = spec.artifacts.get("emergency_policy")
            if policy == "terminate_and_record_loss" and total_manifest:
                state.extra["artifact_loss"] = {
                    "manifest": total_manifest, "reason": transfer_result.detail, "policy": policy,
                }
                _safe_ledger_event(
                    state.run_dir, "artifact_loss", resource_id=resource_id, spend_usd_estimate=_safe_cost(backend, resource_id),
                    detail=f"policy={policy}: {transfer_result.detail}",
                )
    state.extra["sync_verified"] = sync_verified
    state.save()

    # --- destroy (always attempted, even on abort, so nothing leaks) -------
    # W-3: destroy_unknown is retried on every subsequent call, inspecting the
    # provider for evidence before declaring destroy_confirmed.
    destroy_confirmed = False
    current_resource_status = state.resource_status(COMPUTE_RESOURCE_ID_KEY)
    if current_resource_status == RESOURCE_DESTROY_CONFIRMED:
        destroy_confirmed = True
    else:
        if current_resource_status != RESOURCE_DESTROY_REQUESTED:
            # Legal from active/syncing/sync_verified/ready and, since W-3,
            # from destroy_unknown too: unknown must stay retryable.
            state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_DESTROY_REQUESTED)

        try:
            inspection = backend.inspect(resource_id)
        except Exception:
            inspection = None
        if inspection is not None and not inspection.exists:
            # Provider evidence the resource is already gone.
            state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_DESTROY_CONFIRMED)
            destroy_confirmed = True
        else:
            try:
                backend.destroy(resource_id)
            except Exception:
                pass  # the destroy request itself failing is handled by confirm_destroyed below
            _safe_ledger_event(
                state.run_dir, "destroy", resource_id=resource_id, spend_usd_estimate=_safe_cost(backend, resource_id),
                detail="destroy requested",
            )
            try:
                confirmation = backend.confirm_destroyed(resource_id)
            except Exception:
                confirmation = None
            if confirmation is True:
                state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_DESTROY_CONFIRMED)
                destroy_confirmed = True
            elif confirmation is False:
                if abort_reason is None:
                    abort_reason = "destroy not yet confirmed by backend"
            else:
                state.transition_resource(COMPUTE_RESOURCE_ID_KEY, RESOURCE_DESTROY_UNKNOWN)
                if abort_reason is None:
                    abort_reason = "destroy confirmation errored (destroy_unknown); will retry on the next run() call"

    state.extra["destroy_confirmed"] = destroy_confirmed
    state.save()

    completed = sync_verified and destroy_confirmed

    # W-5: work_status/work_reason are recomputed from persisted stage state
    # every call, so a resume never loses a failure recorded in a prior call.
    work_status, work_reason = _compute_work_outcome(state, effective_stages)
    state.extra["work_outcome"] = {"status": work_status, "reason": work_reason}
    state.save()
    if abort_reason is None and work_status != WORK_SUCCEEDED:
        abort_reason = work_reason

    if completed:
        state.mark_completed()

    return RunOutcome(
        state=state, completed=completed, sync_verified=sync_verified, destroy_confirmed=destroy_confirmed,
        work_status=work_status, work_reason=work_reason, abort_reason=abort_reason,
    )
