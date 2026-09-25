"""N-1 (W-13 partly): a segment map with unresolved lines is not a valid frozen map. validate()
must fail a call checked against it, including when the fresh call puts arbitrary text where the
map itself has unresolved lines -- a map cannot be treated as authoritative for a line nothing
ever established as fixed or protected."""
import copy

from steno.span.analysis import discover, validate
from steno.span.record import CallRecord, Part, RawValueRule, SCHEMA_VERSION

RULE = RawValueRule(name="verbatim_line", pattern=r"(?im)^.*working directory.*$", description="a path line")


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


def test_a_map_with_an_unresolved_line_never_validates_any_call():
    """Two sessions disagree on an uncovered line ("build label"), so discovery leaves it
    unresolved. Freezing that map and validating against it -- even with the exact same calls
    that produced it -- must fail: the map itself is not valid."""
    call_a = make_call("a", "working directory /a\nbuild label: x", session_id="s1")
    call_b = make_call("b", "working directory /b\nbuild label: y", session_id="s2")

    discovery = discover([call_a, call_b], [RULE])
    assert discovery["pass"] is False  # "build label" is uncovered by the rule

    frozen_map = discovery["cohorts"]
    validation = validate([call_a, call_b], frozen_map, [RULE])

    assert validation["pass"] is False
    assert all(not entry["pass"] for entry in validation["per_call"])
    assert any("uncovered by any rule" in reason for entry in validation["per_call"] for reason in entry["reasons"])


def test_arbitrary_text_at_an_unresolved_map_line_still_fails():
    """A fresh call with completely different, arbitrary text at the position the map left
    unresolved must fail -- not because the text looks wrong, but because nothing at that
    position was ever validated."""
    call_a = make_call("a", "working directory /a\nbuild label: x", session_id="s1")
    call_b = make_call("b", "working directory /b\nbuild label: y", session_id="s2")
    discovery = discover([call_a, call_b], [RULE])
    frozen_map = discovery["cohorts"]

    arbitrary = copy.deepcopy(call_a)
    arbitrary.call_id = "arbitrary"
    arbitrary.preamble[0].text = "working directory /a\nanything at all goes here, even nonsense !!!"

    validation = validate([arbitrary], frozen_map, [RULE])
    assert validation["pass"] is False
    assert not validation["per_call"][0]["pass"]


def test_a_map_with_zero_unresolved_lines_does_validate_normally():
    """Sanity check: the fix must not make every map fail -- a genuinely consistent map (no
    uncovered lines) still validates matching calls."""
    call_a = make_call("a", "working directory /a\nan identical fixed line", session_id="s1")
    call_b = make_call("b", "working directory /b\nan identical fixed line", session_id="s2")
    discovery = discover([call_a, call_b], [RULE])
    assert discovery["pass"] is True

    validation = validate([call_a, call_b], discovery["cohorts"], [RULE])
    assert validation["pass"] is True


def test_discover_self_check_also_fails_every_call_touching_an_unresolved_line():
    """The same fix applies to discovery's own self-check (used by report()/build_report()):
    a call whose only problem is an uncovered line must not show pass=True in per_call."""
    call_a = make_call("a", "working directory /a\nbuild label: x", session_id="s1")
    call_b = make_call("b", "working directory /b\nbuild label: y", session_id="s2")
    discovery = discover([call_a, call_b], [RULE])
    cohort = discovery["cohorts"][0]
    assert cohort["pass"] is False
    assert all(not entry["pass"] for entry in cohort["per_call"])
