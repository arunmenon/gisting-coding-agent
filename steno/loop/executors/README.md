# steno.loop.executors

Wave 2 of the Steno run loop (steno-design.md build order step B7): migrates one existing
journey, **J11** (`experiments/journeys/j11-conn`, driven today by
`experiments/vast/conn_chain.sh`), onto `steno.loop.runner`'s `stage_executors` seam. **Dry-run
only**: nothing in this package makes a network call, provisions a resource, or runs a remote
command. It is safe to run anywhere, including this machine. Revised after a Codex review
(steno-build-wave2) found gaps in the first draft; see "Fixed after the wave-2 review" below.

## What's here

- `markers.py`: parses a chain script's STATE file text (the `mark()` lines
  `experiments/vast/conn_chain.sh` appends to `/root/STATE`) into typed `Marker` records --
  `chain_start`, `download_attempt`, `ckpt_built`, `server_up`, `b6_result`, `b6_failed`,
  `b6_done`, `bench_done`, `infra_failure` (any `*_FAILED` marker or a `DEADLINE` line, with the
  marker name as `reason`), `verdict_text`, and `unknown` for anything not recognised (never
  dropped). This is intentionally specific to `conn_chain.sh`'s marker vocabulary, read out of
  that script rather than guessed; a different chain script would need its own marker shapes
  added here or in a sibling module.
- `j11.py`: three stage executors --
  - `SpanReportExecutor` (`span`): a genuine no-op. See "Span for a serving-only journey" below.
  - `ServeExecutor` (`serve`): wraps conn_chain.sh's download + checkpoint-build + `start_server`
    sequence. `result_from_markers()` requires exactly one `chain_start` marker and `ckpt_built`
    to precede `server_up` (X-15: accepting them out of order would accept a server never shown
    to be serving the checkpoint it claims), then reports success with `server_up`'s fields
    (`max_model_len`, `max_num_seqs`, `gpu_util`, `max_batched`) as metrics; any `infra_failure`
    marker before `server_up` fails the stage with that marker's text as the detail.
  - `BenchmarkExecutor` (`benchmark`): wraps the B6 sweep. `result_from_markers()` requires
    exactly one `chain_start`, rejects duplicate `(conn, arm, c)` combinations, requires the
    result set to equal exactly the eight expected combinations (`EXPECTED_B6_COMBINATIONS`:
    conn in {100, 512} x arm in {full, gist8} x c in {128, 256}), requires exactly one `B6_done`
    marker positioned after all eight results, and exactly one `BENCH_DONE` positioned after
    `B6_done` (X-15). Only once all of that holds does it turn every `b6_result` marker into a
    `max_running__<conn>_<arm>_<c>` / `rpm__...` / `kv_max__...` / `preempt__...` metric plus an
    aggregate `max_running_max`.
  - Each executor exposes a `.plan` (`StagePlan`): `required_inputs` (local files), the
    `remote_command` it would run (copy-pasted from `conn_chain.sh`, not re-derived, so it cannot
    silently drift), and `expected_artifacts`.
  - `__call__(resource_id, stage_plan)` -- the shape `steno.loop.runner.run`'s `stage_executors`
    dict actually needs to plug into a real backend -- raises `NotImplementedError` on `serve`
    and `benchmark` (no real backend exists yet): wiring these to actually execute is deferred
    until one does. `SpanReportExecutor.__call__` *does* work, since it is genuinely a no-op with
    nothing remote to defer.
- `dryrun.py`: `python -m steno.loop.executors.dryrun steno/loop/examples/j11-conn.json`
  (see below). Evaluates gates through `steno.loop.runner._evaluate_gate` (imported read-only,
  never reimplemented) and exits nonzero on a missing input, a failed stage, or a failed gate.
- `steno/loop/examples/j11-conn.json`: the spec. Stages `["span", "serve", "benchmark"]` --
  the only combination that both matches J11 (no `data`/`train`/`evaluate`) and satisfies
  `steno.loop.spec.RunSpec.validate()`'s requirement that `span` precede any of
  `train/serve/evaluate/benchmark` in the same spec. `compute` uses the neutral
  `{"backend", "request": {...ComputeRequest fields...}, "backend_options": {}}` shape from
  `steno.loop.compute.ComputeRequest` (X-11) -- no provider query vocabulary (no `gpu_query`)
  leaks into the spec; `gpu_count`, `gpu_memory_gb_min`, `gpu_families`, `disk_gb_min` and
  `reliability_min` carry J11's actual H200/reliability/disk constraints so a real backend can
  see and honor them.

## Span for a serving-only journey

J11 has no training data and nothing that would normally produce an "invariance report" the way
`steno.span.cli report` does against captured calls. `steno.loop.spec.STAGES_REQUIRING_SPAN`
still requires a `span` stage in the same spec as `serve`/`benchmark`, and `RunSpec.validate()`
enforces that fail-closed -- deliberately not touched by this wave, since weakening it would let
a *different* journey's spec skip span silently.

Rather than relax that validation, `SpanReportExecutor` is a real stage that reports two
separately named things (X-10 -- the wave-2 review found the first draft's single `share` metric
conflated them, and it passed a `share_min=0.9` gate despite the program's actually-measured
static-span share being 0.72):

