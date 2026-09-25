<!-- Fable (claude-fable-5-1) design opinion, read-only, 2026-09-25. Verbatim final report. -->

# Design opinion: harness-agnostic span analysis and one auto loop

## Question 1: harness-agnostic span analysis

### Recommendation

Split the pipeline at one seam: a `HarnessAdapter` turns raw captured traffic into a canonical `CallRecord`; a `ModelAdapter` turns canonical calls into rendered token ids. Everything between those two (span discovery, classification, invariance check, segment map, hashes, reports) becomes generic code that never sees a wire format. Today the seam does not exist: `static_span.py::system_text()` joins system blocks with `"\n"`, `span.py::load_dominant_request()` joins with `""`, and `dataset.py::system_text_as_served()` also folds inline `role=system` messages and strips billing headers. The canonical record must carry one serialisation, produced once, by the adapter, and asserted equal to what the engine actually rendered.

### Adapter contract

```python
@dataclass
class CallRecord:                      # one model call, wire format erased
    call_id: str
    session_id: str | None             # None is allowed; the generic layer refuses to build a session split on None
    turn_index: int
    ts: float
    preamble: list[Part]               # ordered, each Part = {kind: "system"|"tools"|"other", text: str, source: str}
    tool_catalogue: list[ToolSpec]     # canonical {name, description, schema}; hash computed generically
    messages: list[Msg]                # canonical roles: system|user|assistant|tool, plus tool_calls/tool_results
    response: Reply | None             # text, reasoning, tool_calls, stop_reason
    usage: Usage | None                # input_tokens as the engine reported them, or None
    timing: {ttfb_s, ttft_s, latency_s}
    raw_ref: str                       # pointer back to the raw capture line for audits

class HarnessAdapter(Protocol):
    name: str
    def wants(self, raw: dict) -> bool                     # replaces the "/v1/messages" and not count_tokens filter
    def parse_request(self, raw: dict) -> CallRecord
    def parse_response(self, raw_bytes: bytes, streamed: bool) -> Reply   # replaces parse_sse_events + summarize_stream
    def first_token_marker(self) -> bytes                  # what the tap scans a chunk for to stamp ttft (today b"content_block_delta")
    def rewrite_request(self, raw: dict, new_preamble: list[Part]) -> dict   # inverse of parse_request; used by the proxy in swap mode
    def per_session_rules(self) -> list[ValueRule]         # declared patterns: {name, regex_or_extractor, must_preserve: bool}
    def launch(self, task: Task, endpoint: str, model_name: str, workdir: Path) -> LaunchResult   # replaces run_sessions_local.sh::run_one
    def normalize_for_anchoring(self, text: str) -> str    # replaces tap.py --normalize old=new
```

Notes on each method against current code:

- `parse_request` absorbs `session_key()` (Claude puts a JSON string in `metadata.user_id`), the `system` block join and `tools` extraction. Session fallback to "first user text" must move out of the adapter and become an explicit generic option, flagged in the report.
- `parse_response` absorbs Anthropic SSE reassembly, including `input_json_valid`.
- `rewrite_request` is what the proxy needs; today `tap.py::forward()` hand-builds `[{"type":"text","text":gisted}]` and relies on the template's `'<gist_' in system` substring test (`chat_template_gist.jinja:59`).
- `per_session_rules` replaces `segments.py::VERBATIM_LINE`, which is one regex for cwd, a few path prefixes, UUIDs, dates and "powered by the model". Rules become data the adapter ships and the generic layer tests.
- `launch` wraps `claude -p ... --allowedTools ... --strict-mcp-config --max-turns` and the `ANTHROPIC_BASE_URL`/`ANTHROPIC_MODEL` environment. The return value is a typed exit (ok, timeout, http_failure) so `eval_hard.py` stops dropping non-200 sessions silently.
- Effort remapping (`EFFORT_REMAP` in tap.py) belongs in pair configuration, applied by `rewrite_request`, never at capture time; today it mutates the request before logging.

### What stays generic

- Capture: the tap becomes a wire-agnostic byte relay that calls `adapter.parse_*` and writes `CallRecord` plus raw. Timing stays generic.
- Span discovery: `common_prefix` and difflib across sessions (`segments.py::dynamic_spans`) run over `preamble` text.
- Classification: fixed vs per-session from (a) diff across sessions, (b) declared `ValueRule`s, (c) `MIN_STATIC_TOKENS` folding. All three already exist; they just read canonical fields.
- Invariance check (new, generic): for every call, assert the preamble equals `fixed_segments + observed dynamic values` and the catalogue hash equals the selected one. Emit a per-call pass/fail table. Today `static_span.py` picks `most_common` tools and never checks the rest.
- Token counting: via `ModelAdapter` only.
- Segment map and bundle identity: `segments.json` gains `harness`, `harness_adapter_version`, `model_id`, `tokenizer_sha`, `template_sha`, `catalogue_sha` (already `tools_hash` in new maps, absent in all shipped ones), `rules_sha`, `bundle_sha` over all of the above. The proxy refuses a bundle missing any field; the conditional checks in `tap.py::forward()` go away.
- Reporting: the E0 share table and gate (`>= 0.25`) unchanged.

