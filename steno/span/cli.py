"""Command line entry point for span analysis.

    python -m steno.span.cli report   --harness claude-code --captures <jsonl> [--out report.json]
    python -m steno.span.cli discover --harness claude-code --captures <jsonl> --out map.json
    python -m steno.span.cli validate --harness claude-code --captures <jsonl> --map map.json [--out report.json]

`report` is discovery followed by self-validation against the same capture (see
`steno/span/analysis.py`'s module docstring). `discover` derives and freezes a segment map from
one capture; `validate` checks a *different* capture against a previously frozen map. Every
selected capture line gets an explicit outcome (parsed / parse_error); an unexplained exclusion
fails the run (W-10).
"""
from __future__ import annotations

import argparse
import json
import sys

from .analysis import build_report, discover, outcome_summary, select_and_parse, validate
from .adapters.claude_code import ClaudeCodeAdapter

ADAPTERS = {
    "claude-code": ClaudeCodeAdapter,
}


def _get_adapter(name: str):
    adapter_cls = ADAPTERS.get(name)
    if adapter_cls is None:
        print("unknown harness adapter: %s (known: %s)" % (name, ", ".join(sorted(ADAPTERS))), file=sys.stderr)
        return None
    return adapter_cls()


def _load_raws(captures_path: str):
    raws = []
    with open(captures_path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                raws.append(json.loads(line))
    return raws


def _write_json(path, payload):
    with open(path, "w") as out_file:
        json.dump(payload, out_file, indent=2, sort_keys=True)
        out_file.write("\n")


def _print_gate_summary(outcomes_summary: dict, analysis_pass: bool, overall_pass: bool) -> None:
    print("captures selected: %d, parsed: %d, parse_error: %d" % (
        outcomes_summary["selected"], outcomes_summary["parsed"], outcomes_summary["parse_error"]))
    for detail in outcomes_summary["parse_error_details"][:5]:
        print("  parse_error at line %s (raw_pointer=%s): %s" % (detail["line"], detail["raw_pointer"], detail["reason"]))
    print("analysis pass: %s" % analysis_pass)
    print("OVERALL PASS" if overall_pass else "OVERALL FAIL")


def command_report(args: argparse.Namespace) -> int:
    adapter = _get_adapter(args.harness)
    if adapter is None:
        return 2
    raws = _load_raws(args.captures)
    calls, outcomes = select_and_parse(raws, adapter)
    report = build_report(calls, adapter.raw_value_rules())
    outcomes_summary = outcome_summary(outcomes)
    overall_pass = report["pass"] and outcomes_summary["parse_error"] == 0
    report["capture_outcomes"] = outcomes_summary
    report["overall_pass"] = overall_pass
    if args.out:
        _write_json(args.out, report)
    print("cohorts: %d, unresolved ranges: %d" % (report["coverage"]["cohort_count"], report["coverage"]["unresolved_ranges_total"]))
    _print_gate_summary(outcomes_summary, report["pass"], overall_pass)
    return 0 if overall_pass else 1


def command_discover(args: argparse.Namespace) -> int:
    adapter = _get_adapter(args.harness)
    if adapter is None:
        return 2
    raws = _load_raws(args.captures)
    calls, outcomes = select_and_parse(raws, adapter)
    report = discover(calls, adapter.raw_value_rules())
    outcomes_summary = outcome_summary(outcomes)
    overall_pass = report["pass"] and outcomes_summary["parse_error"] == 0
    report["capture_outcomes"] = outcomes_summary
    report["overall_pass"] = overall_pass
    if args.out:
        _write_json(args.out, {"segment_maps": report["cohorts"], "harness": args.harness, "adapter_version": adapter.identity().version})
    print("discovered %d cohorts from %d calls" % (report["coverage"]["cohort_count"], report["coverage"]["total_calls"]))
    _print_gate_summary(outcomes_summary, report["pass"], overall_pass)
    return 0 if overall_pass else 1


def command_validate(args: argparse.Namespace) -> int:
    adapter = _get_adapter(args.harness)
    if adapter is None:
        return 2
    with open(args.map) as handle:
        map_bundle = json.load(handle)
    raws = _load_raws(args.captures)
    calls, outcomes = select_and_parse(raws, adapter)
    report = validate(calls, map_bundle["segment_maps"], adapter.raw_value_rules())
    outcomes_summary = outcome_summary(outcomes)
    overall_pass = report["pass"] and outcomes_summary["parse_error"] == 0
    report["capture_outcomes"] = outcomes_summary
    report["overall_pass"] = overall_pass
    if args.out:
        _write_json(args.out, report)
    print("validated %d calls against %d frozen cohorts (%d matched)" % (
        report["coverage"]["total_calls"], len(map_bundle["segment_maps"]), report["coverage"]["matched_cohorts"]))
    _print_gate_summary(outcomes_summary, report["pass"], overall_pass)
    return 0 if overall_pass else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m steno.span.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser = subparsers.add_parser("report", help="discover, then self-validate, one capture")
    report_parser.add_argument("--harness", required=True, choices=sorted(ADAPTERS))
    report_parser.add_argument("--captures", required=True, help="path to a tap requests.jsonl capture")
    report_parser.add_argument("--out", default=None, help="write the JSON report here")
    report_parser.set_defaults(func=command_report)

    discover_parser = subparsers.add_parser("discover", help="derive a segment map from a capture")
    discover_parser.add_argument("--harness", required=True, choices=sorted(ADAPTERS))
    discover_parser.add_argument("--captures", required=True, help="path to a tap requests.jsonl capture")
    discover_parser.add_argument("--out", required=True, help="write the frozen segment-map bundle here")
    discover_parser.set_defaults(func=command_discover)

    validate_parser = subparsers.add_parser("validate", help="check a capture against a frozen segment map")
    validate_parser.add_argument("--harness", required=True, choices=sorted(ADAPTERS))
    validate_parser.add_argument("--captures", required=True, help="path to a tap requests.jsonl capture")
    validate_parser.add_argument("--map", required=True, help="a segment-map bundle written by `discover`")
    validate_parser.add_argument("--out", default=None, help="write the JSON report here")
    validate_parser.set_defaults(func=command_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
