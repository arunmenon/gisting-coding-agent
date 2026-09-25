"""W-13: discovery (derive a segment map) is a different operation from validation (check calls
against a frozen, identified segment map). `report()` is discovery plus self-validation only;
it must not be mistaken for validating a fresh capture against an earlier map."""
import copy

from steno.span.adapters.claude_code import ClaudeCodeAdapter
from steno.span.analysis import discover, validate

CONSISTENT_COHORT_CALL_IDS = {"aaaaaaaa0001", "aaaaaaaa0006", "aaaaaaaa000a"}


def _consistent_calls(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = [adapter.parse_request(raw) for raw in fixture_raws if adapter.wants(raw)]
    return [call for call in calls if call.call_id in CONSISTENT_COHORT_CALL_IDS]


def test_validate_against_its_own_frozen_map_passes(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)

    discovery = discover(calls, adapter.raw_value_rules())
    assert discovery["pass"] is True

    validation = validate(calls, discovery["cohorts"], adapter.raw_value_rules())
    assert validation["pass"] is True
    assert validation["coverage"]["insufficient_evidence_count"] == 0
    assert all(entry["outcome"] == "validated" for entry in validation["per_call"])


def test_validate_reports_insufficient_evidence_for_an_unseen_cohort(fixture_raws):
    """A call whose cohort (catalogue hash + preamble structure) was never seen during discovery
    cannot be validated against anything; that must be reported as insufficient evidence, not
    silently skipped or silently passed."""
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)
    discovery = discover(calls[:2], adapter.raw_value_rules())

    mutated = copy.deepcopy(calls[2])
    mutated.tools = mutated.tools + [mutated.tools[0]]  # forces a different catalogue_hash -> unseen cohort

    validation = validate([mutated], discovery["cohorts"], adapter.raw_value_rules())
    assert validation["pass"] is False
    assert validation["coverage"]["insufficient_evidence_count"] == 1
    assert validation["per_call"][0]["outcome"] == "insufficient_evidence"


def test_validate_fails_when_a_fixed_line_changed_after_discovery(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)
    discovery = discover(calls, adapter.raw_value_rules())
    assert discovery["pass"] is True

    drifted = copy.deepcopy(calls)
    drifted[0].preamble[0].text = drifted[0].preamble[0].text + " an instruction that was not there during discovery"

    validation = validate(drifted, discovery["cohorts"], adapter.raw_value_rules())
    assert validation["pass"] is False
    failing = [entry for entry in validation["per_call"] if not entry["pass"]]
    assert failing
    assert any("does not match the segment map's fixed line" in reason for entry in failing for reason in entry["reasons"])