### The model side

Yes, a second adapter, because `span.py::render_prefix_ids` searches for the literal `<|im_start|>user`, `segments.py` asserts the template inserts the tools block in exactly one place, `dataset.py::build_example` hand-orders `tools_gist + system` to mimic Qwen's template, and `segments.py` hardcodes `embedding_rows: 248320`.

```python
class ModelAdapter(Protocol):
    model_id: str; revision: str
    def tokenizer(self) -> Tokenizer
    def render(self, preamble: list[Part], messages: list[Msg], tools: list[ToolSpec], gen_prompt: bool) -> str
    def prefix_boundary(self, rendered: str) -> int        # where the first non-preamble turn begins; replaces the "<|im_start|>user" search
    def tools_block(self, preamble, tools) -> (text, position)  # replaces the with/without-tools difflib trick
    def register_gist_tokens(self, n: int) -> GistRange     # asserts contiguous ids at end of vocab, returns first_id and vocab facts
    def swap_template(self) -> Path                         # gist-mode chat template; activation contract defined here, not by substring
    def engine_count(self, endpoint, rendered) -> int       # /tokenize parity check
```

Trainer-facing model facts (shard names, tied embeddings, spare rows) belong in the same adapter but are out of scope here.

### Onboarding a new harness

1. Capture 3 or more sessions of 5 or more turns on the new harness through the passthrough tap, plus one deliberately different cwd and one different catalogue.
2. Write the adapter (`wants`, `parse_request`, `parse_response`, `rewrite_request`, `launch`, rules).
3. Commit fixtures: 20 raw capture lines plus their expected `CallRecord` JSON (golden parse). Generic test: parse, rewrite with identity preamble, and assert byte-equal request.
4. Run the invariance report on the capture. Required: 100 percent of calls match the fixed span plus dynamic values; catalogue cohorts listed; every declared `ValueRule` fires at least once and every diff-detected dynamic range is covered by a rule or explicitly accepted.
5. Rendering parity: for 20 calls, `ModelAdapter.render` token ids equal the engine's `/tokenize` count (the `--vllm` path in `static_span.py`, made mandatory).
6. Round trip: proxy swap then reverse swap reproduces the original request. Only then does the adapter get a version tag that segment maps record.

### Risks

- Preamble shape leaks: a harness that has no single system field, or that carries tool schemas inside messages, will strain `list[Part]`. Keep `Part.kind` open and let the generic layer treat any Part as a candidate span; do not add harness knowledge to the generic code.
- Session identity leaks: adapters will be tempted to guess. Require `session_id` to be either extracted or `None`; the generic layer refuses to split train/eval on `None` (which also closes the `train_set = [...] or examples` leak once trainer work starts).
- Rules drift: the value rules will keep missing shapes (`/opt/app/config.toml`, `customer-123` per the review). The invariance report, not the regex, is the safety net: anything that differs across sessions and is not covered by a rule fails the run.
- Template coupling: the gist-mode activation must be a registered-token check in the model adapter, not `'<gist_' in text`.
- Keep adapters thin by forbidding them from importing tokenizer or segment code, and by testing them only with the golden fixtures.

### Next steps, ordered

1. Define `CallRecord` and write `ClaudeCodeAdapter` by moving existing functions (no behaviour change); make all three scripts read through it.
2. Add the per-call invariance report and make it the first stage; fail on any mismatch.
3. Make bundle identity mandatory in `segments.json` and the proxy; regenerate the 17 hashless maps or mark them legacy.
4. Extract `ModelAdapter` for Qwen from `span.py`, `segments.py`, `dataset.py`; remove the `<|im_start|>` literal and `embedding_rows` constant.
5. Golden fixtures and round-trip test for the Claude Code adapter.
6. Move `launch` out of `run_sessions_local.sh` into the adapter with typed exits.

## Question 2: the auto loop

### Recommendation

Replace the per-journey scripts with one entry point, `steno run <spec.yaml>`, driven by a persisted state machine. The pieces exist: `recipes.jsonl` is already a run spec (ratio, lr, accum, segments, data, cache); `/root/STATE` markers written by `mark()` in `chain_train.sh` are already a state log; `gate.json` is already a gate; `bench_provision.sh` already has a credit gate, launch deadline, milestone file, marker-based liveness and abort-with-verified-destroy. They are not connected, and `run_r8v2.sh` reading `/tmp/r8v2_iid.txt` or `run_latency.sh` editing `ledger.md` with a Python string replace are the symptoms.

### Target shape

Run spec (one file, validated before any spend):

