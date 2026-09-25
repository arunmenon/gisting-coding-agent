Steno is a single-pair research implementation, not yet a reusable five-part capability. The repository implements span extraction, embedding-only training, substitution, task scoring and portions of unattended execution, but connects them through Qwen-specific assumptions and historical experiment state. The biggest blocker is the absence of a validated pair configuration that carries the harness format, model layout, tokenizer, template and artifact identities through the whole suite. Evaluation and teardown defects also remain open, so replacing model names would not produce a trustworthy second run.

Review performed read-only from the repository root. All 25 inspected Python sources parsed and all 38 shell scripts passed `bash -n`; these checks do not establish runtime compatibility. Targeted in-memory checks reproduced the split leakage and incomplete verbatim matching described below. “September 8” and “September 15” refer to the two requested reviews; their reconciliation was checked against current source.

## 1. Span analysis

**Verified: partly.** [`static_span.py::main()`](/Users/arunmenon/projects/gisting/experiments/analysis/static_span.py:76) measures a common system prefix and dominant catalogue, while [`segments.py::dynamic_spans()`](/Users/arunmenon/projects/gisting/experiments/gist/segments.py:48) separates observed differences and selected verbatim patterns, but neither establishes that everything classified static is invariant across every call.

**Coupling:**

- `analysis/static_span.py::load_records()`, `system_text()`, `tools_json()` and `session_key()` assume Anthropic Messages requests, `system` text blocks, `tools`, Anthropic usage fields and Claude’s JSON-encoded `metadata.user_id.session_id`. Another harness requires explicit request, usage and session extraction.
- `static_span.py::main()` defaults to `Qwen/Qwen3.8-27B`, served name `qwen3.8-27b` and `experiments/logs/requests.jsonl`. Its exact-count mode uses vLLM `/tokenize` after converting Anthropic schemas into OpenAI functions. Those defaults and the counting adapter must change with the pair.
- [`gist/span.py`](/Users/arunmenon/projects/gisting/experiments/gist/span.py:13) fixes `MODEL`; `load_dominant_request()` assumes a list of system blocks and retains the first system text associated with the dominant tools array. `render_prefix_ids()` searches for the literal `"<|im_start|>user"`. A different template needs its own validated prefix-boundary extraction.
- `segments.py::all_system_texts()` uses Claude session metadata and keeps only the first qualifying system text per session. `main()` takes the catalogue from the first input log. A new capture adapter must preserve all relevant variants and identify catalogue cohorts.
- `segments.py::VERBATIM_LINE` recognizes `working directory`, `/private/`, `/Users/`, `/home/`, UUIDs, ISO dates and `powered by the model`. The verbatim policy must be supplied and tested for the new captured format.
- `segments.py::main()` assumes rendering tools creates exactly one insertion, encodes segments independently, registers contiguous `<gist_N>` tokens and writes `"embedding_rows": 248320`. It exposes ratios and minimum segment length through environment variables, but model selection and embedding metadata remain fixed.
- Capture depends on `proxy/tap.py::TapHandler.forward()` and `stub.py::H.do_POST()`, which understand Messages API payloads. The tap also remaps reasoning effort before logging, so its capture is already specific to the studied serving path.

**Gaps:**

- **The measurement is not an all-call invariant.** `static_span.py` selects the most frequent tools array even when others exist, then uses that span size across sessions. `segments.py` does not validate every request against the selected catalogue or retain within-session system changes.
- **Dynamic-value protection remains incomplete.** The current regex does not match isolated `/opt/app/config.toml`, `/root/project`, Windows paths or `customer-123`; the read-only check reproduced this. September 8 F-2-3 and September 15 F-9-1 remain open.
- **The extraction paths disagree about serialization.** `static_span.py::system_text()` joins blocks with newlines; `span.py` concatenates without separators; `dataset.py` additionally merges inline system messages. There is no shared rendering contract or token-level comparison against actual server inputs.
- **Generated metadata and shipped metadata differ.** Current `segments.py` writes `tools_hash`, but all 17 inspected maps under `gist/out*` and `loop/ratios/*` lack it. Existing maps therefore do not activate the proxy’s catalogue guard.
- There is no single capture-to-span command, minimum diversity requirement, catalogue-change report or validation suite for insertion/deletion boundaries, repeated anchors and exact preservation of dynamic values.
- Captures and tokenizer directories exist as ignored local files, but a clean clone does not contain them. README names private artifact repositories without an executable, revision-pinned restoration procedure. September 8 F-5-1 through F-5-3 remain relevant.
- The earlier request to measure behaviour and retraining cost across actual harness/catalogue changes remains unimplemented. Existing journey narratives are not a substitute for that experiment.

