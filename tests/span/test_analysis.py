import copy

from steno.span.adapters.claude_code import ClaudeCodeAdapter
from steno.span.analysis import build_report

# Call ids of the fixture's one internally-consistent cohort (same catalogue, same preamble
# structure, and every uncovered variation in it is either fixed or matched by the verbatim-line
# rule). Established by running build_report over the whole fixture once and reading off the
# cohort that already passes.
CONSISTENT_COHORT_CALL_IDS = {"aaaaaaaa0001", "aaaaaaaa0006", "aaaaaaaa000a"}


def _consistent_calls(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = [adapter.parse_request(raw) for raw in fixture_raws if adapter.wants(raw)]
    return [call for call in calls if call.call_id in CONSISTENT_COHORT_CALL_IDS]


def test_invariance_report_passes_on_a_consistent_cohort(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)
    assert len(calls) == 3

    report = build_report(calls, adapter.raw_value_rules())

    assert report["pass"] is True
    assert report["coverage"]["cohort_count"] == 1
    assert report["coverage"]["unresolved_ranges_total"] == 0
    assert all(entry["pass"] for entry in report["cohorts"][0]["per_call"])


def test_invariance_report_fails_on_an_uncovered_path_shape(fixture_raws):
    """VERBATIM_LINE matches lines naming /Users/, /private/, /home/ or the words "working
    directory"; it does not match an arbitrary absolute path such as /opt/app/config.toml. That
    gap is exactly the kind of uncovered difference the report must catch and fail on."""
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)

    injected = copy.deepcopy(calls)
    varying_part_index = 1  # the large instructions block, present in every call of this cohort
    injected[0].preamble[varying_part_index].text += "\nreading configuration from /opt/app/config.toml"

    report = build_report(injected, adapter.raw_value_rules())

    assert report["pass"] is False
    assert report["coverage"]["unresolved_ranges_total"] >= 1
    cohort = report["cohorts"][0]
    unresolved = [r for part in cohort["parts"] for r in part["varying_ranges"] if r["unresolved"]]
    assert any("/opt/app/config.toml" in r["base_excerpt"] or "/opt/app/config.toml" in
               injected[0].preamble[varying_part_index].text for r in unresolved)
    failing_calls = [entry for entry in cohort["per_call"] if not entry["pass"]]
    assert failing_calls, "the other two calls should fail the fixed-line check against the injected call"


def test_mismatched_tool_catalogue_lands_in_its_own_cohort(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls = _consistent_calls(fixture_raws)

    mutated = copy.deepcopy(calls)
    from steno.span.record import ToolSpec
    mutated[0].tools = mutated[0].tools + [ToolSpec(name="ExtraTool", description="not in the others", schema={})]

    report = build_report(mutated, adapter.raw_value_rules())

    assert report["coverage"]["cohort_count"] == 2
    catalogue_hashes = {cohort["catalogue_hash"] for cohort in report["cohorts"]}
    assert len(catalogue_hashes) == 2
    call_counts = sorted(cohort["call_count"] for cohort in report["cohorts"])
    assert call_counts == [1, 2]
