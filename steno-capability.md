# Steno capability

Steno is learned prompt compression for agent calls, the technique Shopify calls gisting. It replaces the fixed preamble a coding agent re-sends to the model with a small set of learned tokens, with the base model frozen.

This document tracks Steno as a capability: what its parts are, where they live in this repository, how far each part is from running on a new harness and distilled-model pair, and the open work. Update it whenever an item is closed or a new gap is found.

**Status, as of 2026-09-25:** a single-pair research implementation, built and run for Claude Code with Qwen3.8-27B. It is not yet a reusable capability. The biggest blocker, per the capability review, is that no single pair configuration carries the harness format, model layout, tokenizer, template and artifact identities through the whole suite.

Source review: `experiments/journeys/reviews/steno-capability-20260925/codex-review.md` (Codex gpt-6-astra, medium effort, read-only).

## The five parts

| Part | What it does | Code | Verified for the studied pair | Main coupling to the studied pair |
|---|---|---|---|---|
| 1. Span analysis | Measures what the harness re-sends on every call; separates the fixed part from per-session values that must stay raw | `experiments/analysis/static_span.py`, `experiments/gist/span.py`, `experiments/gist/segments.py`, `experiments/proxy/tap.py` | Partly. Measures the dominant system prefix and tool catalogue, but does not check that every call matches it, and the raw-value rules miss some path and ID shapes | Anthropic Messages request format; Claude session metadata; Qwen model and tokenizer defaults; three code paths serialise the system text differently |
| 2. Trainer | Adds new token rows to the model and trains them by self-distillation, base model frozen | `experiments/gist/train.py`, `dataset.py`, `teacher_cache.py`, `prepare_checkpoint.py`, `export_rows.py`, `memprobe.py` | Yes | Qwen checkpoint shard names and tensor keys; the "243 spare rows" assumption; the served chat template reproduced in code; teacher caches identified by position, not by hash |
| 3. Proxy | Swaps the fixed span for the Steno tokens | `experiments/proxy/tap.py`, `experiments/vast/serve_gist.sh`, `apply_gist_delta.sh`, `experiments/gist/out/chat_template_gist.jinja`, `experiments/gist/mask_gist_logits.py` | Partly. No change to the agent or to the engine's source code, but serving needs the expanded checkpoint and tokenizer, a custom chat template and a vLLM logits processor | Anthropic Messages and streaming format; Claude-to-Qwen effort remapping; one global bundle; catalogue-hash checks can be skipped |
| 4. Evaluation | Task suites scored against the full prompt, plus a serving benchmark | `experiments/driver/`, `experiments/loop/eval_sweep.py`, `experiments/bench/` | Yes, within a narrow scope. Does not establish general quality parity or successful-task throughput | Claude Code launch flags and tool names; fixed ports and paths; hard-suite fixtures not reproducible from a clean clone; failed sessions can still score as passes |
| 5. Auto loop | Provisions a GPU, trains, serves, evaluates, syncs results and tears down, with spend guards | `experiments/loop/`, `experiments/vast/` | Partly. The handoffs exist but are spread across per-journey scripts; there is no single span-first entry point | vast.ai CLI and SSH conventions; journey-specific run scripts and historical instance files; hardcoded artifact names |

## Open work

`P1` blocks running the suite on a second pair. `P2` means the run would work but be fragile or unrepeatable. `P3` is polish. Tick an item and add the closing commit when it is done.