```yaml
pair: {harness: claude-code@adapter-v1, model: qwen3.8-27b@rev, template_sha, tokenizer_sha}
stages: [span, data, train, serve, evaluate, benchmark]      # any prefix; span is always first and blocks the rest
inputs: {capture: path, ratio: 8, tools_ratio: 8, lr: 1e-3, accum: 8, smax: 32000}
budget: {max_usd: 40, max_hours: 8, min_credit: 30, idle_min: 45}
gates: {span_share_min: 0.25, invariance: all_calls, quality: gate.json, unswapped_turns_max: 0}
compute: {backend: vast, gpu_query: "...", image: vllm/vllm-openai:v0.28.0}
```

Stage pipeline: each stage is a function `(state, spec) -> artefacts + hashes`, with a required-input manifest checked before the stage starts (the `provision.sh` scp list becomes that manifest). Outputs are content-addressed; the bundle from `span` is the identity every later stage records.

Lifecycle state machine, persisted to `runs/<id>/state.json` after every transition, reconstructed on restart (the controller's `done` set and `started` clock are process-local today): `planned -> preflight -> provisioning -> provisioned -> stage:<name> -> syncing -> synced -> destroying -> destroyed | aborted`. `destroyed` is entered only after the provider confirms the instance is gone (the verify step in `bench_provision.sh::abort` becomes the only path). `synced` requires a checksum manifest of required artefacts; `controller.py::finish()` today ignores `scp_down` failure and marks done even when `destroy()` fails.

Compute backend interface: `search_offer`, `create`, `wait_ssh`, `put`, `run`, `get`, `destroy`, `confirm_destroyed`, `cost_so_far`. The vast implementation wraps `rsh.sh` and the SDK; the idle watchdog stays on-box but reports through the same STATE file, with the DELETE checked.

What replaces the per-journey scripts: nothing per journey. A journey becomes a spec file plus the run directory the loop writes. `bench_provision.sh`, `provision.sh`, `provision_eval.sh` collapse into the `provisioning` stage; `chain_*.sh` become on-box stage runners invoked with the spec; the ledger becomes a JSONL the loop appends on create, sync and destroy, and `ledger.md` is rendered from it.

### RSI, time-boxed: four mechanisms

1. Failure triage. Classify a failed run from typed STATE markers and logs into {provision, ssh, oom, train_diverged, serve_unhealthy, eval_http, gate_fail}; retry only classes on an allowlist (provision, ssh, serve_unhealthy) at most twice, with a fresh offer; stop otherwise. Needs typed markers instead of free text. Guardrail: retries count against `budget.max_usd`. Measure: unattended completion rate and dollars per completed run.
2. Lessons store as enforced checks. Each incident becomes a preflight or postcondition (the 2026-09-15 pgrep incident already turned into the marker-based liveness check in `bench_provision.sh`; the `JDIR` bug and the 8500 vs 8600 tunnel mismatch would become "all ports allocated once and echoed into state"). Needs a `checks/` directory the preflight runs. Guardrail: checks are code reviewed like any change; no automatic generation. Measure: count of repeat incidents.
3. Gated promotion. A candidate bundle replaces the incumbent only after the held-out task suite passes `gate.json` against a teacher measured in the same run, not the historical `teacher_reference` 12/12, plus zero unswapped turns and invariance pass. Needs a fixed untouched task split. Measure: number of promotions later reverted.
4. Bounded recipe proposer. An agent reads the results ledger and proposes the next spec inside a whitelist of tunable fields (ratio, lr, accum, smax) and a per-proposal budget; a human approves. Adopt last, only after 1 to 3 give clean ledgers. Guardrail: it cannot change gates, budgets or adapters. Measure: gate pass rate of proposed versus hand-written recipes.

Not adopted: self-modifying loop code or prompts (no eval to make it safe, and the review shows the loop cannot yet reliably tear down a box); automatic gate relaxation; unbounded search over recipes; agent-driven provisioning decisions (spend decisions stay in the spec).

### Next steps, ordered

1. Write the spec schema and a preflight that validates spec, credit, required inputs and ports; fix `JDIR` and the tunnel port in the process.
2. Persisted state machine with sync-verified and destroy-confirmed transitions; controller reads state, not a `done` set.
3. Typed STATE markers on-box (`stage:train:ok`, `stage:train:fail:oom`) and failure triage with a retry allowlist.
4. Ledger as JSONL written by the loop; render `ledger.md` from it.
5. Fold `provision*.sh` and `chain_*.sh` into stage runners driven by the spec; delete `run_*.sh`.
6. Gated promotion with in-run teacher arm and untouched split.
7. Recipe proposer, only after the above.

## Three next steps first, overall

1. `CallRecord` plus `ClaudeCodeAdapter` extracted from the three scripts, with the per-call invariance report as stage zero. This unblocks both questions and exposes the serialisation disagreement immediately.
2. Mandatory bundle identity (harness, model, tokenizer, template, catalogue, rules hashes) in `segments.json`, enforced by proxy and dataset builder.
3. Run spec plus preflight plus persisted state machine with verified sync and confirmed destroy, replacing `controller.py::finish()` and the `run_*.sh` entry points.
