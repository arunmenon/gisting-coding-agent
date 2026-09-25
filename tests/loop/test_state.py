import pytest

from steno.loop.state import (
    IllegalTransitionError,
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
)


def test_stage_legal_transitions(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    assert state.stage_status("span") == STAGE_PENDING
    state.transition_stage("span", STAGE_RUNNING)
    assert state.stage_status("span") == STAGE_RUNNING
    state.transition_stage("span", STAGE_SUCCEEDED)
    assert state.stage_status("span") == STAGE_SUCCEEDED


def test_stage_illegal_transition_raises(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    with pytest.raises(IllegalTransitionError):
        state.transition_stage("span", STAGE_SUCCEEDED)  # pending -> succeeded is illegal


def test_stage_terminal_states_are_final(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    state.transition_stage("span", STAGE_RUNNING)
    state.transition_stage("span", STAGE_FAILED)
    with pytest.raises(IllegalTransitionError):
        state.transition_stage("span", STAGE_RUNNING)


def test_stage_cancel_from_pending(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    state.transition_stage("span", STAGE_CANCELLED)
    assert state.stage_status("span") == STAGE_CANCELLED


def test_resource_legal_lifecycle(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    state.transition_resource("compute", RESOURCE_READY)
    state.transition_resource("compute", RESOURCE_ACTIVE)
    state.transition_resource("compute", RESOURCE_SYNCING)
    state.transition_resource("compute", RESOURCE_SYNC_VERIFIED)
    state.transition_resource("compute", RESOURCE_DESTROY_REQUESTED)
    state.transition_resource("compute", RESOURCE_DESTROY_CONFIRMED)
    assert state.resource_status("compute") == RESOURCE_DESTROY_CONFIRMED


def test_resource_destroy_unknown_is_recoverable(tmp_path):
    # W-3: destroy_unknown means "an API error occurred," not "destroyed." It
    # must stay retryable: destroy_requested is reachable from it, and only
    # from there can it reach destroy_confirmed, never directly.
    state = RunState.new("run1", str(tmp_path), ["span"])
    state.transition_resource("compute", RESOURCE_REQUESTED)
    state.transition_resource("compute", RESOURCE_PROVISIONING)
    state.transition_resource("compute", RESOURCE_READY)
    state.transition_resource("compute", RESOURCE_DESTROY_REQUESTED)
    state.transition_resource("compute", RESOURCE_DESTROY_UNKNOWN)

    with pytest.raises(IllegalTransitionError):
        state.transition_resource("compute", RESOURCE_DESTROY_CONFIRMED)  # no shortcut around retrying

    state.transition_resource("compute", RESOURCE_DESTROY_REQUESTED)  # retry
    state.transition_resource("compute", RESOURCE_DESTROY_CONFIRMED)  # now backed by provider evidence
    assert state.resource_status("compute") == RESOURCE_DESTROY_CONFIRMED


def test_resource_illegal_skip_raises(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    state.transition_resource("compute", RESOURCE_REQUESTED)
    with pytest.raises(IllegalTransitionError):
        state.transition_resource("compute", RESOURCE_ACTIVE)  # cannot skip provisioning/ready


def test_resource_must_start_at_requested(tmp_path):
    state = RunState.new("run1", str(tmp_path), ["span"])
    with pytest.raises(IllegalTransitionError):
        state.transition_resource("compute", RESOURCE_PROVISIONING)  # never registered as requested


def test_state_persists_atomically_and_reloads(tmp_path):
    run_dir = str(tmp_path)
    state = RunState.new("run1", run_dir, ["span", "data"])
    state.transition_stage("span", STAGE_RUNNING)
    state.transition_stage("span", STAGE_SUCCEEDED)
    state.transition_resource("compute", RESOURCE_REQUESTED)

    reloaded = RunState.load(run_dir)
    assert reloaded.stage_status("span") == STAGE_SUCCEEDED
    assert reloaded.stage_status("data") == STAGE_PENDING
    assert reloaded.resource_status("compute") == RESOURCE_REQUESTED


def test_events_are_append_only(tmp_path):
    run_dir = str(tmp_path)
    state = RunState.new("run1", run_dir, ["span"])
    state.transition_stage("span", STAGE_RUNNING)
    state.transition_stage("span", STAGE_SUCCEEDED)

    with open(state.events_path) as handle:
        lines = [line for line in handle if line.strip()]
    assert len(lines) >= 3  # run_created + two stage transitions
