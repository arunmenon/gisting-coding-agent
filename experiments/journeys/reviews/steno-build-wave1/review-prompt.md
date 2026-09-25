# Code review: Steno build wave 1

Read-only. Emit the review to stdout.

## Context

Steno is learned prompt compression for coding-agent calls (see `steno-design.md`, the spec, and `steno-capability.md`). Wave 1 builds two new packages alongside the untouched research code under `experiments/`:

- `steno/span/`: build steps B1 to B3. Canonical `CallRecord`, a `HarnessAdapter` protocol, a `ClaudeCodeAdapter` ported from `experiments/analysis/static_span.py`, `experiments/gist/segments.py`, `experiments/gist/dataset.py` and `experiments/proxy/tap.py`, a pair manifest with bundle hashes, and a generic all-call invariance report. Tests in `tests/span/` with a sanitised fixture in `tests/span/fixtures/`.
- `steno/loop/`: build step B5. Run spec, persisted lifecycle for stages and rented resources, compute backend protocol with a `FakeBackend` test double, a runner, a JSONL ledger, and a CLI. Tests in `tests/loop/`.

The tests pass: run `experiments/.venv/bin/python -m pytest tests -q` if your sandbox allows it.

The builders reported these deliberate choices. Judge each one:

1. Span: canonical system-text serialisation follows `dataset.py` (empty-string join, inline system messages folded in).
2. Span: missing session ID stays `None`; the heuristic fallback in `static_span.py` was not ported.
3. Span: invariance classification is line-granular, not character-range-granular.
4. Span: run against a real 43-call Claude Code capture, the report gives 6 cohorts, 15 unresolved ranges, overall fail.
5. Loop: `completed` means only sync verified and destroy confirmed; a run whose span stage failed can still be `completed`, with the failure carried in `abort_reason`.
6. Loop: preflight credit check is a placeholder; `gates` are parsed but not evaluated; `max_attempts_per_stage` is validated but unused; the vast backend is a stub.

## What to check

1. **Correctness bugs** in both packages, with a concrete failing input where possible.
2. **Fidelity to `steno-design.md`**: missing contract methods, wrong semantics, anything that would have to be redone later.
3. **The rewrite round trip**: does `rewrite_request(raw, parse_request(raw).preamble)` truly reproduce any valid request, or only the fixture?
4. **The invariance report**: can it pass something it should fail, or fail something it should pass? Is the 6-cohort, 15-unresolved result on real data plausible or a bug?
5. **Lifecycle safety**: any path where a rented resource could be lost track of, double-provisioned, or marked done without confirmed teardown. Is choice 5 safe, or should outcome and cleanup be separate fields?
6. **Tests**: important untested paths; tests that pass for the wrong reason.
7. **Fixture safety**: anything sensitive in `tests/span/fixtures/`.
8. No em dashes in code, docs or messages.

## Output

A verdict of at most four sentences: can this be committed as wave 1, and what must change first.

Then findings: `W-<n>: <one line>. Severity: blocking | major | minor. File: <path:line>.` followed by the evidence and a concrete fix.

End with a short list of what wave 2 should pick up. No praise.
