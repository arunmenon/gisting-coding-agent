"""Generic all-call span discovery and the invariance report.

Everything here works against `CallRecord`s only, never against a harness's wire format, so the
same code serves every harness adapter. Per steno-design.md section 3 step 2: this looks at
*every* captured call, not just the most common one, groups calls into cohorts, and produces a
per-call invariance check that fails the run on any uncovered difference.

**Discovery vs validation (W-13).** These are two different questions and this module keeps them
separate:

- `discover(calls, rules)` looks at a set of calls with no prior assumptions and derives a
  *segment map* per cohort: which lines are fixed, which are protected by a declared rule, and
  which vary without being covered by anything. It can only report "consistent with itself,"
  and a cohort with fewer than two calls has no cross-call evidence at all -- that is reported
  explicitly as `insufficient_evidence`, not silently treated as a pass.
- `validate(calls, segment_map_bundle, rules)` checks a *fresh* set of calls against a *frozen*
  segment map produced by an earlier `discover()` call (typically on a different, larger
  capture). A call whose cohort was never seen during discovery gets `insufficient_evidence`
  too, but for the opposite reason: there is no earlier map to compare it against.
- `report(calls, rules)` is discovery followed immediately by self-validation (the map is
  derived from, and then checked against, the same calls). This is what `steno.span.cli report`
  runs; it is not a substitute for validating a later capture against an earlier, frozen map.

**Capture accounting (W-10).** `select_and_parse()` is the single place a raw capture becomes
either a `CallRecord` or an explained exclusion (`parse_error`, with the raw pointer and a
reason). Nothing an adapter's `wants()` accepts is allowed to disappear silently: a bare
`except: continue` around `parse_request()` is exactly the bug this function exists to prevent.

Comparison granularity is whole lines, matching the line-oriented raw-value rules Claude Code's
adapter ports from `experiments/gist/segments.py` (`VERBATIM_LINE` is a `re.MULTILINE` pattern
that matches whole lines). A varying character run that never lines up with a whole line would
need character-level analysis; that refinement is left for a later wave, noted in
`known_gaps()` below.

Token counting is explicitly out of scope this wave (steno-design.md: "tokens are counted only
through the model adapter"). This module reports character counts instead and exposes
`character_count` as the one hook a model adapter should replace with real token counts once it
exists; nothing here assumes character counts equal token counts.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable, List, Optional, Tuple

from .record import CallRecord, RawValueRule, sha256_of

REPORT_SCHEMA_VERSION = "steno-span-report/v2"


def character_count(text: str) -> int:
    """The character-count hook. Replace with a model adapter's real token count in a later
    wave; every call site that means "size of this span" should go through this function so
    that swap is one place, not scattered `len()` calls."""
    return len(text)


def known_gaps() -> List[str]:
    return [
        "Comparison is line-granular; a varying run that does not align to a whole line is not "
        "separately analysed within that line.",
        "Token counting is out of scope; character_count() is a placeholder a model adapter "
        "should replace.",
        "Session-consistency classification assumes calls with the same session_id came from "
        "the same run; it does not detect a reused session_id across unrelated captures.",
        "Bundle-identity enforcement (steno.span.manifest.DeployableBundle.validate() being "
        "called by a proxy or dataset builder) is not implemented; see manifest.py and README.md.",
    ]


# --------------------------------------------------------------------------------------
# Capture accounting (W-10)
# --------------------------------------------------------------------------------------

def select_and_parse(raws: Iterable[Any], adapter) -> Tuple[List[CallRecord], List[dict]]:
    """Every raw capture that the adapter claims (`wants()` is true) gets an explicit outcome:
    "parsed" (with the resulting CallRecord kept) or "parse_error" (with a reason and the raw
    pointer, kept in the outcome list even though no CallRecord resulted). A raw the adapter does
    not want is not "excluded" in the sense this exists to catch -- it was never in scope -- so
    it gets no outcome entry at all. Returns (calls, outcomes); callers decide how strict the
    gate on parse_error outcomes should be (the CLI fails the run on any)."""
    calls: List[CallRecord] = []
    outcomes: List[dict] = []
    for line_index, raw in enumerate(raws):
        pointer = raw.get("id") if isinstance(raw, dict) else None
        try:
            wanted = adapter.wants(raw)
        except Exception as error:  # an adapter bug in wants() is itself an explained exclusion
            outcomes.append({"line": line_index, "raw_pointer": pointer, "outcome": "parse_error",
                              "reason": "wants() raised: %r" % (error,)})
            continue
        if not wanted:
            continue
        try:
            call = adapter.parse_request(raw)
        except Exception as error:
            outcomes.append({"line": line_index, "raw_pointer": pointer, "outcome": "parse_error",
                              "reason": repr(error)[:300]})
            continue
        calls.append(call)
        outcomes.append({"line": line_index, "raw_pointer": call.raw_pointer, "outcome": "parsed"})
    return calls, outcomes


def outcome_summary(outcomes: List[dict]) -> dict:
    parsed = sum(1 for o in outcomes if o["outcome"] == "parsed")
    parse_errors = [o for o in outcomes if o["outcome"] == "parse_error"]
    return {
        "selected": len(outcomes),
        "parsed": parsed,
        "parse_error": len(parse_errors),
        "parse_error_details": parse_errors,
    }


# --------------------------------------------------------------------------------------
# Cohorting
# --------------------------------------------------------------------------------------

def _cohort_key(call: CallRecord):
    structure = tuple(part.source for part in call.preamble)
    return (call.catalogue_hash(), structure)


def _compiled_rules(rules: Iterable[RawValueRule]):
    return [(rule, re.compile(rule.pattern)) for rule in rules]


def _rule_match(line: Optional[str], compiled_rules) -> Optional[str]:
    if line is None:
        return None
    for rule, pattern in compiled_rules:
        if pattern.search(line):
            return rule.name
    return None


def _line_at(lines: List[str], index: int) -> Optional[str]:
    return lines[index] if 0 <= index < len(lines) else None


def _varying_line_indices(lines_per_call: List[List[str]]) -> set:
    import difflib

    base = lines_per_call[0]
    varying = set()
    for other in lines_per_call[1:]:
        matcher = difflib.SequenceMatcher(None, base, other, autojunk=False)
        for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
            if tag != "equal":
                varying.update(range(i1, max(i2, i1 + 1)))
    return varying


# --------------------------------------------------------------------------------------
# Discovery: deriving a segment map from a set of calls (W-11, W-12)
# --------------------------------------------------------------------------------------

def _classify_part(position: int, calls: List[CallRecord], compiled_rules) -> dict:
    """Per-line classification for one preamble part position, aligned by cohort structure.

    W-12: every line is scanned for a rule match, not only lines that happen to vary in this
    sample -- a declared protected value must be excluded from the fixed/compressible count even
    when the captured evidence happens to agree on it everywhere (a singleton cohort, or a
    coincidence of which sessions were captured).

    W-11: classification and rule-matching are evaluated per individual line, never on a merged
    multi-line block. Grouping equal-classification, equal-rule, adjacent lines into a displayed
    range happens only after every line's own classification is settled, so two adjacent
    rule-covered lines both end up "protected-raw," not "unresolved" merely because they are
    contiguous. Session/call classification is likewise computed per line, so a multi-line range
    never loses that information to "None"."""
    texts = [call.preamble[position].text for call in calls]
    lines_per_call = [text.split("\n") for text in texts]
    base_lines = lines_per_call[0]

    varying_indices = _varying_line_indices(lines_per_call)
    protected_indices = {index for index, line in enumerate(base_lines) if _rule_match(line, compiled_rules)}
    considered = varying_indices | protected_indices

    line_classifications = {}
    for index in sorted(considered):
        per_call_lines = [_line_at(lines, index) for lines in lines_per_call]
        rule_hits = {_rule_match(line, compiled_rules) for line in per_call_lines}
        if len(rule_hits) == 1 and None not in rule_hits:
            classification, rule_name, covered = "protected-raw", next(iter(rule_hits)), True
        elif index not in varying_indices:
            # The base line matches a rule but at least one other call's line at this index does
            # not (rare: a rule that should protect a value stopped matching for one call). Not
            # safe to call this fixed either, since the base line was flagged as sensitive.
            classification, rule_name, covered = "unresolved", None, False
        else:
            by_session = defaultdict(set)
            all_sessions_known = all(call.session_id is not None for call in calls)
            for call, line in zip(calls, per_call_lines):
                by_session[call.session_id].add(line)
            varies_within_a_session = any(len(values) > 1 for values in by_session.values())
            classification = "session-varying" if (all_sessions_known and not varies_within_a_session) else "call-varying"
            rule_name, covered = None, False

        line_classifications[index] = {
            "classification": classification,
            "rule": rule_name,
            "covered": covered,
            "base_line": base_lines[index] if index < len(base_lines) else None,
        }

    return {
        "source": calls[0].preamble[position].source,
        "kind": calls[0].preamble[position].kind,
        "base_lines": base_lines,
        "line_classifications": line_classifications,
    }


def _display_ranges(part_classification: dict) -> List[dict]:
    """Groups consecutive lines sharing the same classification and rule into one reported
    range, so two adjacent protected-raw lines show up as a single covered range rather than
    two, while a run that changes classification partway through is not merged incorrectly."""
    line_classifications = part_classification["line_classifications"]
    ranges: List[dict] = []
    for index in sorted(line_classifications):
        info = line_classifications[index]
        if (ranges and ranges[-1]["end_line"] == index
                and ranges[-1]["classification"] == info["classification"]
                and ranges[-1]["rule"] == info["rule"]):
            ranges[-1]["end_line"] = index + 1
            ranges[-1]["base_excerpt"] += "\n" + (info["base_line"] or "")
        else:
            ranges.append({
                "start_line": index,
                "end_line": index + 1,
                "classification": info["classification"],
                "rule": info["rule"],
                "covered": info["covered"],
                "unresolved": not info["covered"],
                "base_excerpt": info["base_line"] or "",
            })
    return ranges


def _check_call_against_part(call_part_text: str, part_classification: dict, compiled_rules) -> List[str]:
    """A call's own text for one part, checked against that part's derived (or frozen)
    classification: every line not in `line_classifications` must equal the base text exactly
    (it is fixed); a "protected-raw" line must still match its declared rule for this specific
    call; a session-varying/call-varying/unresolved line carries no per-call equality
    requirement beyond existing (uncovered ranges already fail the cohort as a whole)."""
    reasons = []
    base_lines = part_classification["base_lines"]
    line_classifications = part_classification["line_classifications"]
    call_lines = call_part_text.split("\n")
    source = part_classification["source"]

    if len(call_lines) != len(base_lines):
        reasons.append("part %s has %d lines, the segment map expects %d" % (source, len(call_lines), len(base_lines)))

    for index, base_line in enumerate(base_lines):
        call_line = _line_at(call_lines, index)
        info = line_classifications.get(index)
        if info is None:
            if call_line != base_line:
                reasons.append("part %s line %d does not match the segment map's fixed line" % (source, index))
        elif info["classification"] == "protected-raw":
            if call_line is None or _rule_match(call_line, compiled_rules) != info["rule"]:
                reasons.append("part %s line %d is declared protected by rule %r but does not match it for this call" % (source, index, info["rule"]))
        else:
            # session-varying / call-varying / unresolved: this line was never established as
            # either fixed or protected, so nothing about it was actually validated -- a segment
            # map containing such a line is not a valid frozen map to check calls against (N-1).
            # This fires regardless of what text the call has here, including arbitrary text a
            # fresh call happens to put in that position: an uncovered line in the map can never
            # be satisfied, on principle, not just when the specific text looks suspicious.
            reasons.append(
                "part %s line %d is %s in the segment map (uncovered by any rule); a segment "
                "map with uncovered lines is not valid for per-call validation"
                % (source, index, info["classification"])
            )
    return reasons


# --------------------------------------------------------------------------------------
# Discovery report
# --------------------------------------------------------------------------------------

def derive_segment_map(calls: List[CallRecord], rules: Iterable[RawValueRule]) -> dict:
    """Derives a JSON-serialisable, frozen-able segment map for one cohort of calls. This is the
    "proposed segment map" a later `validate()` call checks fresh calls against."""
    compiled_rules = _compiled_rules(rules)
    num_parts = len(calls[0].preamble)
    parts = [_classify_part(position, calls, compiled_rules) for position in range(num_parts)]

    unresolved_total = sum(
        sum(1 for info in part["line_classifications"].values() if not info["covered"])
        for part in parts
    )
    sessions = sorted({call.session_id for call in calls if call.session_id is not None})
    return {
        "cohort_id": sha256_of({"catalogue_hash": calls[0].catalogue_hash(), "structure": [p.source for p in calls[0].preamble]}),
        "catalogue_hash": calls[0].catalogue_hash(),
        "structure": [p.source for p in calls[0].preamble],
        "call_count": len(calls),
        "sessions": sessions,
        "sessions_unknown_count": sum(1 for call in calls if call.session_id is None),
        "insufficient_evidence": len(calls) < 2,
        "unresolved_count": unresolved_total,
        "parts": parts,
    }


def _check_calls_against_segment_map(calls: List[CallRecord], segment_map: dict, rules: Iterable[RawValueRule]) -> List[dict]:
    compiled_rules = _compiled_rules(rules)
    per_call = []
    for call in calls:
        reasons = []
        for position, part_classification in enumerate(segment_map["parts"]):
            if position >= len(call.preamble):
                reasons.append("call has only %d preamble parts, segment map expects %d" % (len(call.preamble), len(segment_map["parts"])))
                continue
            reasons.extend(_check_call_against_part(call.preamble[position].text, part_classification, compiled_rules))
        per_call.append({"call_id": call.call_id, "session_id": call.session_id, "pass": not reasons, "reasons": reasons})
    return per_call


def _renderable_segment_map(segment_map: dict) -> dict:
    """The segment map with per-line dicts (int keys) turned into a JSON-safe shape and the
    grouped display ranges attached, for writing to disk or printing."""
    rendered_parts = []
    for part in segment_map["parts"]:
        rendered_parts.append({
            "source": part["source"],
            "kind": part["kind"],
            "total_lines": len(part["base_lines"]),
            "base_lines": part["base_lines"],
            "line_classifications": {str(index): info for index, info in part["line_classifications"].items()},
            "varying_ranges": _display_ranges(part),
            "unresolved_count": sum(1 for info in part["line_classifications"].values() if not info["covered"]),
            "fixed_line_count": len(part["base_lines"]) - len(part["line_classifications"]),
            "fixed_char_count": character_count("\n".join(
                line for index, line in enumerate(part["base_lines"]) if index not in part["line_classifications"]
            )),
            "total_char_count": character_count("\n".join(part["base_lines"])),
        })
    out = dict(segment_map)
    out["parts"] = rendered_parts
    return out


def _segment_map_from_disk(part: dict) -> dict:
    """Inverse of the int-keys-to-str-keys step in `_renderable_segment_map`, for a map that was
    written to disk and read back for `validate`."""
    return {
        "source": part["source"],
        "kind": part["kind"],
        "base_lines": part["base_lines"],
        "line_classifications": {int(index): info for index, info in part["line_classifications"].items()},
    }


def discover(calls: Iterable[CallRecord], rules: Iterable[RawValueRule]) -> dict:
    """Groups calls into cohorts and derives a segment map for each, with no assumption other
    than "these calls are the evidence." A cohort with fewer than two calls is flagged
    `insufficient_evidence`; it is not folded into `pass` as a false positive, but it also does
    not, by itself, fail the run (there being only one example of a shape is not a defect)."""
    calls = list(calls)
    cohorts = defaultdict(list)
    for call in calls:
        cohorts[_cohort_key(call)].append(call)

    segment_maps = []
    per_call_by_cohort = []
    for members in cohorts.values():
        segment_map = derive_segment_map(members, rules)
        per_call = _check_calls_against_segment_map(members, segment_map, rules)
        segment_maps.append(_renderable_segment_map(segment_map))
        per_call_by_cohort.append(per_call)

    cohort_reports = []
    for segment_map, per_call in zip(segment_maps, per_call_by_cohort):
        cohort_pass = segment_map["unresolved_count"] == 0 and all(entry["pass"] for entry in per_call)
        cohort_report = dict(segment_map)
        cohort_report["per_call"] = per_call
        cohort_report["pass"] = cohort_pass
        cohort_reports.append(cohort_report)

    unresolved_ranges_total = sum(c["unresolved_count"] for c in cohort_reports)
    insufficient_evidence_cohorts = [c["cohort_id"] for c in cohort_reports if c["insufficient_evidence"]]
    overall_pass = len(calls) > 0 and all(c["pass"] for c in cohort_reports)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "discover",
        "pass": overall_pass,
        "coverage": {
            "total_calls": len(calls),
            "cohort_count": len(cohort_reports),
            "unresolved_ranges_total": unresolved_ranges_total,
            "insufficient_evidence_cohorts": insufficient_evidence_cohorts,
        },
        "cohorts": cohort_reports,
        "known_gaps": known_gaps(),
    }


def validate(calls: Iterable[CallRecord], segment_map_bundle: List[dict], rules: Iterable[RawValueRule]) -> dict:
    """Checks fresh calls against a frozen segment map bundle (as `discover()` produced and a
    caller persisted). A call whose cohort key is absent from the bundle gets
    `insufficient_evidence` (no earlier map to compare it against), which fails validation --
    unlike discovery, a validation run is claiming compatibility with a specific, identified
    prior map, and silently skipping unknown cohorts would undermine that claim."""
    calls = list(calls)
    maps_by_key = {}
    for segment_map in segment_map_bundle:
        key = (segment_map["catalogue_hash"], tuple(segment_map["structure"]))
        maps_by_key[key] = segment_map

    per_call = []
    matched_cohort_ids = set()
    for call in calls:
        key = _cohort_key(call)
        segment_map = maps_by_key.get(key)
        if segment_map is None:
            per_call.append({"call_id": call.call_id, "session_id": call.session_id, "pass": False,
                              "outcome": "insufficient_evidence",
                              "reasons": ["no segment map for catalogue_hash=%s structure=%s" % key]})
            continue
        matched_cohort_ids.add(segment_map["cohort_id"])
        parts = [_segment_map_from_disk(part) for part in segment_map["parts"]]
        reasons = []
        compiled_rules = _compiled_rules(rules)
        for position, part_classification in enumerate(parts):
            if position >= len(call.preamble):
                reasons.append("call has only %d preamble parts, segment map expects %d" % (len(call.preamble), len(parts)))
                continue
            reasons.extend(_check_call_against_part(call.preamble[position].text, part_classification, compiled_rules))
        per_call.append({"call_id": call.call_id, "session_id": call.session_id, "pass": not reasons,
                          "outcome": "validated", "reasons": reasons})

    overall_pass = len(calls) > 0 and all(entry["pass"] for entry in per_call)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "validate",
        "pass": overall_pass,
        "coverage": {
            "total_calls": len(calls),
            "matched_cohorts": len(matched_cohort_ids),
            "insufficient_evidence_count": sum(1 for entry in per_call if entry.get("outcome") == "insufficient_evidence"),
        },
        "per_call": per_call,
        "known_gaps": known_gaps(),
    }


def build_report(calls: Iterable[CallRecord], rules: Iterable[RawValueRule]) -> dict:
    """`report` = discovery followed by self-validation, kept for the CLI's `report` subcommand
    and for callers that just want one shot at "is this capture internally consistent." It is
    not a substitute for `validate()` against an earlier, frozen, identified map (W-13)."""
    discovery = discover(calls, rules)
    discovery["mode"] = "report"
    return discovery
