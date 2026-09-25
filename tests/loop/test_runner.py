import subprocess
import time

import pytest

from steno.loop.backend import ExecuteResult, FakeBackend
from steno.loop.runner import IncompatibleResumeError, run
from steno.loop.spec import spec_from_dict
from steno.loop.state import (
    RESOURCE_ACTIVE,
    RESOURCE_DESTROY_REQUESTED,
    RESOURCE_DESTROY_UNKNOWN,
    RESOURCE_PROVISIONING,
    RESOURCE_READY,
    RESOURCE_REQUESTED,
    STAGE_CANCELLED,
    STAGE_RUNNING,
    STAGE_SUCCEEDED,
    RunState,
    acquire_run_lock,
    release_run_lock,
)


class FakeClock:
    """A deterministic, injectable clock: each call advances by `step` seconds."""

    def __init__(self, start: float = 0.0, step: float = 1.0):
        self.t = start
        self.step = step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


def base_spec_dict(**overrides):
    document = {
        "schema": "steno-run/v1",
        "pair": "pairs/claude-code-qwen38.yaml",
        "inputs": {"captures": "sha256:abc", "tasks": "sha256:def"},
        "stages": ["span", "data", "train"],
        "budget": {"max_usd": 40, "max_hours": 8, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 2},
        "gates": {},
        "compute": {"backend": "fake"},
        "artifacts": {"store": "journeys/j-test/results", "emergency_policy": "terminate_and_record_loss"},
    }
    document.update(overrides)
    return document


def make_spec(**overrides):
    spec = spec_from_dict(base_spec_dict(**overrides))
    spec.validate()
    return spec


def ok_executor(resource_id, stage_plan):
    return ExecuteResult(ok=True, kind="ok", output_manifest={f"{stage_plan['stage']}.json": "hash-" + stage_plan["stage"]})


ALL_STAGE_EXECUTORS = {"span": ok_executor, "data": ok_executor, "train": ok_executor}


# --- happy path and ordinary failure modes (dry_run=True: FakeBackend only, no infra) ---