## 2. Trainer

**Verified: yes.** [`prepare_checkpoint.py::main()`](/Users/arunmenon/projects/gisting/experiments/gist/prepare_checkpoint.py:41) initializes added input rows from span embeddings, and [`train.py::main()`](/Users/arunmenon/projects/gisting/experiments/gist/train.py:82) freezes model parameters with `requires_grad_(False)` and optimizes only `gist_rows` using self-distillation.

**Coupling:**

- `prepare_checkpoint.py:25` fixes the model repository, two shard filenames, `model.language_model.embed_tokens.weight`, `lm_head.weight` and padding to 128 rows. `export_rows.py` repeats the embedding shard and tensor key. A different model requires layout discovery and support for its actual checkpoint organization.
- `prepare_checkpoint.py::main()` asserts that gist tokens exceed existing embedding capacity, explicitly citing the “243-spare-rows finding.” Its final assertion also expects spare rows to have been overwritten. Models needing no resize, or having no spare rows, are not accommodated.
- [`dataset.py::system_text_as_served()` and `anthropic_to_openai_messages()`](/Users/arunmenon/projects/gisting/experiments/gist/dataset.py:31) reproduce the studied vLLM Anthropic adapter, including billing-header removal, reasoning blocks and tool-result ordering. Other request formats need another conversion path.
- `dataset.py::build_example()` manually places the tools gist before system text, assumes the completed assistant render extends the generation prompt, and requires Claude session metadata. `GIST_OUT` selects a directory containing specifically named `segments.json` and `tokenizer/` artifacts.
- `teacher_cache.py::query()` fixes `http://127.0.0.1:8000`, model name `qwen3.8-27b-gist`, `/v1/completions` and vLLM `prompt_logprobs`. The endpoint, model identity and probability-export interface need configuration.
- `train.py::response_logits()` directly calls `model.model` or `model.base_model`, expects `last_hidden_state`, then invokes `model.lm_head`. `main()` expects standard input embeddings and loads the entire model onto one device.
- `train.py:156` calls `model.train()` with the comment “the model has no dropout, so outputs are unchanged.” That property is assumed rather than checked. `--tiny-test` constructs only a Qwen3 model.
- `GistInjector.hook()` treats **every** input ID at or above `first_gist_id` as a gist-row index. This requires a contiguous terminal gist range without other added tokens.
- `memprobe.py` fixes CUDA, bf16, four sequence lengths and random IDs below 200,000. For another vocabulary or memory target, the probe itself must change.
- Training launchers in `vast/chain_train.sh`, `chain_j3b.sh`, `chain_sweep.sh` and `loop/run_coverage.sh` repeat `/root/qwen3.8-27b-gist`, historical data/cache paths and studied sequence caps.

**Gaps:**