- [ ] P1 · Auto loop · Define one pair/run configuration and a span-first entry point with required-input preflight · experiments/loop/, experiments/analysis/static_span.py, experiments/gist/, experiments/vast/
- [ ] P1 · Span analysis · Add a harness capture adapter and validate system/catalogue variants across every captured request · experiments/proxy/tap.py, experiments/analysis/static_span.py, experiments/gist/span.py, experiments/gist/segments.py
- [ ] P1 · Span analysis · Make verbatim exclusions configurable and verify exact dynamic-value preservation on a varied capture fixture · experiments/gist/segments.py, experiments/gist/dataset.py
- [ ] P1 · Trainer · Discover checkpoint tensor/shard layout and explicitly support or reject tied embeddings, spare-row cases and checkpoint formats · experiments/gist/prepare_checkpoint.py, experiments/gist/export_rows.py, experiments/vast/apply_gist_delta*.sh
- [ ] P1 · Proxy · Configure model parsers, template, token ranges and serving limits; reject missing or incompatible metadata · experiments/proxy/tap.py, experiments/gist/mask_gist_logits.py, experiments/gist/out/chat_template_gist.jinja, experiments/vast/serve*.sh
- [ ] P1 · Proxy · Require catalogue and bundle hashes and replace or migrate all hashless segment maps · experiments/gist/segments.py, experiments/gist/out*/segments.json, experiments/loop/ratios/*/segments.json, experiments/proxy/tap.py
- [ ] P1 · Trainer · Verify request rendering, response-token alignment and HF/vLLM target parity for the new pair · experiments/gist/dataset.py, experiments/gist/teacher_cache.py, experiments/gist/train.py
- [ ] P1 · Trainer · Reject missing session IDs and empty training partitions instead of restoring evaluation examples to training · experiments/gist/train.py
- [ ] P1 · Evaluation · Supply reproducible fixtures, repository pins, dependencies and a harness launch/result adapter · experiments/driver/setup_box.sh, experiments/driver/run_sessions*.sh, experiments/driver/tasks*.txt
- [ ] P1 · Evaluation · Make HTTP/session failures invalidate results and apply one explicit quality gate across all suites · experiments/driver/eval_*.py, experiments/driver/run_sessions_local.sh, experiments/loop/controller.py, experiments/loop/eval_sweep.py
- [ ] P1 · Auto loop · Fix the unset JDIR default and use one allocated tunnel port consistently · experiments/vast/bench_provision.sh, experiments/loop/train_then_hard_eval.sh
- [ ] P1 · Auto loop · Require verified artifact synchronization and confirmed destruction before marking a run complete · experiments/loop/controller.py, experiments/loop/train_then_hard_eval.sh, experiments/vast/idle_watchdog.sh
- [ ] P1 · Auto loop · Persist lifecycle state and enforce deadlines through provisioning, unreachable-host handling, evaluation and teardown · experiments/loop/controller.py, experiments/loop/run*.sh, experiments/vast/bench_provision.sh, experiments/vast/bench_chain.sh
- [ ] P2 · Trainer · Bind caches and rows to model, tokenizer, template, dataset and response hashes; reject incomplete or mismatched caches · experiments/gist/teacher_cache.py, experiments/gist/train.py, experiments/loop/merge_cache.py
- [ ] P2 · Trainer · Save optimizer, RNG, split and data-position state; record length-cap changes as new experimental conditions · experiments/gist/train.py, experiments/vast/chain_sweep.sh
- [ ] P2 · Trainer · Validate dropout behaviour, model accessors and vocabulary bounds; make memory probes model-derived · experiments/gist/train.py, experiments/gist/memprobe.py
- [ ] P2 · Proxy · Require emitted token IDs and failing exit codes for no-emission checks; gate worker readiness on those checks · experiments/vast/gen_test.py, experiments/vast/chain_sweep.sh, experiments/loop/controller.py
- [ ] P2 · Proxy · Record per-segment substitution and add streaming, fallback and template-activation regression checks · experiments/proxy/tap.py, experiments/proxy/smoke.sh, experiments/gist/dataset.py
- [ ] P2 · Evaluation · Replace permissive checks and the defective delete probe; score tool arguments, outcomes and repeated attempts explicitly · experiments/driver/eval_checks.py, experiments/driver/eval_hard.py, experiments/driver/eval_coverage.py, experiments/driver/tasks*.txt
- [ ] P2 · Evaluation · Freeze untouched tasks and add paired repeats, independent expected outputs and an untrained-gist control · experiments/driver/, experiments/loop/eval_sweep.py, experiments/loop/run_coverage.sh
- [ ] P2 · Evaluation · Use paired hashed workloads, controlled cache state, independent arrival seeds, longer windows and a common SLO · experiments/bench/build_corpus.py, experiments/bench/loadgen.py, experiments/bench/analyze.py, experiments/vast/bench_chain.sh
- [ ] P2 · Evaluation · Tune both prompt arms and measure successful live tasks at load on the exact hashed serving checkpoint · experiments/vast/bench_chain.sh, experiments/driver/, experiments/bench/
- [ ] P2 · Auto loop · Pin dependencies, model revisions and images; provide artifact restoration and per-run provenance manifests · README.md, experiments/loop/, experiments/vast/, experiments/gist/
- [ ] P2 · Auto loop · Reconcile lifecycle and billing records, including failed hosts and retraining costs · experiments/ledger.md, experiments/loop/controller.py, experiments/vast/bench_provision.sh
- [ ] P3 · Span analysis · Document the supported span contract and a measured catalogue-change/retraining procedure · README.md, experiments/gist/segments.py, experiments/journeys/
- [ ] P3 · Evaluation · Mark superseded journey claims and reconcile protocol documentation with executable behaviour · experiments/journeys/j3-e3-e2/journey.md, experiments/journeys/j8-coverage/journey.md, experiments/journeys/j10-bench/journey.md, experiments/bench/queue.md

## How to use this list

- The next-pair experiment in the Lattice pitch depends on every P1 item. Do not start it until they are closed or explicitly waived.
- When a review, experiment or run finds a new gap, add it here with a priority and the files it touches.
- Keep the part descriptions in the deck and the note to Srini consistent with the "Verified" column above.