def test_happy_path_completes(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome = run(spec, backend, stage_executors={}, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    assert outcome.completed is True
    assert outcome.sync_verified is True
    assert outcome.destroy_confirmed is True
    assert outcome.work_status == "succeeded"
    assert outcome.success is True
    for stage in ("span", "data", "train"):
        assert outcome.state.stage_status(stage) == STAGE_SUCCEEDED


def test_sync_failure_never_completes_but_still_destroys_and_records_loss(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    backend.fail_sync = True

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    assert outcome.completed is False
    assert outcome.sync_verified is False
    assert outcome.success is False
    assert outcome.destroy_confirmed is True
    assert "artifact_loss" in outcome.state.extra
    assert outcome.state.extra["artifact_loss"]["policy"] == "terminate_and_record_loss"


def test_destroyed_resource_cannot_fabricate_sync_verification(tmp_path):
    # W-4: FakeBackend must model resource existence/artifacts so that clearing
    # fail_sync after destruction cannot manufacture a false verification.
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    backend.fail_sync = True

    run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    backend.fail_sync = False
    outcome2 = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)
    assert outcome2.sync_verified is False  # the resource is gone; transfer must still fail


def test_destroy_request_failure_stays_visible_never_completes(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    backend.fail_destroy = True

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    assert outcome.completed is False
    assert outcome.destroy_confirmed is False
    assert outcome.state.resource_status("compute") == RESOURCE_DESTROY_REQUESTED
    assert outcome.abort_reason is not None


def test_destroy_api_error_leaves_destroy_unknown_and_is_recovered_on_resume(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    backend.fail_destroy_confirmation = True

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    assert outcome.completed is False
    assert outcome.destroy_confirmed is False
    assert outcome.state.resource_status("compute") == RESOURCE_DESTROY_UNKNOWN
    assert outcome.abort_reason is not None

    # W-3: resuming with the backend healthy again must recover, not stay stuck.
    backend.fail_destroy_confirmation = False
    outcome2 = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)
    assert outcome2.destroy_confirmed is True
    assert outcome2.completed is True


def test_budget_cap_stops_run_and_still_destroys(tmp_path):
    spec = make_spec(budget={"max_usd": 40, "max_hours": 0.0001, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 2})
    clock = FakeClock(step=5.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True)

    assert outcome.abort_reason is not None
    assert outcome.state.stage_status("span") == STAGE_CANCELLED
    assert outcome.destroy_confirmed is True
    assert outcome.work_status == "failed"


def test_wallclock_cap_enforced_while_host_unreachable(tmp_path):
    spec = make_spec(budget={"max_usd": 40, "max_hours": 0.001, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 2})
    clock = FakeClock(step=2.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    run_id = "r1"
    idempotency_key = f"{run_id}:compute"
    provisioned = backend.provision(spec.compute, idempotency_key)
    backend.unreachable_hosts.add(provisioned.resource_id)

    outcome = run(
        spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id=run_id,
        poll_interval_seconds=0.0, max_unreachable_polls=1000, dry_run=True,
    )

    assert outcome.completed is False
    assert outcome.abort_reason is not None
    assert outcome.state.stage_status("span") == STAGE_CANCELLED
    assert outcome.destroy_confirmed is True


def test_span_failure_skips_downstream_stages(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def failing_span(resource_id, stage_plan):
        return ExecuteResult(ok=False, kind="task_failure", detail="span cohort mismatch")

    outcome = run(
        spec, backend, stage_executors={"span": failing_span, "data": ok_executor, "train": ok_executor},
        run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True,
    )

    assert outcome.state.stage_status("span") == "failed"
    assert outcome.state.stage_status("data") == STAGE_CANCELLED
    assert outcome.state.stage_status("train") == STAGE_CANCELLED
    # "completed" tracks cleanup only; work_status is what tells you the run
    # did not actually succeed.
    assert outcome.completed is True
    assert outcome.destroy_confirmed is True
    assert outcome.work_status == "failed"
    assert "span" in outcome.work_reason
    assert outcome.success is False


def test_ordinary_execute_exception_is_caught_and_cleanup_still_runs(tmp_path):
    # W-2: an ordinary exception raised by a stage executor must not escape
    # run() uncaught; it becomes a typed failure and cleanup still completes
    # in the same call, no restart required.
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def buggy_span(resource_id, stage_plan):
        raise RuntimeError("a bug in the executor, not a process crash")

    outcome = run(
        spec, backend, stage_executors={"span": buggy_span, "data": ok_executor, "train": ok_executor},
        run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True,
    )

    assert outcome.state.stage_status("span") == "failed"
    assert outcome.destroy_confirmed is True  # cleanup ran despite the exception
    assert outcome.work_status == "failed"


# --- W-1: provisioning-phase crash recovery (a real process kill, both sides of the provider call) ---


def test_crash_before_provider_call_then_resume_does_not_double_provision(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    run_dir = str(tmp_path)
    run_id = "r1"

    # Simulate a real crash: persist "provisioning" (as the runner does right
    # before calling backend.provision) but never call the backend at all.
    effective_stages = ["preflight", "span", "data", "train"]
    state = RunState.new(run_id, run_dir, effective_stages)
    state.extra["identity_digest"] = spec.identity_digest()
    state.extra["start_time"] = clock()
    state.idempotency_key = f"{run_id}:compute"
    state.save()
    state.transition_stage("preflight", STAGE_RUNNING)
    state.transition_stage("preflight", "succeeded")
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    # (no backend.provision() call at all: the crash happened before it)

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=run_dir, clock=clock, run_id=run_id, dry_run=True)

    assert len(backend._resources) == 1  # exactly one resource ever created
    assert outcome.completed is True


def test_crash_after_provider_call_then_resume_does_not_double_provision(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    run_dir = str(tmp_path)
    run_id = "r1"

    effective_stages = ["preflight", "span", "data", "train"]
    state = RunState.new(run_id, run_dir, effective_stages)
    state.extra["identity_digest"] = spec.identity_digest()
    state.extra["start_time"] = clock()
    idempotency_key = f"{run_id}:compute"
    state.idempotency_key = idempotency_key
    state.save()
    state.transition_stage("preflight", STAGE_RUNNING)
    state.transition_stage("preflight", "succeeded")
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    # Simulate the crash landing AFTER the provider created the resource but
    # BEFORE the runner persisted the returned id (W-1's exact failure mode).
    backend.provision(spec.compute, idempotency_key)
    state.save()  # still no backend_resource_id recorded

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=run_dir, clock=clock, run_id=run_id, dry_run=True)

    assert len(backend._resources) == 1  # the stranded resource was recovered, not duplicated
    assert outcome.completed is True


# --- W-9: attempt limit persists and is enforced across restarts ---


def test_max_attempts_enforced_across_restart(tmp_path):
    spec = make_spec(budget={"max_usd": 40, "max_hours": 8, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 1})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    run_dir = str(tmp_path)
    run_id = "r1"

    state = RunState.new(run_id, run_dir, ["preflight", "span", "data", "train"])
    state.extra["identity_digest"] = spec.identity_digest()
    state.extra["start_time"] = clock()
    idempotency_key = f"{run_id}:compute"
    state.idempotency_key = idempotency_key
    state.save()
    state.transition_stage("preflight", STAGE_RUNNING)
    state.transition_stage("preflight", "succeeded")
    provisioned = backend.provision(spec.compute, idempotency_key)
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    state.transition_resource("compute", RESOURCE_READY, backend_resource_id=provisioned.resource_id, host=provisioned.host, port=provisioned.port)
    state.transition_resource("compute", RESOURCE_ACTIVE)
    state.transition_stage("span", STAGE_RUNNING)
    state.extra.setdefault("stage_attempts", {})["span"] = 1  # one attempt already used, limit is 1
    state.save()

    calls = []

    def span_executor(resource_id, stage_plan):
        calls.append(1)
        return ExecuteResult(ok=True, kind="ok", output_manifest={"span.json": "hash1"})

    outcome = run(spec, backend, stage_executors={"span": span_executor, "data": ok_executor, "train": ok_executor},
                  run_dir=run_dir, clock=clock, run_id=run_id, dry_run=True)

    assert calls == []  # the attempt limit was already reached; the executor must not run again
    assert outcome.state.stage_status("span") == "failed"
    assert "max_attempts_per_stage" in outcome.abort_reason


# --- W-6: unique run identity, incompatible resume rejection, single owner ---


def test_two_runs_of_the_same_pair_get_separate_resources(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome_a = run(spec, backend, stage_executors={}, run_dir=str(tmp_path / "a"), clock=clock, dry_run=True)
    outcome_b = run(spec, backend, stage_executors={}, run_dir=str(tmp_path / "b"), clock=clock, dry_run=True)

    id_a = outcome_a.state.resource_meta["compute"]["backend_resource_id"]
    id_b = outcome_b.state.resource_meta["compute"]["backend_resource_id"]
    assert id_a != id_b


def test_incompatible_resume_is_rejected(tmp_path):
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    run_dir = str(tmp_path)

    run(spec, backend, stage_executors={}, run_dir=run_dir, clock=clock, run_id="r1", dry_run=True)

    changed_spec = make_spec(inputs={"captures": "sha256:changed", "tasks": "sha256:def"})
    with pytest.raises(IncompatibleResumeError):
        run(changed_spec, backend, stage_executors={}, run_dir=run_dir, clock=clock, run_id="r1", dry_run=True)


def _hold_lock_in_subprocess(run_dir):
    """Starts a real second process that holds the run lock, and waits until it does."""
    import os as _os, sys, time as _time
    ready = _os.path.join(run_dir, "holder-ready")
    code = (
        "import fcntl,os,sys,time\n"
        "fd=os.open(os.path.join(sys.argv[1],'lock'),os.O_CREAT|os.O_RDWR)\n"
        "fcntl.flock(fd,fcntl.LOCK_EX)\n"
        "open(sys.argv[2],'w').close()\n"
        "time.sleep(30)\n"
    )
    _os.makedirs(run_dir, exist_ok=True)
    process = subprocess.Popen([sys.executable, "-c", code, run_dir, ready])
    for _ in range(200):
        if _os.path.exists(ready):
            return process
        _time.sleep(0.02)
    process.kill()
    raise RuntimeError("lock-holder subprocess did not start")


def test_concurrent_owner_lock_is_enforced(tmp_path):
    run_dir = str(tmp_path)
    process = _hold_lock_in_subprocess(run_dir)
    try:
        with pytest.raises(RuntimeError, match="already owned"):
            acquire_run_lock(run_dir)
    finally:
        process.kill()
        process.wait()


# --- W-8: fail-closed preflight checks outside dry_run ---


def test_preflight_requires_credit_outside_dry_run(tmp_path):
    spec = make_spec()  # compute has no available_credit
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1")

    assert outcome.work_status == "preflight_failed"
    assert "credit" in outcome.work_reason


def test_preflight_requires_existing_pair_path_outside_dry_run(tmp_path):
    spec = make_spec(compute={"backend": "fake", "available_credit": 100})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1")

    assert outcome.work_status == "preflight_failed"
    assert "pair manifest" in outcome.work_reason


def test_preflight_requires_executors_outside_dry_run(tmp_path, monkeypatch):
    spec_document = base_spec_dict(compute={"backend": "fake", "available_credit": 100})
    spec = spec_from_dict(spec_document)
    spec.validate()
    # Make the pair path resolve so only the missing-executor check trips.
    pair_path = tmp_path / "pair.yaml"
    pair_path.write_text("placeholder")
    spec.pair = str(pair_path)

    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    outcome = run(spec, backend, stage_executors={"span": ok_executor}, run_dir=str(tmp_path / "rundir"), clock=clock, run_id="r1")

    assert outcome.work_status == "preflight_failed"
    assert "executor" in outcome.work_reason


# --- W-2 (recheck): every provider call after ownership must be exception-safe ---


def test_inspect_exception_while_waiting_for_reachability_is_caught(tmp_path):
    # Regression for the recheck's W-2 finding: an exception from
    # backend.inspect() during the reachability wait used to escape run()
    # uncaught. It must instead be treated as "not reachable this poll," let
    # the wall-clock/budget caps keep working, and still lead to cleanup.
    spec = make_spec(budget={"max_usd": 40, "max_hours": 8, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 2})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def always_raising_inspect(resource_id):
        raise RuntimeError("simulated provider API error from inspect()")

    backend.inspect = always_raising_inspect

    outcome = run(
        spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=str(tmp_path), clock=clock, run_id="r1",
        poll_interval_seconds=0.0, max_unreachable_polls=5, dry_run=True,
    )

    assert outcome.state.stage_status("span") == STAGE_CANCELLED
    assert outcome.abort_reason is not None
    assert outcome.destroy_confirmed is True  # cleanup still ran despite inspect() always raising


def test_inspect_exception_during_provisioning_reconciliation_is_caught(tmp_path):
    # Regression for the exact "runner.py around line 258" (now in
    # _ensure_provisioned): resuming with a resource id already on file, where
    # backend.inspect() raises during reconciliation, must not escape either.
    spec = make_spec()
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)
    run_dir = str(tmp_path)
    run_id = "r1"

    state = RunState.new(run_id, run_dir, ["preflight", "span", "data", "train"])
    state.extra["identity_digest"] = spec.identity_digest()
    state.extra["start_time"] = clock()
    idempotency_key = f"{run_id}:compute"
    state.idempotency_key = idempotency_key
    state.save()
    state.transition_stage("preflight", STAGE_RUNNING)
    state.transition_stage("preflight", "succeeded")
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    # Simulate a resource id having been noted before a crash, without ever
    # reaching `ready` (an unusual but possible intermediate state).
    state.resource_meta.setdefault("compute", {})["backend_resource_id"] = "fake-orphan-id"
    state.save()

    def always_raising_inspect(resource_id):
        raise RuntimeError("simulated provider API error from inspect()")

    backend.inspect = always_raising_inspect

    outcome = run(spec, backend, stage_executors=ALL_STAGE_EXECUTORS, run_dir=run_dir, clock=clock, run_id=run_id, dry_run=True)

    assert outcome.state.resource_status("compute") in (RESOURCE_PROVISIONING, RESOURCE_DESTROY_REQUESTED, "destroy_confirmed")
    assert outcome.work_status == "failed"
    assert outcome.abort_reason is not None


# --- W-6 (recheck): identity_digest must hash file contents, not just paths ---


def test_identity_digest_changes_when_pair_file_contents_change(tmp_path):
    pair_path = tmp_path / "pair.yaml"
    pair_path.write_text("version: 1")
    spec = make_spec(pair=str(pair_path))
    digest_before = spec.identity_digest()

    pair_path.write_text("version: 2")
    digest_after = spec.identity_digest()

    assert digest_before != digest_after


def test_identity_digest_stable_when_pair_file_contents_unchanged(tmp_path):
    pair_path = tmp_path / "pair.yaml"
    pair_path.write_text("version: 1")
    spec_a = make_spec(pair=str(pair_path))
    spec_b = make_spec(pair=str(pair_path))
    assert spec_a.identity_digest() == spec_b.identity_digest()


def test_identity_digest_changes_when_input_file_contents_change(tmp_path):
    captures_path = tmp_path / "captures.jsonl"
    captures_path.write_text("line one")
    spec = make_spec(inputs={"captures": str(captures_path), "tasks": "sha256:def"})
    digest_before = spec.identity_digest()

    captures_path.write_text("line one, edited")
    digest_after = spec.identity_digest()

    assert digest_before != digest_after


def test_resume_rejected_when_pinned_pair_file_is_edited(tmp_path):
    pair_path = tmp_path / "pair.yaml"
    pair_path.write_text("version: 1")
    run_dir = str(tmp_path / "rundir")
    spec = make_spec(pair=str(pair_path))
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    run(spec, backend, stage_executors={}, run_dir=run_dir, clock=clock, run_id="r1", dry_run=True)

    pair_path.write_text("version: 2, quietly changed")
    edited_spec = make_spec(pair=str(pair_path))
    with pytest.raises(IncompatibleResumeError):
        run(edited_spec, backend, stage_executors={}, run_dir=run_dir, clock=clock, run_id="r1", dry_run=True)


# --- N-2 (recheck): the run lock must be atomic, with safe stale-lock reclaim ---


def test_lock_is_reentrant_for_the_same_process(tmp_path):
    run_dir = str(tmp_path)
    path1 = acquire_run_lock(run_dir)
    path2 = acquire_run_lock(run_dir)  # same pid: must not raise
    assert path1 == path2
    release_run_lock(run_dir)


def test_lock_file_contents_do_not_decide_ownership(tmp_path):
    """A leftover lock file (corrupt contents or a dead or live foreign PID) is
    not a lock; only a process actually holding the OS lock is."""
    import os as _os

    run_dir = str(tmp_path)
    _os.makedirs(run_dir, exist_ok=True)
    with open(_os.path.join(run_dir, "lock"), "w") as handle:
        handle.write("not-a-pid")
    acquire_run_lock(run_dir)  # must not raise
    release_run_lock(run_dir)


def test_lock_is_released_when_the_holder_dies(tmp_path):
    run_dir = str(tmp_path)
    process = _hold_lock_in_subprocess(run_dir)
    process.kill()
    process.wait()
    acquire_run_lock(run_dir)  # kernel released the dead holder's lock
    release_run_lock(run_dir)

def test_lock_rejects_a_lock_held_by_a_live_different_process(tmp_path):
    run_dir = str(tmp_path)
    process = _hold_lock_in_subprocess(run_dir)
    try:
        with pytest.raises(RuntimeError, match="already owned"):
            acquire_run_lock(run_dir)
    finally:
        process.kill()
        process.wait()

# --- W-8 (recheck): minimal fail-closed gate evaluation ---


def test_gate_passes_when_metric_meets_threshold(tmp_path):
    spec = make_spec(gates={"span": {"share_min": 0.25}})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def span_with_metrics(resource_id, stage_plan):
        return ExecuteResult(ok=True, kind="ok", output_manifest={"span.json": "h"}, metrics={"share": 0.4})

    outcome = run(
        spec, backend, stage_executors={"span": span_with_metrics, "data": ok_executor, "train": ok_executor},
        run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True,
    )

    assert outcome.state.stage_status("span") == STAGE_SUCCEEDED
    assert outcome.work_status == "succeeded"


def test_gate_failure_on_unmet_threshold_skips_downstream(tmp_path):
    spec = make_spec(gates={"span": {"share_min": 0.25}})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def span_below_threshold(resource_id, stage_plan):
        return ExecuteResult(ok=True, kind="ok", output_manifest={"span.json": "h"}, metrics={"share": 0.1})

    outcome = run(
        spec, backend, stage_executors={"span": span_below_threshold, "data": ok_executor, "train": ok_executor},
        run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True,
    )

    assert outcome.state.stage_status("span") == "failed"
    assert outcome.state.stage_status("data") == STAGE_CANCELLED
    assert outcome.state.extra["stage_failures"]["span"]["kind"] == "gate_failure"
    assert "share" in outcome.state.extra["stage_failures"]["span"]["detail"]


def test_gate_failure_on_missing_metric_fails_closed(tmp_path):
    spec = make_spec(gates={"span": {"share_min": 0.25}})
    clock = FakeClock(step=1.0)
    backend = FakeBackend(clock=clock, hourly_usd=1.0)

    def span_without_metrics(resource_id, stage_plan):
        return ExecuteResult(ok=True, kind="ok", output_manifest={"span.json": "h"})  # no metrics reported

    outcome = run(
        spec, backend, stage_executors={"span": span_without_metrics, "data": ok_executor, "train": ok_executor},
        run_dir=str(tmp_path), clock=clock, run_id="r1", dry_run=True,
    )

    assert outcome.state.stage_status("span") == "failed"
    assert outcome.state.extra["stage_failures"]["span"]["kind"] == "gate_failure"
    assert "not reported" in outcome.state.extra["stage_failures"]["span"]["detail"]


# --- Recheck 2: gates fail closed for non-numeric fields and non-finite values ---


def test_gate_scalar_field_requires_matching_metric():
    from steno.loop.runner import _evaluate_gate

    ok, _ = _evaluate_gate("span", {"invariance": "all_calls"}, {"invariance": "all_calls"})
    assert ok
    ok, reason = _evaluate_gate("span", {"invariance": "all_calls"}, {})
    assert not ok and "not reported" in reason
    ok, reason = _evaluate_gate("span", {"invariance": "all_calls"}, {"invariance": "sampled"})
    assert not ok and "expected" in reason


def test_gate_rejects_non_finite_threshold_and_metric():
    from steno.loop.runner import _evaluate_gate

    ok, reason = _evaluate_gate("span", {"share_min": float("nan")}, {"share": 0.7})
    assert not ok and "finite" in reason
    ok, reason = _evaluate_gate("span", {"share_min": 0.25}, {"share": float("nan")})
    assert not ok and "finite" in reason


def test_gate_structured_value_fails_closed():
    from steno.loop.runner import _evaluate_gate

    ok, reason = _evaluate_gate("evaluate", {"teacher_reference": {"score": 12}}, {"teacher_reference": 12})
    assert not ok and "not evaluable" in reason
