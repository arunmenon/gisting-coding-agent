"""W-10: every selected capture gets an explicit outcome, and an unexplained parse failure is
not allowed to disappear as a bare "skipped" count."""
from steno.span.adapters.claude_code import ClaudeCodeAdapter
from steno.span.analysis import outcome_summary, select_and_parse


def test_every_wanted_capture_gets_an_outcome(fixture_raws):
    adapter = ClaudeCodeAdapter()
    calls, outcomes = select_and_parse(fixture_raws, adapter)
    assert len(outcomes) == len(fixture_raws)  # every fixture line is a /v1/messages call
    assert all(o["outcome"] == "parsed" for o in outcomes)
    assert len(calls) == len(fixture_raws)


def test_a_malformed_selected_call_becomes_an_explicit_parse_error(fixture_raws):
    adapter = ClaudeCodeAdapter()
    malformed = dict(fixture_raws[0])
    malformed["request"] = dict(malformed["request"])
    malformed["request"]["messages"] = [None]  # adapter.wants() still says yes; parsing must not silently drop this

    raws = [fixture_raws[1], malformed]
    calls, outcomes = select_and_parse(raws, adapter)

    assert len(outcomes) == 2
    assert len(calls) == 1  # the malformed one produced no CallRecord
    parse_errors = [o for o in outcomes if o["outcome"] == "parse_error"]
    assert len(parse_errors) == 1
    assert parse_errors[0]["reason"]  # a reason is recorded, not just a silent count

    summary = outcome_summary(outcomes)
    assert summary["selected"] == 2
    assert summary["parsed"] == 1
    assert summary["parse_error"] == 1


def test_unwanted_captures_get_no_outcome_entry():
    adapter = ClaudeCodeAdapter()
    not_a_call = {"path": "/v1/messages/count_tokens", "request": {"model": "x"}}
    calls, outcomes = select_and_parse([not_a_call], adapter)
    assert outcomes == []
    assert calls == []