- **Distilled-model readiness is unverified.** The trainer and preparation code derive embedding width from the loaded tensors, so 5,120 dimensions and 27B parameters are not intrinsic requirements of the optimization. However, preparation/export assume separate, untied dense embedding and output-head tensors in two particular shards. Tied embeddings, a shared shard, another tensor naming scheme or a quantized checkpoint have no compatibility path or rejection check.
- **Session splitting can leak completely.** `train.py:172` contains `train_set = [...] or examples`. With one session, or missing session IDs, the reproduced result was 20 training examples, 20 evaluation examples and 20 overlapping examples. The September 8 reconciliation’s closure is therefore incomplete, as September 15 F-9-1 already noted.
- **Cache identity is positional.** `teacher_cache.py`, `train.py` and `loop/merge_cache.py` associate targets with integer dataset indices. They do not verify dataset, response, tokenizer, model or template hashes; merging does not validate matching K or target provenance. September 8 F-2-5 and September 15 F-6-3 remain open.
- **Training/serving parity is unproven.** `dataset.py` does not propagate request reasoning effort into template rendering, reconstructs responses from parsed blocks and tokenizes prompt and response separately. There is no exact emitted-token comparison or HF-versus-vLLM logit parity check. `parity_probe.py` compares generated tool calls, not those interfaces.
- **The cached objective has an unresolved approximation.** `kl_per_token_cached()` implements a renormalized top-K teacher against the full student distribution. No matched full-distribution audit is supplied. `teacher_cache.py` still labels availability of the actual token’s returned probability as membership inside top-K, although those are different checks.
- **Partial datasets can silently become training inputs.** `dataset.py::main()` catches all example-building exceptions and continues; `teacher_cache.py` logs failed requests and saves the remaining cache. Neither enforces an expected coverage threshold or writes a complete exclusion manifest.
- **Recovery is warm starting, not exact resumption.** Only rows are saved. Adam state, RNG state, split assignment and data position are omitted. `chain_sweep.sh` shortens the length cap after OOM and estimates progress from printed steps, which can be later than the last saved rows. September 8 F-2-7 remains open.
- A seed exists, but split IDs, effective epoch coverage and dependency/model revisions are not captured in a complete run manifest. Cached-mode step count is calculated before the whole-session split, using `eval_n` rather than the resulting evaluation-set size.
- No compatibility tests verify unchanged real-token weights, tied-weight behaviour, bounded gist IDs, export/reload equivalence or dropout handling across model layouts. The same selected model supplies the teacher; there is no separate original-teacher configuration for a distilled model.

## 3. Proxy

**Verified: partly.** [`tap.py::TapHandler.forward()`](/Users/arunmenon/projects/gisting/experiments/proxy/tap.py:140) substitutes gist strings and preserves the tools array, but deployment also requires an expanded checkpoint/tokenizer, a custom chat template and a vLLM logits processor, so “unchanged engine” means no engine-source patch.

**Coupling:**

- `TapHandler.forward()`, `parse_sse_events()` and `summarize_stream()` assume Anthropic Messages requests and SSE events. The substitution path applies to top-level `system` plus `tools`; another harness needs a validated protocol adapter.
- `EFFORT_REMAP` and `forward()` rewrite Claude `high`/`max` effort to Qwen `medium`/`xhigh`, with other unsupported values becoming `medium`. This policy must become pair configuration.
- `load_gist()` and `gist_system_text()` depend on `system_*`, `tools`, literal anchor strings and `<gist_N>` naming. The proxy has one global bundle, rather than bundle selection by request/model/catalogue identity.
- [`chat_template_gist.jinja:57`](/Users/arunmenon/projects/gisting/experiments/gist/out/chat_template_gist.jinja:57) detects `'<gist_'` in the system text and skips tool rendering. The rest of the file embeds Qwen role delimiters, thinking syntax and XML-style tool calls. A new model needs a corresponding template modification and parity verification.
- `vast/serve.sh`, `serve_gist.sh` and `serve_bench.sh` use vLLM, `--language-model-only`, `--reasoning-parser qwen3` and `--tool-call-parser qwen3_coder`. Context limits, memory utilization and sequence/batch caps are studied settings, even where environment overrides exist.
- `serve_gist.sh`, `serve_ratio.sh`, `apply_gist_delta.sh` and `apply_gist_delta_bench.sh` repeat Qwen checkpoint paths and shard keys. `serve_ratio.sh` rebuilds from `/root/ratios/<run>` and shared `/root/gist/out` and `/root/delta` directories.
- [`mask_gist_logits.py`](/Users/arunmenon/projects/gisting/experiments/gist/mask_gist_logits.py:13) imports vLLM’s logits-processor interface, defaults to ID `248077` if metadata is unavailable, and masks every ID from that boundary onward.
- `proxy/smoke.sh`, `vast/gen_test.py` and `parity_probe.py` fix Qwen served names and localhost ports; the latter two fix `/root` artifact locations. `gen_test.py` additionally assumes a 398-token student probe.

**Gaps:**

