"""W-11 and W-12: per-line evaluation within merged varying ranges, and protected values
classified before fixed-span discovery even when constant in the sample."""
from steno.span.analysis import derive_segment_map, discover
from steno.span.record import CallRecord, Part, RawValueRule, SCHEMA_VERSION

VERBATIM_LINE_RULE = RawValueRule(
    name="verbatim_line",
    pattern=r"(?im)^.*(?:working directory|\b20\d\d-\d\d-\d\d\b).*$",
    description="a working-directory line or a date line",
)


def make_call(call_id, text, session_id):
    return CallRecord(
        schema_version=SCHEMA_VERSION,
        call_id=call_id,
        harness="test-harness",
        adapter_version="test/1.0.0",
        session_id=session_id,
        session_source="metadata.user_id",
        preamble=[Part(kind="instructions", text=text, source="system[0]")],
        tools=[],
        messages=[],
    )


def test_two_adjacent_rule_covered_lines_do_not_fail_invariance():
    """Codex review W-11's exact case: two lines that each individually match the declared rule,
    sitting next to each other, must not be merged into one range and then judged as a whole
    (which previously disabled rule matching for anything longer than one line)."""
    call_a = make_call("call-a", "working directory /a\nDate: 2026-01-01", session_id="session-1")
    call_b = make_call("call-b", "working directory /b\nDate: 2026-01-02", session_id="session-2")

    report = discover([call_a, call_b], [VERBATIM_LINE_RULE])

    assert report["pass"] is True
    assert report["coverage"]["unresolved_ranges_total"] == 0
    cohort = report["cohorts"][0]
    ranges = cohort["parts"][0]["varying_ranges"]
    assert len(ranges) == 1
    covering_range = ranges[0]
    assert covering_range["start_line"] == 0
    assert covering_range["end_line"] == 2
    assert covering_range["classification"] == "protected-raw"
    assert covering_range["covered"] is True


def test_session_classification_is_not_lost_next_to_a_protected_range():
    """A varying, rule-uncovered line sitting immediately next to a rule-covered line must still
    get its own session/call classification, not "None" from being folded into the same merged
    block as the covered line."""
    call_a1 = make_call("a1", "working directory /a\nrun label: build-x", session_id="session-1")
    call_a2 = make_call("a2", "working directory /a\nrun label: build-x", session_id="session-1")
    call_b1 = make_call("b1", "working directory /b\nrun label: build-y", session_id="session-2")

    calls = [call_a1, call_a2, call_b1]
    segment_map = derive_segment_map(calls, [VERBATIM_LINE_RULE])
    line_info = segment_map["parts"][0]["line_classifications"]

    assert line_info[0]["classification"] == "protected-raw"
    # line 1 ("run label: ...") is not covered by the rule but is constant per session -> session-varying,
    # not merged with line 0's classification and not left as an unexplained None
    assert line_info[1]["classification"] == "session-varying"
    assert line_info[1]["covered"] is False


def test_declared_protected_value_is_excluded_from_fixed_span_even_when_constant():
    """Codex review W-12: two identical preambles containing a working-directory line must not
    report that line as part of the fixed/compressible span just because the captured evidence
    happens to agree on it -- the rule says this value must always stay raw."""
    text = "working directory /a\nsome genuinely fixed instruction line"
    call_a = make_call("call-a", text, session_id="session-1")
    call_b = make_call("call-b", text, session_id="session-2")

    segment_map = derive_segment_map([call_a, call_b], [VERBATIM_LINE_RULE])
    part = segment_map["parts"][0]

    assert 0 in part["line_classifications"]
    assert part["line_classifications"][0]["classification"] == "protected-raw"
    # only the genuinely fixed line (index 1) counts toward the fixed/compressible span
    assert 1 not in part["line_classifications"]


def test_singleton_capture_still_classifies_a_declared_protected_line():
    """Even with only one call (no cross-call variation to diff against), a line matching a
    declared rule must be classified protected-raw, not silently folded into "fixed"."""
    call_a = make_call("call-a", "working directory /a\nan ordinary fixed line", session_id="session-1")
    segment_map = derive_segment_map([call_a], [VERBATIM_LINE_RULE])
    part = segment_map["parts"][0]
    assert part["line_classifications"][0]["classification"] == "protected-raw"
    assert segment_map["insufficient_evidence"] is True  # still flagged: no cross-call evidence at all
