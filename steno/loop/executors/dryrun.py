"""``python -m steno.loop.executors.dryrun <spec> [--state <path>]``

The B7 dry-run command: validates a run spec, checks that each declared stage's required local
inputs exist, prints the stage plan (remote command, inputs, expected artifacts, gate) for every
non-preflight stage, replays a real STATE file (default: J11's actual
`experiments/journeys/j11-conn/results/STATE`) through `steno/loop/executors/j11.py`'s marker
parsers to show the typed `ExecuteResult` (ok/kind/detail/metrics) the loop would have recorded,
and evaluates each declared gate against the replayed metrics using the runner's own gate logic
(`steno.loop.runner._evaluate_gate`, imported read-only, never reimplemented here so gate
semantics cannot drift between the real loop and this dry run).

Nothing here executes anything remote, provisions anything, or calls any backend. This is a
standalone script, not `steno.loop.cli`'s `dry-run` subcommand (which drives the full
lifecycle against `FakeBackend`): this one exists specifically to answer "if this spec's stages
ran against the box that produced this STATE file, what would the loop have recorded, and would
its gates have passed?"

Per X-16, the exit code reflects that answer: nonzero if a required input is missing, a stage's
replayed result is not ok, or a declared gate fails against the replayed metrics -- exactly
mirroring how `steno.loop.runner.run()` would have failed the run, matching the runner's own
rule that a stage's gate is only evaluated once the stage itself succeeded.
"""
from __future__ import annotations

import argparse
import os
import sys

from ..runner import _evaluate_gate  # read-only: the exact gate logic the real loop uses
from ..spec import SpecValidationError, load_spec
from .j11 import DEFAULT_STATE_PATH, STAGE_EXECUTORS, STAGE_PLANS
from .markers import parse_state_file


def _print_stage_plan(stage: str, spec) -> bool:
    """Prints one stage's plan and returns True iff every required input exists."""
    plan = STAGE_PLANS.get(stage)
    if plan is None:
        print("  %-10s no executor registered in this wave" % stage)
        return False
    print("  %-10s remote_command: %s" % (stage, plan.remote_command))
    print("             required_inputs: %s" % (plan.required_inputs or "(none)"))
    missing = plan.missing_inputs()
    if missing:
        print("             MISSING: %s" % missing)
    else:
        print("             all required inputs present")
    print("             expected_artifacts: %s" % (plan.expected_artifacts or "(none)"))
    gate = spec.gates.get(stage)
    if gate:
        print("             gate: %s" % gate)
    return not missing


def _run_stage(stage: str, markers):
    executor = STAGE_EXECUTORS[stage]
    if stage == "span":
        return executor.report()
    return executor.result_from_markers(markers)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m steno.loop.executors.dryrun")
    parser.add_argument("spec_path")
    parser.add_argument("--state", default=DEFAULT_STATE_PATH,
                         help="STATE file to replay (default: J11's real recorded run)")
    args = parser.parse_args(argv)

    try:
        spec = load_spec(args.spec_path)
        spec.validate()
    except SpecValidationError as error:
        print("INVALID: %s" % error)
        return 1
    except OSError as error:
        print("ERROR: could not read spec: %s" % error)
        return 2
    print("VALID: schema=%s pair=%s stages=%s" % (spec.schema, spec.pair, spec.stages))

    print("\nStage plan (nothing below is executed):")
    overall_ok = True
    stages_with_executors = []
    for stage in spec.stages:
        if stage == "preflight":
            continue
        inputs_present = _print_stage_plan(stage, spec)
        overall_ok = overall_ok and inputs_present
        if stage in STAGE_EXECUTORS:
            stages_with_executors.append(stage)
        elif inputs_present:
            print("  %-10s WARNING: no executor registered in this wave; cannot replay or gate this stage" % stage)
    if not overall_ok:
        print("\nWARNING: one or more stages are missing required local inputs; a real run would fail preflight.")

    if not os.path.isfile(args.state):
        print("\nNo STATE file at %s; skipping replay." % args.state)
        return 0 if overall_ok else 1

    markers = parse_state_file(args.state)
    print("\nReplaying %s (%d marker lines) through the executors' marker parsers:" % (args.state, len(markers)))

    for stage in stages_with_executors:
        result = _run_stage(stage, markers)
        print("  %s: ok=%s kind=%s detail=%r" % (stage, result.ok, result.kind, result.detail))
        for key in sorted(result.metrics):
            print("    %s = %s" % (key, result.metrics[key]))

        if not result.ok:
            print("  %s: STAGE FAILED, not evaluating its gate (matches runner.run()'s own rule)" % stage)
            overall_ok = False
            continue

        gate_spec = spec.gates.get(stage)
        if gate_spec:
            gate_passed, gate_detail = _evaluate_gate(stage, gate_spec, result.metrics)
            print("  %s: gate %s" % (stage, "PASS" if gate_passed else "FAIL (%s)" % gate_detail))
            if not gate_passed:
                overall_ok = False

    print("\noverall: %s" % ("PASS" if overall_ok else "FAIL"))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