- **Catalogue validation is bypassed by every inspected bundled map.** `load_gist()` accepts absent hashes and both checks in `forward()` are conditional. Require a complete bundle identity before substitution, rather than silently accepting legacy maps.
- **Partial substitution is underreported.** `gist_system_text()` succeeds when any system anchor matches. `gist_applied=True` does not mean every intended segment was swapped. There is no per-segment coverage report or explicit bundle compatibility decision.
- **Training and proxy substitution differ.** `dataset.py::gist_prefix_text()` requires every anchor with `.index()`; the proxy skips missing anchors. The deployed partial-substitution distribution is not represented by that builder.
- **Template activation is an unchecked substring test.** Literal `<gist_` text can suppress tool rendering without proving that valid registered gist tokens were inserted. The proxy, tokenizer and serving template need a shared, tested activation contract.
- **Distilled-model vocabulary handling is unsafe without validation.** The mask’s fallback boundary can be wrong for another vocabulary, and its blanket suffix mask assumes no legitimate tokens follow the gist boundary. Missing or inconsistent metadata should stop startup.
- **The no-emission gate is not a gate.** `gen_test.py` requests emitted IDs but silently falls back to retokenizing text; a printed `FAIL` does not produce a failing exit status. The output-head zeroing fix is present, but the mask remains the actual exclusion mechanism. September 8 F-2-4 and September 15 F-9-1 are only partly closed.
- `smoke.sh` prints responses/event counts without asserting tool-schema preservation, exact dynamic text, full-prompt fallback, token reduction or streaming equivalence. No automated server-tokenization parity suite is supplied.
- `forward()` catches connection setup failures, but streaming reads, client writes and final logging lack encompassing cleanup/error recording. Disconnects can leave requests without complete evidence; there is no tested bounded logging/backpressure policy.
- Catalogue-change fallback and retraining have no measured lifecycle. The current proxy does not verify that its map matches the actually served rows, tokenizer or template.

## 4. Evaluation

**Verified: yes, within a narrow scope.** [`eval_sweep.py`](/Users/arunmenon/projects/gisting/experiments/loop/eval_sweep.py:30) runs gist and full-prompt task arms through the checkers, and [`loadgen.py::closed_loop()` / `open_loop()`](/Users/arunmenon/projects/gisting/experiments/bench/loadgen.py:94) implement serving replay; these do not establish general quality parity or successful-task throughput.

**Coupling:**

- `driver/run_sessions.sh` invokes a particular `~/.local/bin/claude`, Anthropic environment variables, the Qwen served name, fixed ports and a generated calculator repository.
- `run_sessions_local.sh::run_one()` invokes `claude -p` with Claude-specific permission, tool and MCP flags. Its `ALLOWED` list names Claude tools and Bash command patterns. Another harness requires its own launch and result adapter.
- `run_sessions_local.sh` sources ignored `experiments/claude-env.sh` and defaults to a UUID-bearing `/private/tmp/claude-501/.../scratchpad`, pre-existing `repos/` and `sessionvenv/`. `setup_box.sh` installs Claude Code 2.1.259 under user `cc`; it does not build the complete local hard-suite environment.
- `tasks*.txt`, `eval_checks.py` and `eval_hard.py::check()` bind task order to calculator, `seedadv`, Requests, Click and Typer files and function names. Tool probes name `Glob`, `Grep`, `TaskCreate`, `Agent` and other Claude tools. New suites must update fixtures and checkers together.
- `eval_hard.py::session_calls()` assumes Claude metadata and Anthropic `tool_use` responses. `match()` identifies tasks by their first 80 text characters. `analysis/coverage.py` uses the same response format and the last successful request’s catalogue.
- `loop/controller.py::run_eval()` fixes `tasks_eval.txt`, concurrency four and Qwen normalization. `gate.json` embeds a historical teacher result of 12/12. `eval_sweep.py` assumes `/root/ratios`, Qwen health responses and the local scratch layout.
- `bench/build_corpus.py` requires paired tokenized datasets but names arms `full`, `gist8`, `gist16`, `full16`, independently selects sessions for two datasets and fixes a 36,000-token prompt cap.
- `bench/loadgen.py` uses vLLM completions, `ignore_eos`, fixed output lengths and vLLM metric names. `analyze.py` defaults to tag `B1`, hard-codes arm pairings and uses multiples of each arm’s own unloaded latency.
- `vast/bench_chain.sh` fixes historical r8v2/r16 artifacts, a serving-tuning grid, workload ladders and short durations. `conn_chain.sh` encodes the J11 connection-cap study. `bench_latency.py` fixes Qwen, 12 sessions, six turns, 200 output tokens and concurrency 1/4/8.

**Gaps:**

