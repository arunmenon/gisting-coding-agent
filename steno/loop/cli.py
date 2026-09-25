"""``python -m steno.loop.cli validate|dry-run|quote <spec>`` (steno-design.md
section 3, step 5; the `quote` subcommand is wave 2, build order step 9).

validate: parses and validates a spec, printing a clear pass/fail message.
dry-run: runs the spec against a FakeBackend with no-op stage executors (no
network, no GPU, no vast.ai calls) and prints the resulting lifecycle.
quote: read-only. Resolves the spec's ``compute.backend`` from the registry
and prints its offers for ``compute.request``. For a real backend (for
example ``vast``) this makes read-only provider API calls only (a search, no
create/start/destroy); it never provisions anything.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from .backend import FakeBackend
from .backends import create_backend
from .compute import ComputeRequest, ComputeRequestError
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


def _cmd_quote(args: argparse.Namespace) -> int:
    try:
        spec = load_spec(args.spec_path)
        spec.validate()
    except SpecValidationError as error:
        print(f"INVALID: {error}")
        return 1

    backend_name = spec.compute.get("backend")
    if not backend_name:
        print("ERROR: compute.backend is required to resolve a backend for quote")
        return 2

    try:
        backend = create_backend(backend_name, spec.compute.get("backend_options", {}))
    except Exception as error:
        print(f"ERROR: could not create backend {backend_name!r}: {error}")
        return 2

    try:
        request = ComputeRequest.from_dict(spec.compute.get("request"))
        request.validate()
    except ComputeRequestError as error:
        print(f"INVALID: compute.request: {error}")
        return 1

    try:
        offers = backend.quote(request)
    except Exception as error:
        print(f"ERROR: quote failed: {error}")
        return 2

    print(f"backend: {backend_name} ({len(offers)} offer(s))")
    for offer in offers:
        print(
            f"{offer.offer_id}\t{offer.gpu_family}\tgpus={offer.gpu_count}\t"
            f"mem_gb={offer.gpu_memory_gb:.1f}\t${offer.hourly_usd:.3f}/hr\t"
            f"region={offer.region}\treliability={offer.reliability}"
        )
    return 0


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

    quote_parser = subparsers.add_parser("quote", help="read-only: print the spec's backend's offers")
    quote_parser.add_argument("spec_path")
    quote_parser.set_defaults(func=_cmd_quote)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
