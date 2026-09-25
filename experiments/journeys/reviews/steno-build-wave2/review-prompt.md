# Code review: Steno build wave 2

Read-only. Emit to stdout. Do not make network calls; do not call any cloud API.

## Context
Wave 1 (reviewed and cleared, trail in `experiments/journeys/reviews/steno-build-wave1/`) built `steno/span/` and `steno/loop/`. Wave 2 added, per `steno-design.md` and `steno-capability.md` build steps B3, B6, B7:

- **B6, compute contracts:** `steno/loop/compute.py` (provider-neutral ComputeRequest, ComputeOffer, ResourceHandle), `steno/loop/backend.py` (ComputeBackend abstract contract), `steno/loop/backends/` (registry; fake, local and vast backends; vast is the only file importing the vastai SDK), preflight credit lookup, a read-only `quote` CLI. Conformance suite `tests/loop/test_backend_contract.py` runs against fake, local and a recorded vast SDK double; a live test is skipped unless an env var is set.
- **B3, enforcement:** `steno/span/enforce.py` (load and verify a deployable bundle, check a request against it), an opt-in `--bundle` gate in `experiments/proxy/tap.py`, an optional bundle check in `experiments/gist/dataset.py`.
- **B7, one journey migrated as a dry run:** `steno/loop/executors/` (STATE-marker parsers and executors wrapping the existing `experiments/vast/conn_chain.sh`), `steno/loop/examples/j11-conn.json`, and a dry run that replays the real J11 STATE file.

Owner requirements: **no hard-coding to any cloud provider** in the runner or spec; **contracts must be explicit and tested**; cost-aware (nothing may create cloud resources unintentionally); the vast.ai API key lives in `~/.vast_api_key` and must never reach code, logs, argv, exceptions or reprs.

Known concern to judge: for J11, the span stage reports `share=0.985` derived from checkpoint composition, not from a span study; the measured static-span share in this program was 0.72. A gate then passes on that number.

Tests: `experiments/.venv/bin/python -m pytest tests -q` (191 pass, 3 skipped).

## Check
1. Provider neutrality: any provider-specific assumption outside `steno/loop/backends/vast.py` (runner, spec, compute, CLI, executors). Is `backend_options` truly opaque? Does the flat wave-1 `compute` form let provider details leak into the neutral layer?
2. Contract completeness and the conformance suite: does every backend actually meet the documented semantics (idempotent provision, unknown never means destroyed, transfer verification, timeouts)? Tests passing for the wrong reason?
3. VastBackend safety: any path that could rent twice (label idempotency, retries), leak the key, run a shell string, or report destroyed without evidence. Unit handling (GB vs MB).
4. B3: can the tap or dataset builder be bypassed or fail open with `--bundle` given? Tampering detection.
5. B7: marker parsing correctness; the J11 share metric concern; anything in the executors that would do remote work in a dry run.
6. Regressions to wave 1 guarantees (fail-closed gates, lifecycle, lock).
7. No em dashes in new code, docs or tests.

## Output
Verdict (at most four sentences), then findings `X-<n>: <line>. Severity: blocking | major | minor. File: <path:line>.` with evidence and a concrete fix. End with exactly `Commit wave 2: yes` or `Commit wave 2: no, because ...`.