- **A clean clone cannot construct the hard-suite environment.** The driver creates `seed`, but no inspected setup constructs `seedadv`, pins the external repositories or installs their complete task dependencies. Client skills, hooks, memory and peer-agent state are also not captured.
- **Infrastructure failures can receive passing task scores.** `session_calls()` drops non-200 requests; coverage can pass from an earlier tool occurrence despite a later failed session. Drivers print exit codes without reliably failing the entire run. This is the September 8 J8 contamination mechanism, still present.
- **Checkers remain permissive.** Easy explanation/reporting tasks do not score the explanation/report. Hard checks accept document length, existing references, some agent-written tests and a read-before-edit predicate that misses Bash edits. Task 7 still rewards preserving a file explicitly requested for deletion.
- **Coverage is occurrence, not correctness.** `eval_coverage.py` checks tool names without schema validation, successful execution or task completion. `match()` overwrites repeated task matches, so multiple passes can collapse into the last matching session.
- **Quality gates are inconsistent.** The easy controller checks names and parsed JSON, not complete schemas; hard and coverage sweeps do not apply that gate. Generation-test success is excluded. Child sessions and partial substitutions are not separately enforced or fully attributed.
- **Untouched evaluation remains missing.** `run_coverage.sh` collects training examples and evaluates using the same coverage task file. Easy tasks overlap collection tasks; the hard suite guided the span repair. There is no fixed independent split, repeated paired quality protocol or trained-versus-untrained gist control. September 8 F-2-2, F-3-* and F-8-1/F-8-2 remain open.
- **Serving replay still has unresolved measurement defects.** `loadgen.py` restarts at corpus entry zero; repeats reuse the default arrival seed; throughput selects successful requests by start time while counters include warm-up and drain. Synchronous metrics requests block its event loop. `bench_chain.sh` tunes only the gist arm, lacks equivalent cache reset, and does not establish steady state. September 15 F-1-* and F-2-* remain open.
- **Analysis does not enforce a common service requirement.** `analyze.py` uses arm-relative thresholds, reports selected peaks and groups runs without validating checkpoint/configuration identity or excluding errorful runs. No independent confirmation block or uncertainty around the selected capacity is provided.
- **The connection-limit defect is fixed in current code.** `make_session()` explicitly sets limits and records them. J11 and its remediation withdraw the 100-request hardware-ceiling interpretation; they do not close the remaining benchmark findings.
- **Quality at load remains unmeasured.** Replay bypasses the agent and tools, does not retain generated content for scoring, and counts requests rather than correctly completed tasks. Historical task scores are not cryptographically linked to the served benchmark checkpoint.
- Journey records retain superseded claims, including J3’s gate language, J8’s capacity conclusion and J10’s residency explanation. A new operator cannot treat those narratives as the current executable protocol.

## 5. Auto loop

**Verified: partly.** [`controller.py::run_eval()` and `finish()`](/Users/arunmenon/projects/gisting/experiments/loop/controller.py:51), the worker chains and provisioning scripts implement individual handoffs, but no entry point performs the complete span-first suite with enforced artifact preservation and spend limits.

**Coupling:**

- `loop/provision.sh` takes an already-created instance, host and port; its defaults select J4 datasets and the J3 teacher cache. `provision_eval.sh` ships exactly r2/r4/r8/r16 and writes `evalbox.json`.
- `controller.py` uses Vast CLI from `experiments/.venv`, root SSH, `/root/STATE`, fixed remote filenames, Qwen health/normalization and journey-specific result directories. `boxes.json` and `evalbox*.json` contain historical instance endpoints.
- `run_r8v2.sh` reads `/tmp/r8v2_iid.txt`. `run_latency.sh`, `run_e5.sh`, `run_coverage.sh`, `run_covexam_baseline.sh`, `run_seg.sh` and `run_j9_reeval.sh` embed J5–J9 artifacts, labels and temporary filenames. These must be replaced by explicit run inputs.
- Those rental scripts repeat Vast offer filters for one GPU, at least 90 GB, CUDA/network/disk thresholds, fixed price ceilings, historical rejected offer IDs and exclusion of Spain. Ledger text labels the selected hardware RTX PRO 6000 regardless of the broader filter.
- `vast/bench_provision.sh` uses the Vast SDK/CLI, H100 NVL defaults, a vLLM image tag, J10 labels and r8v2/r16 artifacts. GPU query, image and several limits are configurable, but these settings are not shared with the training provisioners.
- `vast/rsh.sh` resolves Vast direct/proxy endpoints. Credential paths differ between `~/.vast_api_key`, `~/.config/vastai/vast_api_key`, per-instance key files and `/root/.vast_key`. Another provider requires provisioning, endpoint, billing and destruction adapters.
- `bootstrap_j2.sh`, `bootstrap_j5.sh`, `chain_j3a.sh`, `chain_j3b.sh`, `chain_train.sh`, `chain_sweep.sh`, `download.sh` and `launch_j3b_when_cached.sh` hard-code Qwen downloads and `/root` staging. The chain scripts install unpinned packages, including `flash-linear-attention`.
- `supervise.sh`, `supervise_gist.sh`, `supervise_bench.sh` and `chain_mask_then_base.sh` depend on shared process-name matching, `/root/STOP` and fixed serving scripts. `idle_watchdog.sh` samples the first GPU via `nvidia-smi` and calls Vast’s destruction endpoint.
- `bench_chain.sh`, `conn_chain.sh` and `journeys/j11-conn/watch.sh` use benchmark-specific state/results locations. `bench_provision.sh` also uses macOS `sed -i ''`; remote scripts expect Linux utilities.