- `checkpoint_share`: always computed from `experiments/gist/out_r8v2/segments.json`, the
  identity file for the exact 8:1 gist checkpoint `conn_chain.sh` downloads and serves
  (`rm -rf /root/gist/out && cp -r /root/gist/out_r8v2 /root/gist/out`) -- the fraction of the
  checkpoint's own preamble tokens that are static/compressible. This is checkpoint
  *composition*: how the checkpoint was built, not a measurement of live traffic.
  `gist_ratio`/`gist_token_count` are also reported for context.
  - `share`: the measured static-span share, reported **only** when `span_report_path` (default
  `experiments/journeys/j11-conn/results/span_report.json`, which does not exist today) points
  at a real, passing `steno.span.analysis` report (`schema_version` starting with
  `steno-span-report`, `pass: true`, at least one cohort). Computed as the ratio of
  `fixed_char_count` to `total_char_count` summed across every cohort and part -- the same
  character-count fields `steno.span.analysis._renderable_segment_map` already writes.

**With no such report, `SpanReportExecutor.report()` returns `ok=False` (a `task_failure`),
`checkpoint_share` still in `metrics`, and no `share` key at all.** The spec's `span` gate
therefore targets `checkpoint_share_min` (what is actually evidenced), not `share_min` -- and
because the runner only evaluates a stage's gate once the stage itself succeeds, the span stage
simply fails today, honestly, until a real report exists. See "Known gaps" below for the wave-3
path to producing one.

## Running the dry run

```bash
experiments/.venv/bin/python -m steno.loop.executors.dryrun steno/loop/examples/j11-conn.json
```

This: (1) validates the spec; (2) for each of `span`/`serve`/`benchmark`, checks its
`required_inputs` exist locally and prints the remote command, inputs, expected artifacts, and
gate, warning (without failing) if an input is missing; (3) if
`experiments/journeys/j11-conn/results/STATE` (or a path passed via `--state`) exists, parses it
and runs it through each executor's `result_from_markers()`/`report()`, printing the typed result
and metrics; (4) for each stage that succeeded, evaluates its declared gate via
`steno.loop.runner._evaluate_gate`, and prints PASS/FAIL. Replaying J11's real STATE file today:
`serve` ok (`max_num_seqs=256`), `benchmark` ok with resident-session metrics `max_running__*` of
100 (x4), 123, 126, 128 and 137 and its `max_running_max_min: 100` gate passing, and `span`
**failing** (no provenance report exists yet, so `checkpoint_share_min: 0.5` is never even
evaluated -- matching the runner's own rule that a gate is only checked once its stage succeeds).
The command's exit code is nonzero whenever any stage failed or any evaluated gate failed, so
this replay currently exits 1, honestly reflecting the missing span evidence. Nothing above
executes remotely; `--state` accepts any STATE file, including one from a failed or partial run.

## Tests

```bash
experiments/.venv/bin/python -m pytest tests/executors -q
```

Covers marker parsing (success, a `*_FAILED` marker, and a mixed success/`b6_failed`/`DEADLINE`
partial run), stage-level order/boundary/completeness/duplicate validation (`test_marker_validation.py`:
missing or doubled `chain_start`, out-of-order `ckpt_built`/`server_up`, too few or duplicate B6
combinations, `B6_done`/`BENCH_DONE` ordering), the spec's validity including its neutral compute
shape, the J11 replay reproducing the real recorded benchmark metrics and passing its gate, and
the span stage's fail-closed behavior both with and without a synthetic provenance report.

## Fixed after the wave-2 review (X-4/X-5 are `steno/span/enforce.py`'s, not this package's, but
noted here since they gate the same bundle a real J11 run would eventually use)

- **X-10**: `share` and `checkpoint_share` are no longer the same number under two names; see
  "Span for a serving-only journey" above.
- **X-11**: `compute` migrated from a flat `gpu_query` string (silently ignored by a
  provider-neutral backend) to `steno.loop.compute.ComputeRequest`'s neutral fields.
- **X-15**: `ServeExecutor`/`BenchmarkExecutor` now validate one coherent invocation
  (`chain_start` count), marker order (`ckpt_built` before `server_up`; all eight B6 results
  before `B6_done` before `BENCH_DONE`), the exact expected combination set, and duplicates,
  before ever reporting success.
- **X-16**: `dryrun.py` now evaluates gates via the runner's own `_evaluate_gate` and returns
  nonzero on a missing input, a failed stage, or a failed gate, instead of always exiting 0 once
  a STATE file was found.

## Known gaps for wave 3

- `ServeExecutor`/`BenchmarkExecutor.__call__` are stubs; there is no real backend to execute
  against yet. Wiring these executors into an actual `runner.run()` call against a real box is
  future work, gated on that backend existing.
- No provenance-bearing span report exists for J11 (a serving-only journey with no tap
  captures), so the span stage fails closed by design today. Producing one means either
  capturing J11-shaped traffic through the tap and running `steno.span.cli discover`/`validate`
  against it, or deciding a serving-only journey needs a different kind of span evidence
  entirely; either way, `checkpoint_share` should stay a separate, clearly-labelled metric rather
  than be retired once a real report exists.
- `markers.py`'s marker vocabulary is specific to `conn_chain.sh`; migrating a second journey
  with a differently-shaped chain script will need either new marker patterns added here or a
  per-journey marker module, plus a decision about how much of this parsing generalises.
- `BenchmarkExecutor` still does not distinguish a *partial* B6 sweep (some combinations ok,
  later ones failed) from a total failure in any way beyond "the combination set does not match
  the expected eight"; a caller wanting partial credit would need to inspect the raw markers
  directly.
