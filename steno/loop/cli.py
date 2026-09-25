"""``python -m steno.loop.cli validate|dry-run <spec>`` (steno-design.md section 3, step 5).

validate: parses and validates a spec, printing a clear pass/fail message.
dry-run: runs the spec against a FakeBackend with no-op stage executors (no
network, no GPU, no vast.ai calls) and prints the resulting lifecycle.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from .backend import FakeBackend
from .runner import run
from .spec import SpecValidationError, load_spec


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        spec = load_spec(args.spec_path)
        spec.validate()
    except SpecValidationError as error:
        print(f"INVALID: {error}")
        return 1
    except OSError as error:
        print(f"ERROR: could not read spec: {error}")
        return 2
    print(f"VALID: schema={spec.schema} pair={spec.pair} stages={spec.stages}")
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    try:
        spec = load_spec(args.spec_path)
        spec.validate()
    except SpecValidationError as error:
        print(f"INVALID: {error}")
        return 1

    run_dir = args.run_dir or tempfile.mkdtemp(prefix="steno-dry-run-")
    os.makedirs(run_dir, exist_ok=True)

    clock_state = {"t": 0.0}

    def clock() -> float:
        clock_state["t"] += 1.0
        return clock_state["t"]

    backend = FakeBackend(clock=clock, hourly_usd=float(spec.compute.get("dry_run_hourly_usd", 1.0)))
    outcome = run(spec, backend, stage_executors={}, run_dir=run_dir, clock=clock, dry_run=True)

    print(f"run_dir: {run_dir}")
    print(f"stages: {outcome.state.stages}")
    print(f"resource: {outcome.state.resources}")
    print(f"sync_verified: {outcome.sync_verified}")
    print(f"destroy_confirmed: {outcome.destroy_confirmed}")
    print(f"cleanup completed: {outcome.completed}")
    print(f"work_status: {outcome.work_status}")
    if outcome.work_reason:
        print(f"work_reason: {outcome.work_reason}")
    if outcome.abort_reason:
        print(f"abort_reason: {outcome.abort_reason}")
    print(f"success: {outcome.success}")
    # "completed" alone (cleanup) is never treated as success; the exit code
    # requires both cleanup completion and work success (W-5).
    return 0 if outcome.success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m steno.loop.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="parse and validate a run spec")
    validate_parser.add_argument("spec_path")
    validate_parser.set_defaults(func=_cmd_validate)

    dry_run_parser = subparsers.add_parser("dry-run", help="run a spec against FakeBackend, no network or GPU")
    dry_run_parser.add_argument("spec_path")
    dry_run_parser.add_argument("--run-dir", default=None, help="directory to persist state (default: a temp dir)")
    dry_run_parser.set_defaults(func=_cmd_dry_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