**Gaps:**

- **There is no complete suite entry point.** The controller does not provision or derive spans; training provisioning assumes prepared maps/data/cache; benchmark provisioning assumes trained rows and corpora. Recipes are spread across scripts rather than represented as one validated run specification.
- **The advertised default benchmark invocation fails.** [`bench_provision.sh:11`](/Users/arunmenon/projects/gisting/experiments/vast/bench_provision.sh:11) sets `JDIR="${JDIR:-$JDIR}"` under `set -u`. With `JDIR` unset, the reproduced result is `JDIR: unbound variable`.
- **The coverage tunnel is miswired.** [`train_then_hard_eval.sh:20`](/Users/arunmenon/projects/gisting/experiments/loop/train_then_hard_eval.sh:20) opens a random port from 8600–8899, but the proxy upstream remains 8500. `run_seg.sh` enables this path through `COVEXAM=1`.
- **Sync-before-destroy is not enforced.** `controller.py::finish()` ignores `scp_down()` failure and proceeds to destruction. `train_then_hard_eval.sh` also ignores its final copy result. No checksum-verified required-artifact manifest gates teardown.
- **Destruction failure can become completed state.** `finish()` sets `box["done"] = True` even if `destroy()` fails. The watchdog sends one unchecked DELETE and exits. Neither supplies reliable confirmation and retry persistence.
- **Restart safety is incomplete.** The controller’s `done` set and deadline start are process-local; it does not reconstruct completion from its ledger. A Vast API parse failure can still be classified as disappearance. The earlier repeated-vanished polling bug is fixed, but September 15 F-9-1’s broader concerns remain.
- **Failure propagation is incomplete.** `chain_sweep.sh` marks `READY_FOR_EVAL` after `gen_test.py` without requiring success. Controller/evaluation subprocess timeouts lack encompassing cleanup; SSH helpers can return stdout from unsuccessful remote commands. Historical STATE text is not a typed terminal-state contract.
- **Spend guards do not bound the whole workflow.** Older provisioning/readiness loops are unbounded; several failure exits occur before watchdog installation. The controller skips its deadline check while handling unreachable hosts. Benchmark deadlines are checked between blocks, and GPU activity can indefinitely reset the idle watchdog.
- **The benchmark path does not complete teardown itself.** Normal `bench_provision.sh` returns after launch; `bench_chain.sh` stops serving and marks completion; `j11-conn/watch.sh` copies results but does not destroy. The separate idle watchdog is not coordinated with successful synchronization.
- **Reproducibility is incomplete.** Image tags and one Claude installer version are present, but model downloads lack enforced revisions, packages are upgraded without locks, and no complete source/configuration/artifact manifest accompanies each run. Local rows, caches and corpora cannot be assumed on another workstation.
- **Accounting remains historical text editing.** `ledger.md` still has a J9 row marked live with blank cost despite the top-level statement of no program instances. Current scripts do not reconcile instance lifecycle, billing and result status into an authoritative ledger. September 8 F-6-1 and September 15 F-5-3 remain relevant.

## Consolidated TODO

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
