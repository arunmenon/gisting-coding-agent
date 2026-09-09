# Gisting → Experiment Queue for LLM Agent Compression

Source: Shopify Engineering, "Gisting: LLM Context Compression" (https://shopify.engineering/gisting). Digested 2026-09-03.

---

## 1. What Shopify did, in one paragraph

They took the fixed system prompt of their Sidekick GraphQL agent (~6,000 tokens) and replaced it with ~1,500 learned "gist tokens" (4:1). Model weights stay frozen; only the gist token embeddings are trained. Training is self-distillation: the same model runs twice per trajectory — a teacher pass with the full prompt, a student pass with the gist tokens in its place — and the gist embeddings are optimized with KL divergence between teacher and student logits at every response position. At deploy time the trained embeddings are written straight into the embedding matrix and the gist tokens registered as special tokens, so the serving stack needs no custom attention masking. Measured at 350 requests/minute: median TTFT 438ms → 354ms (−19%), median end-to-end latency 6.8s → 4.2s (−38%), throughput 20.2 → 23.4 QPS (+16%), and 14% fewer GPUs on their production GraphQL workload. Gisting compounds with prefix caching (they run both) because prefix caching removes prefill cost but not the decode-time attention and KV-cache reads over a long prefix.

## 1a. The same thing, from first principles

Interactive companion: **Gist Trainer** (https://claude.ai/code/artifact/cbda2103-4419-40e1-85c4-ad743569be46) — a toy model that runs the full training loop in the browser with every number visible.

**What a model actually reads.** A language model never sees words. Text is chopped into *tokens* (roughly word-pieces; "GraphQL" might be two or three of them), and each token is looked up in a big table that maps it to a list of a few thousand numbers. That list is the token's *embedding* — think of it as the token's coordinates in a huge space, where tokens with similar meaning sit near each other. The model only ever consumes these coordinate lists; the table is the doorway between text and the model.

**Why a long system prompt is expensive.** A system prompt is a few thousand tokens of instructions that get prepended to every single request. The model has to process them all before it can start answering, and, worse, every answer token it later produces has to "look back" over all of them. Six thousand tokens of preamble is a six-thousand-word note the model rereads on every request, and re-glances at for every word it writes. That is the cost gisting attacks.

**The idea: invent new tokens whose coordinates mean "the whole prompt".** Nothing says the embedding table has to contain only real words. You can add brand-new rows — call them gist tokens — and choose their coordinates freely. The bet is that 1,500 rows of carefully chosen coordinates can carry the same information as 6,000 rows of real-word coordinates, because real words are a wasteful encoding: many tokens are grammar and filler, and the meaning is spread thinly across them. A gist token is a dense, made-up "word" that means something like "instructions chunk 37".

**How do you choose the coordinates? Copy the model's own behaviour.** You can't write coordinates by hand. Instead you set up a matching game. Take a real conversation (a user question and the model's reply). Run the model once with the full 6,000-token prompt in front and record, for every position in the reply, its full list of "how likely is each possible next token" numbers. That's the *teacher* — the behaviour you want to keep. Then run the *same* model again, but with the 1,500 gist tokens in place of the prompt, and record the same lists. That's the *student*. The two lists disagree, and the size of the disagreement is measured by a single number (KL divergence is just a standard way of scoring "how different are these two probability lists"). Then nudge the gist coordinates a little in whichever direction shrinks that number, and repeat over thousands of conversations. Over time the gist coordinates settle into values that make the student's predictions match the teacher's. "Distillation" is the name for this copy-the-outputs training, and "self" because teacher and student are the same model with different inputs.

**Why "frozen weights" matters.** The model has billions of internal numbers (its weights) that could also be nudged during this game, but Shopify locks them all and moves only the 1,500 gist rows. Two payoffs: the model cannot drift into new behaviour anywhere else, and the thing you produce at the end is not a new model, it's just 1,500 extra rows for the embedding table.

**Why deployment is trivial.** Because the output is just table rows, shipping it means appending those rows to the model's embedding table and telling the tokenizer "these 1,500 new special tokens exist". The serving software then handles a gist token exactly the way it handles the word "the": look up its row, feed it in. No custom code in the serving path, no special attention tricks.

**One-liner.** Gisting teaches the model 1,500 made-up words that, together, mean the same thing as its 6,000-word instruction manual, by tuning only those words' dictionary entries until the model behaves identically with either in front of it.

## 2. The transferable learnings (what actually moved the needle)

Shopify ran an "autoresearch" loop — propose a recipe, train, evaluate, repeat — and reported which changes had high impact. These are the parts worth copying, in rough order of leverage:

**Initialization is the biggest single win.** Instead of random init, split the system prompt into chunks of length k (k = compression ratio) and initialize the n-th gist embedding with the mean of the n-th chunk's token embeddings. This reduced initial loss 7×. Lesson: the gist tokens should start as a lossy summary of the prompt, not noise.

**There is a knee in the compression curve; find yours.** They swept ratios and found 4:1 was where quality started to degrade for their domain, and explicitly said other domains vary. Lesson: the ratio is a measured quantity, not a hyperparameter you pick.

**Loss normalization changes behavior, not just convergence.** Verbatim: "While averaging per response token made the model hallucinate, averaging over the batch preserved more signal from long responses and produced stable embeddings." Interpretation (mine): per-response averaging down-weights every token in a long response, so the gist learns mostly from short answers; batch-level averaging (sum over all tokens in the batch ÷ total tokens) keeps long-response tokens at full weight. Lesson: instrument the loss by response length, not just in aggregate.

**Data quantity and diversity closed the remaining gap.** After the above, the residual teacher–student gap was closed by "curating a large and diverse dataset." Lesson: the gist only generalizes over the distribution of trajectories it saw; budget for data generation, not just training.

**Training throughput unlocks the research loop.** Precomputing teacher logits and pre-tokenizing cut a full run from 30 hours to 6. Lesson: do this before the sweeps, not after — the sweeps are where the wins came from, and a 5× faster loop is 5× more sweeps.

**Deployment is trivial by design.** Embeddings go into the embedding matrix; tokens go into the tokenizer. Nothing else changes. Lesson: pick a method whose output is a model artifact your existing serving stack already understands.

**It feeds continual learning.** Once gist embeddings exist, the gisted model is the new starting point; later updates can train weights and gist embeddings together instead of re-distilling from scratch.

## 3. Target: Claude Code 2.1.259 → self-hosted Qwen/Qwen3.8-27B

Pinned 2026-09-03. Harness: Claude Code 2.1.259 (pin it; disable auto-update for the duration). Model: `Qwen/Qwen3.8-27B` (config read from the Hub on 2026-09-03; `model_type: qwen3_5`, 64 layers, hidden 5120, bf16, 262k context, vision tower present). Serving: currently direct, no proxy (see 3.1). Gisting is *possible* here (we own the weights), with one architectural caveat that lowers the ceiling (3.5).

### 3.1 How the pieces fit

Claude Code speaks the Anthropic Messages API. To reach a self-hosted model it is pointed (via `ANTHROPIC_BASE_URL`) at a proxy that translates Messages-API requests into the OpenAI-style chat request the serving engine accepts (LiteLLM, claude-code-router, or a thin custom shim; confirm current options before building). That proxy is the single most useful component in this project, for three reasons:

1. **It is the tap.** Every request Claude Code makes passes through it: the system blocks, the `tools` array, the full message history, and the model's response. Logging there gives the training trajectories for free, in exactly the form the model saw them.
2. **It is where the substitution happens.** Shopify's "no custom serving infra" holds for the engine (vLLM/SGLang serve the gisted model as an ordinary model), but *someone* must put `<gist_0>…<gist_N>` into the request in place of the static prompt text. For us that's the proxy: it recognises the static span and swaps it. Claude Code itself is never modified.
3. **It is the A/B switch.** Full-prompt and gist-prompt arms are one proxy flag apart, on the same engine, same model, same sessions.

Serving: vLLM or SGLang with automatic prefix caching ON in both arms (Claude Code's own `cache_control` markers are dropped by the proxy; the engine's prefix caching covers the same ground).

### 3.2 What exactly gets gisted

Not "Claude Code's system prompt" as a whole. The unit is the **exact token span that is byte-identical across sessions after the chat template renders it.** For Qwen the chat template folds the `tools` array into the system message as JSON, so the rendered prefix is: Claude Code's fixed instruction text + the rendered tool schemas + per-session injections (working directory, git status, date, platform/env info, the repo's `CLAUDE.md`). Only the fixed text and tool schemas are gistable. The injections stay as raw tokens.

Two consequences. If dynamic content is interleaved *inside* the static text rather than appended after it, the gist must be split into several segments (static A → gist block A, dynamic, static B → gist block B); that is fine, since gist tokens are positional stand-ins and training just uses the same layout. And the static span must be pinned to a **specific Claude Code version**; every Claude Code release that touches the prompt or tool schemas changes the span and triggers a retrain (E9).

`CLAUDE.md` is per-repo and cannot be gisted generally. For one large monorepo with a stable `CLAUDE.md` it could get its own gist segment; treat that as a later extension.

### 3.3 Model-level facts (read from the checkpoint's config, 2026-09-03)

- **Embeddings are untied** (`tie_word_embeddings: false`). Adding gist rows to the input embedding does not by itself make them generatable. But if the export resizes both input embedding and output head (the usual `resize_token_embeddings` path), the new head rows will be random and the engine *can* sample them. Either leave the head at its original width if the engine tolerates it, or mask the gist ids at sampling (`logit_bias` / allowed-token processor). Verify with a generation test that no gist id is ever emitted.
- **Spare rows: 243.** Embedding `vocab_size` is 248,320; the highest tokenizer id is 248,076 (33 added tokens, 248,044–248,076, none reserved/unused). A 4:1 gist of a multi-thousand-token span needs far more than 243, so the export **must resize** the embedding matrix. Confirm the engine loads the resized checkpoint and that `vocab_size` in config, tokenizer length and both matrices agree.
- **Tokenizer** is `Qwen2Tokenizer` (BPE). New gist tokens are registered as added special tokens so the literal string `<gist_0>` tokenizes to one id. Round-trip test: encode the string, expect a single id ≥ 248,077; decode with and without `skip_special_tokens` and confirm behaviour.
- **Chat template renders tools into the system message** under a `# Tools … <tools>` block. So the tool catalogue Claude Code sends is part of the static span, and the JSON rendering of that catalogue must be byte-stable across requests (key order, whitespace). Diff two renders before trusting the span.
- **Checked 2026-09-03 on CPU (experiments/gist/).** Tokenizer accepts 5,525 `<gist_N>` special tokens at ids 248,077 to 253,601, one id each. Embedding grown to 253,696 rows with mean-chunk init; lm_head grown with zero rows; real rows untouched. The chat template puts the tools block before the system text and prepends a reasoning-effort line that changes with effort, so the span is: [effort line, dynamic] [tools 20,506] [system 602] [cwd] [system 525] [cwd] [system 458]. Still to verify on GPU: vLLM loads the resized checkpoint, and gist ids are never sampled (zero head rows plus a logits mask).
- **Multimodal checkpoint** (vision config, image/video pad tokens). Irrelevant to gisting but affects serving flags; serve text-only.

### 3.4 Why coding agents are a good target, and where they bite

Good: the prefix is large (rules + a full tool catalogue), re-read on every one of the dozens-to-hundreds of tool-call turns per session, and every generated token attends back over it, so Shopify's decode-time win applies per turn. The prefix's KV-cache footprint also shrinks ~4×, which for long-context agent sessions translates to more concurrent sessions per GPU.

Bites: as a session grows with file contents and tool output the prefix becomes a smaller share of context, so the E0 gate must be measured *integrated over real sessions*, not per request. Quality is exact-match: tool-call JSON must be precisely right, rare tools must still be invoked correctly, and behavioural rules (read before edit, run tests, ask before destructive actions) must survive. Trajectories are long (tens of thousands of tokens each), which makes teacher passes and training expensive per example.

### 3.5 Architecture caveat: this is a hybrid linear-attention model

The config carries `linear_*` fields, a `mamba_ssm_dtype`, and `full_attention_interval: 4`. That means only every fourth layer (16 of 64) is ordinary full attention with a per-token KV cache over the prefix; the other 48 layers are linear-attention / state-space layers that fold the prefix into a **fixed-size state** regardless of prefix length.

Why it matters for the business case: Shopify's headline win (38% end-to-end latency, 14% fewer GPUs) came largely from *decode-time* savings, i.e. every generated token attending over a shorter prefix and reading a smaller KV cache. In this model, that per-token cost over the prefix exists only in the 16 full-attention layers, and their KV footprint is small (4 KV heads × 256 head-dim). So the decode-time and KV-memory savings from a 4× shorter prefix are roughly a quarter of what a full-attention model of the same size would see. **Prefill savings are unaffected** (all 64 layers still process every prefix token), but prefix caching already captures most of prefill for a static span. Net: expect a materially smaller latency/GPU win than Shopify reported. E0 must measure this rather than assume it; the integrated-share gate in E0 should be read against this lower ceiling.

Why it matters for the method: in the linear layers the prompt's information is already compressed into a fixed-size state; the gist tokens must reproduce *that state* as well as the full-attention KV. Nothing in the training recipe changes (the KL objective is agnostic to architecture), but this is a regime the article does not cover, so treat E2's outcome as an open question, not a formality.

## 4. Metrics to track on every experiment

| Column | Definition |
|---|---|
| ratio | static-span tokens : gist tokens |
| KL@end | mean teacher–student KL on a held-out set of Claude Code turns |
| task success | pass rate on the fixed task set (§5, E0) run headless through Claude Code, student vs teacher |
| tool validity | fraction of student tool calls that are schema-valid and name a real tool |
| per-tool parity | per tool: invocation rate and argument exact-match, student vs teacher, on identical session prefixes |
| rule probes | pass rate on scripted probes for specific prompt rules (e.g. edits a file without reading it first; skips tests; runs a destructive command without confirmation) |
| halluc. rate | judge-scored student-vs-teacher divergence on the top quartile of response length |
| TTFT / turn latency / sessions-per-GPU | per turn, at N concurrent sessions, prefix caching ON both arms |
| KV per session | KV-cache bytes held by the prefix per live session |
| train cost | GPU-hours per run |
| data | sessions / turns, stratified how |

All quality columns are *relative to the teacher* (Qwen with the full prompt), never to Claude-the-frontier-model. Gisting can only preserve what the served model already does.

## 5. The experiment queue

### E0 — Instrument the proxy and measure the prompt's real share
Hypothesis: the static span is a large enough share of tokens, integrated over real sessions, that 4:1 compression materially changes cost.
Setup: stand up Claude Code → proxy → engine with the full prompt. Log every request. From ≥100 real sessions compute: static-span token count for the pinned Claude Code version; per-turn context length; static-span share per turn and integrated over the session; turn TTFT and latency; KV bytes per session. Build the fixed task set (a SWE-bench-Verified-style subset plus a set of in-house tasks run with `claude -p`), and the rule probes.
Decision gate: if the integrated static share is below ~25%, gisting alone will underdeliver; pursue prompt trimming and prefix caching first. Record the number either way; it predicts the ceiling of everything below.
Cost: engineering days.

**Result (2026-09-03, journey j1, experiments/journeys/j1-e0-tap/journey.md).** Rendered static span 21,109 tokens (system 603, 51 tool schemas 20,506, of which 24 Playwright MCP tools 4,512). Integrated static share over 8 short headless sessions: median 0.73 (context median 29k, max 34k). Gate PASSED. System text differs across sessions in two characters only (cwd digit), so the layout is three static segments plus the tool block. vLLM 0.28 prefix caching works on the hybrid model (87% token hit rate). Caveats: sessions were short; at 100k context the same span is 21%. First zero-training action: drop the unconnected MCP tools from the catalogue.

### E1 — Prefix caching as the no-training control
Hypothesis: engine prefix caching already removes most prefill cost for the static span; gisting must beat *this*, not the uncached case.
Setup: same sessions, prefix caching on vs off. Record TTFT, turn latency, sessions-per-GPU.
Decision gate: this is the control arm for E8. Ship prefix caching now regardless.
Cost: hours.

**Result (2026-09-03, journey j2).** Prefix caching is on by default in vLLM 0.28 for this hybrid model. Token hit rate 87% on short sessions, 60% over a mixed run with long sessions. Long-session static share (trimmed 17,540-token span, 27 tools): short sessions 0.72, medium 0.48, long 0.44, turns at 80k to 100k context 0.18. One 23-turn session hit the 131k limit.

### E1.5 — Instruction-coverage audit of the training set
Hypothesis: some instructions and tool schemas in the static span are never exercised by logged sessions and would be silently dropped by the gist.
Setup: split the static span into individual instructions and tool schemas. For each, delete it from the prompt and re-run the *teacher* over the candidate training turns; count turns whose output changes materially. That count is the item's coverage.
Decision gate: any item with near-zero coverage needs synthetic sessions that exercise it before E2. Items with zero coverage on a broad set are candidates for removal from the prompt itself. Re-run after E6's data expansion.
Cost: one teacher sweep per instruction; cheap relative to training.

### E2 — Minimum viable gist on the Claude Code static span
Hypothesis: frozen Qwen, 4:1, mean-chunk init, batch-averaged KL, ~2–5k logged turns → KL falls well below random-init, tool validity stays near 100%, task success within a first-run tolerance.
Setup: implement the two-pass trainer over logged turns (teacher: full rendered prompt; student: gist segments in place of the static span, dynamic injections kept). Confirm the mean-init vs random-init starting-loss gap on this model. Train once. Run the task set and rule probes through the proxy in gist mode.
Decision gate: continue if tool validity ≥ 99% and task success within ~10 pt of teacher. Degenerate output or a flat loss is a pipeline bug (usually the span/tokenizer checks in §3.3), not a method limit.
Cost: 1–2 days engineering, tens of GPU-hours (long contexts).

**Pipeline result (2026-09-03, journey j2).** The two-pass trainer runs on one 96 GB GPU with frozen weights, gradient checkpointing, and a forward hook injecting the gist rows: 32 s per 24k-token example. On 50 examples (25 steps, lr 2e-3) held-out KL/token fell 0.660 -> 0.473 from mean-chunk init. Trained rows export into the checkpoint and serve in vLLM with a logits mask; 0 gist ids emitted. Parity probe on 12 turns: student always emitted a well-formed tool call, tool name matched the teacher 10/12, exact arguments 2/12. This is the pipeline gate, not the quality gate: the full E2 run needs E3 first (a full pass over 1,494 examples is ~15 GPU-hours without precomputed teacher logits) and a serving-side swap (custom chat template that omits the tools block while the API still receives tools for the parser).

**Quality result (2026-09-04, journey j3).** Full run: teacher log-probs cached via vLLM prompt_logprobs (top-32, mass 0.999), one epoch over 1,171 examples, held-out KL/token 0.0534 -> 0.0152. Claude Code in gist mode through the tap and a conditional chat template: 12/12 verifiable tasks passed in both arms, input tokens/turn 11.4k vs 24.3k, 0 malformed tool calls, 1 call to a non-existent tool name in 84 (98.8% name validity, sample too small for the 99% gate). E2 PASSED on this task set. See experiments/journeys/j3-e3-e2/journey.md.

### E3 — Speed up the loop
Hypothesis: precomputed teacher logits (top-k + logsumexp) and pre-tokenised turns cut run time ≥3×.
Setup: cache teacher outputs per turn; measure the KL error from top-k truncation; re-run E2's config and confirm identical KL@end. Consider truncating extremely long turns for training only after checking it doesn't shift KL on the held-out set.
Decision gate: prerequisite for E4–E6.
Cost: 1 day.

**Result (2026-09-04, journey j3).** Done via vLLM prompt_logprobs (K=32). Truncation is negligible (top-32 mass 0.999 mean and p10). Cost moved to CPU: ~12 s per 33k-token example, 4.3 h for 1,457 examples, because the engine builds per-position Python dicts. Training then needs only the student pass: 98 s per 8-example step at <=30k tokens, 4 h per epoch on one 96 GB GPU. Engine must run at ~80% memory utilization with 4k prefill chunks or the full-vocab logprob tensor OOMs it.

### E4 — Compression-ratio sweep
Hypothesis: quality is flat up to some ratio and then breaks; tool-schema-heavy text may tolerate a higher ratio than prose rules, or the reverse.
Setup: 2:1, 4:1, 8:1, 16:1 on the whole span; then, if segments exist, sweep the tool-schema segment and the rules segment independently. Plot KL@end, tool validity, per-tool parity, task success vs ratio.
Decision gate: largest ratio before any quality column breaks tolerance. Per-segment ratios are allowed.
Cost: 4–8 runs.

**Result (2026-09-04, journey j4, unattended loop, ~$21).** 2:1, 8:1, 16:1 trained one epoch each against the J3 teacher cache and evaluated through Claude Code in gist mode on the 12-task set: 12/12 at every ratio, 0 malformed calls, 0 invented tool names, all turns swapped; input tokens/turn 16,083 / 11,410 (4:1, J3) / 9,395 / 8,245 vs teacher 24,258. No knee found on this task set even at 16:1 (1,099 gist tokens for 17,539). KL not comparable across runs (different held-out subsets). Next: a harder task set that exercises rare tools and long sessions before choosing a ratio to ship. See experiments/journeys/j4-ratio-sweep/journey.md.

### E5 — Loss normalisation ablation
Hypothesis: per-turn-token averaging makes the student hallucinate on long turns; batch-level averaging does not. Coding-agent turns vary in length by orders of magnitude, so this may matter more than it did for Shopify.
Setup: two runs identical except the reduction. Score hallucination and tool validity on the longest-turn quartile separately.
Decision gate: adopt whichever holds on long turns; keep the length-sliced metric permanently.
Cost: 2 runs.

**Result (2026-09-07, journey j7, $7).** At the corrected 8:1 span, per-response averaging ends at held-out KL 0.0107 vs 0.0088 for batch-level, and scores 14/16 vs 16/16 on the hard exam (misses the Agent task; no invented paths, no malformed calls). Direction matches Shopify; magnitude mild. Batch-level stays the default.

### E6 — Data scale and diversity
Hypothesis: the residual gap closes with more, and more varied, sessions; diversity across tools and repo types matters more than raw count.
Setup: scale 1k / 5k / 20k turns; at fixed N compare "top repos only" vs stratified across tools, languages, task types (bugfix, feature, refactor, explain), failure paths (test failures, permission denials, tool errors), and turn depth. Re-run E1.5 on each set.
Decision gate: where the curve flattens is the data budget. If diversity dominates, build a session generator targeting uncovered tools and rule paths.
Cost: 6–8 runs; session generation is the real cost.

**Result (2026-09-07, journey j8, ~$15).** 48 sessions exercising the 18 never-called tools (teacher reaches every required tool, 16/16, 21 distinct tools) gave 299 examples; retraining corrected 8:1 on base + coverage data (KL 0.0188 -> 0.0084) scored 9/16 on a coverage exam that requires the named tools, against 10/16 for the pre-coverage 8:1 and 16/16 for the teacher. Same tools missing in both: worktrees, web search, messaging. Conclusion: rare-tool reachability at 8:1 is a capacity limit of the gist, not a data shortage; the hard exam alone would not have shown it (14/16 vs 16/16). A residual path-fidelity failure remains at ~1 in 16 sessions even with paths raw.

**Harder-exam result (2026-09-04, journey j5).** A 16-task exam (rare tools, real repos at depth, rule probes, adversarial file content; log-aware scorer) run against the teacher and all four ratios on one box: teacher 15/16, 2:1 12, 4:1 11, 8:1 11, 16:1 12. The shared failures (tasks needing an absolute-path Write after Glob, WebFetch, or Agent) are one defect: the cwd line, session UUID included, sat inside the gisted span and a summary cannot reproduce it verbatim, so the students write to invented paths. Fix in gist/segments.py (VERBATIM_LINE: paths, UUIDs, dates, model name kept as raw tokens); Validated: 8:1 retrained on the corrected span scores 16/16 on the hard exam (teacher 16/16 same night), all absolute-path writes to the real directory, held-out KL 0.022 -> 0.009. Sub-agent sessions (Agent tool) have their own span and run unswapped. See experiments/journeys/j5-hard-eval/journey.md.

### E7 — Robustness
Hypothesis: the student diverges from the teacher most on deep turns (prefix far from the current position), unseen repos/languages, and adversarial content in files or tool output that the prompt's rules are meant to resist.
Setup: evaluate the best E6 student on those slices; run the rule probes with adversarial file contents.
Decision gate: any rule the teacher holds and the student breaks is a launch blocker; fold into data, retrain.
Cost: eval plus one retrain.

### E8 — Serving integration and load test
Hypothesis: with rows written into Qwen's embedding matrix, tokens registered, and the proxy swapping the span, the engine serves the gisted model unchanged; at N concurrent sessions with prefix caching ON in both arms, per-turn latency, sessions-per-GPU, and KV-per-session improve.
Setup: export the checkpoint; deploy beside the E1 control; replay identical sessions; compute GPU-equivalents.
Decision gate: ship if E6/E7 quality holds and the cost win exceeds the E9 retraining tax.
Cost: 1–2 days.

**Result (2026-09-07, journey j6, $1.25).** Corrected 8:1 gist vs full prompt on one 96 GB GPU, prefix caching on in both arms, 12 sessions x 6 turns replayed in order, 200 generated tokens per request. Concurrency 1: throughput +5%, median latency -3%. Concurrency 4: throughput +15%, latency -11%, TTFT p90 -39% (9.0 s to 5.5 s). Concurrency 8: throughput +16%, latency -12%. Shopify's +16% throughput reproduces; their -38% latency does not, as section 3.5 predicted for a hybrid model. Prefix hit rate 0.72 to 0.75 teacher, 0.51 gist. See experiments/journeys/j6-latency/journey.md.

### E9 — Claude Code upgrades and continual learning
Hypothesis: warm-starting from the previous gist rows makes retraining after a Claude Code prompt/tool change a short run.
Setup: apply a real Claude Code version bump; diff the static span; retrain from old rows vs from mean-init; compare steps-to-converge. Same for a Qwen checkpoint update (joint weights+gist vs re-distil).
Decision gate: determines the operational cost. Claude Code ships frequently; if every bump costs a full run, that dominates the economics.
Cost: 3–4 runs.

### E10 — Stretch: segmented gists
Hypothesis: separate gist segments for the tool catalogue and the rules text let a tool-schema change retrain only that segment. Also the natural home for a per-monorepo `CLAUDE.md` segment.
Decision gate: only if E9 shows the retraining tax is painful.
Cost: exploratory.

## 6. Ordering and gates

E0 → E1 → E1.5 → E2 → E3 → E4 → E5 → E6 → E7 → E8 → E9 → (E10).

Hard gates: E0 (is the integrated static share big enough), §3.3 checks (can this checkpoint and engine take new tokens at all), E2 (does the pipeline work), E7 (does the student hold the rules). Everything else is tuning.

## 7. Open questions to settle before E0

- **How is Claude Code reaching the model with no proxy?** Presumably `ANTHROPIC_BASE_URL` pointed at an engine that speaks the Messages API natively. Whatever it is, we still need a tap (request logging) and a swap point (gist substitution). Options: a thin proxy in front of the engine (preferred; ~100 lines), or engine-side hooks. Decide before E0, since E0's logs come from it.
- Which engine and version (vLLM / SGLang), and does it load a resized `qwen3_5` checkpoint and respect added special tokens?
- Task set: which SWE-bench subset, how many in-house tasks, who writes the rule probes.
- Where sessions are logged and how repo contents in training data are handled (privacy/licensing).
- Given 3.5, what latency/GPU win is *worth it*? Set the bar before measuring so E0 is a decision, not a negotiation.

## 8. What the article does not tell you (and what I filled in)

The article does not state the base model or its size, the dataset size or how trajectories were generated, the quality metrics used to confirm behaviour was preserved, the number of training steps or learning rate, or how often the prompt changes and what retraining costs. Everything in §3–§5 specific to Claude Code and Qwen, the quality metrics, the cost estimates, the data sizes, and the tolerances are my proposals, not Shopify's. The instruction-coverage audit (E1.5) is my construction, derived from how the training slopes work, not from the article. The only prior work the article cites is Wingate, Shoeybi & Sorensen (2022), "Prompt Compression and Contrastive Conditioning." The term "gisting" and the gist-token framing also come from Mu, Li & Goodman (2023), "Learning to Compress Prompts with Gist Tokens" — that attribution is from my own knowledge; the notable difference is that Shopify freezes the model and trains only embeddings via self-distillation, whereas the earlier work fine-tuned the model with a gist attention mask.

## 9. Experiment log template

```
id:             E4-r8
date:
claude code:    <pinned version>
checkpoint:     <qwen checkpoint>
static span:    <token count>, segments: <n>
ratio:          8:1 (per segment if split)
init:           mean-chunk
loss reduce:    batch
data:           20k turns from 1.2k sessions, stratified by tool + task type
steps / lr:
KL@end:
task success:   student / teacher
tool validity:
per-tool parity: worst tool + value
rule probes:    pass / total
halluc. rate:   aggregate / longest-quartile
TTFT / turn latency / sessions-per-GPU (prefix cache ON both arms):
KV per session:
train cost:
notes / decision:
```


---

## Program closed 2026-09-09

Nine journeys, about $135 of rented GPU across all runs and failed hosts, credit remaining $33. Independent Codex review 2026-09-08 (experiments/journeys/reviews/) reconciled; the whitepaper is reframed as an internal development study.

Established: the gist pipeline builds and serves on Qwen3.8-27B with no engine patch; distillation loss falls; compressed prompts pass a narrow, reused coding-task set at ratios 2:1 to 16:1; the working-directory/verbatim span defect is real and its fix (keep paths, ids, dates, model name raw) took an 8:1 gist from 11 to 16 on the hard exam; one fixed-output benchmark showed about +16% throughput at concurrency 8 with little single-session latency gain, as the hybrid architecture predicts.

Not established (open, need a rebuilt and validated evaluation harness): independent task parity on unseen work; catalogue-wide rare-tool reach and whether a per-segment ratio restores it (J9 inconclusive, six harness faults, rows saved); a measured path-fidelity rate; production throughput and sessions-per-GPU; the retraining tax on a real client upgrade (E9). The loss-reduction ablation (E5) mildly favoured batch averaging on a single run.

Deliverables: whitepaper and field-notes artifacts, this queue doc, the ledger, per-journey entries and logs under experiments/journeys/, the reusable review skill, and saved trained rows for 4:1/8:1/16:1 and the two per-segment ratios.
