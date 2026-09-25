# Steno explainer video: production plan and prompts (v2)

A 3Blue1Brown-style narrated explainer of our gisting research and the Steno capability built from it, generated with Manim Community Edition plus a synced voiceover.

v2 incorporates independent reviews by Fable and Codex (`experiments/journeys/reviews/video-plan-20260925/`). Both found the arc sound, the numbers accurate, and the plan not yet buildable: qualifiers were missing, scene 7 spent numbers scene 8 had not yet explained, and the pipeline assumed LaTeX and word-timed voices this machine does not have.

## 1. Brief

| Item | Decision |
|---|---|
| Audience | Internal engineering leadership: they know LLMs and coding agents, not gisting |
| Length | 6 to 8 minutes; scene budgets are set from measured audio, not word counts |
| Tone | 3Blue1Brown: curious, patient, visual first, one idea at a time, no hype |
| Pilot | Scenes 1 and 8 end to end first: the pipeline and the hardest visual, before the other seven |
| Voice | macOS `say` for every iteration render; Kokoro, running locally, for the final. No cloud voice, because the script carries internal numbers |
| Output | 1080p30 MP4, a separate `.srt` caption file, and later a 30-second teaser with its own qualified script |
| Branding | Title card "Steno · PAI"; no personal names |

### Source precedence

Where sources disagree, this order decides:

1. **Measurement claims:** the corrected white paper (`Gisting-NeurIPS-paper.html`), then the reconciled reviews (`experiments/journeys/reviews/review-20260915T073918Z-codex.md`, `findings-20260915-j11-remediation.md`).
2. **Framing and capability status:** the deck (`Gisting-CTO-deck.html`) and `steno-capability.md`.
3. **Historical evidence only:** journey narratives such as `experiments/journeys/j10-bench/journey.md` and `j11-conn/log.md`. Several still state explanations that were later withdrawn. Never take a claim from them that the paper does not also make.

Every prompt must flag a conflict rather than pick whichever source reads best.

## 2. Story arc (nine scenes)

Each scene has one job and a status label: demonstrated on one pair, implemented, or planned.

| # | Scene | The one idea | Core visual |
|---|---|---|---|
| 1 | The re-read | We studied one pair, Claude Code with a self-hosted Qwen model. The agent re-sends the same fixed preamble on every call; prefix caching already absorbs part of that cost. Steno is named here. | Three or four turns shown, then a repeat marker, rather than an ever-growing conversation. The fixed block reappears before each turn. |
| 2 | Anatomy of the tax | The block is mostly tool schemas. Separately: across eight logged sessions, the static span averaged 0.72 of cumulative input, falling as history grows. | A composition bar (tool schemas, rules, per-session values; small segments labelled outside), then a separate share display. The two are never drawn as one bar. |
| 3 | The shorthand | The fixed span becomes a small set of trained embedding rows: not a text summary, not arbitrary-context compression. Per-session values stay raw. 8:1 is the ratio for the selected span, not the whole request. | 64 small squares transform into 8 glowing ones; a separate raw lane passes through unchanged. |
| 4 | Teaching it, and shipping it | One frozen model run twice: with the full prompt and with the shorthand. Only the new rows train. The rows ship in the model; a proxy swaps the span; the agent and engine code are unchanged. | A lock on the model, a small block of new rows lighting up, two schematic probability bars moving closer without becoming identical. Closing beat: agent, proxy, model. |
| 5 | Does it still work | On the easy suite, every tested ratio scored 12/12, and at 8:1 input per turn fell from 24.3k to 9.4k tokens. Single runs, partly reused tasks. | Four large score tiles labelled "easy suite"; a token bar shrinking. |
| 6 | A boundary failure | Session values baked into the shorthand sent writes to an invented directory. Keeping them raw, together with retraining, brought the harder suite level. One path error remained. | A path travels into the shorthand and comes out wrong; a raw lane routes it around; an amber residual-risk marker stays on screen. |
| 7 | What the replay showed | H100, short fixed-output replays with caching on: twice the highest tested arrival rate passing each arm's own latency threshold, and +44% observed peak throughput. H200: similar best points. | Paired bars in sequence, not smooth curves. Only registered numbers are plotted. |
| 8 | The instrument was wrong | External review found our load generator capped connections at 100. Lifting the cap showed more than 100 sessions resident and withdrew our explanation. It also lowered throughput in three of four cells. At the two overload points tested, the compressed prompt held up better. Cause still open. About 30 seconds. | A client gate at 100 opens; sampled counts appear as dots above the old line, labelled "more than 100", not as arm-specific needles. "Explanation withdrawn" replaces the old claim. Then the two overload points as paired bars. |
| 9 | From experiment to Steno | Demonstrated: one pair. Implemented: harness adapters, shared span analysis, a run loop with gates and verified teardown, awaiting live verification. Planned: four bounded self-improvement mechanisms. Proposed next: a harness and distilled-model pair, possibly a Jetstream harness, then held-out validation, then a guarded trial. | The adapter chain (harness adapter, shared analysis, model adapter) in one beat; the status ladder in the next; the staged ask on the closing card. |

## 3. Visual language

- Dark ground `#0e1417`; stable colour per concept: petrol `#3fb0c6` for the full prompt, plum `#c39be0` for Steno, copper `#e08a4c` for per-session values, green `#57c08a` for passing, amber `#e3b24c` for caveats. Same palette as the deck.
- Geometry before text. On-screen text is labels and numbers, never the sentence being spoken.
- Dim and reveal: when a part is discussed, everything else dims to 30 percent.
- One persistent object per scene, transformed rather than replaced.
- Minimum text size: 28 at 1080p. Safe area: 5 percent margins on every side, plus caption space at the bottom.
- Discrete values, such as ratios and scores, appear as labels. Only continuous quantities animate.
- No em dashes on screen or in narration.

### No-LaTeX rules (this machine has no LaTeX)

- Never use `Tex`, `MathTex`, or `Brace` labels.
- `DecimalNumber` and `Integer` default to LaTeX: always pass `mob_class=Text`.
- Axes and number lines: `include_numbers=False`, with ticks placed by hand as `Text`.
- Draw icons (lock, gate, badges) from primitives, not emoji.
- Fonts: named macOS fonts verified with `manimpango.list_fonts()`, for example Georgia for titles and Menlo for numbers, each with a declared fallback.

## 4. Claims register

Only these numbers and claims may appear. Each row has a qualifier that must be spoken or shown whenever the claim is used.

| Claim | Value | Must say | Source |
|---|---|---|---|
| Fixed preamble | about 17.5k to 21k tokens across measured span configurations; over 90% tool schemas | "across the configurations we measured" | paper §1, §3.1, Table 1 (17,540 trimmed), §5.1 (21,109 full catalogue) |
| Session share | 0.72 | "mean share of cumulative input across eight logged sessions; falls as history grows" | paper §5.1, Figure 7 |
| Easy-suite tokens at 8:1 | 24.3k to 9.4k per turn | "easy suite, development run" | paper Table 2 |
| Easy-suite scores | 12/12 at 2:1, 4:1, 8:1, 16:1 | "single runs, partly reused tasks" | paper Table 2, §4.5, §7 |
| Hard suite, corrected 8:1 | 11/16 to 16/16 (11/15 to 15/15 excluding one defective probe); input about 25.5k to 10.4k | "retraining, pool and host also changed; one path error remained" | paper §5.5, Table 3 |
| H100 arrival rate | 18 to 36 req/min, highest tested target rate passing | "each arm's own threshold, about 8.5 s and 8.0 s; short fixed-output replays; caching on" | paper §5.6 |
| H100 peak | 42.7 to 61.3 req/min, +44% | "observed peaks; quality at load not measured; capacity not established" | paper §5.6 |
| H200 peak | 85.3 vs 83.3 req/min | "similar best points; H100-tuned settings; two repeats, unequal variability" | paper §5.6 |
| Connection cap | 100 resident in both arms capped; more than 100 (123 to 137 sampled) uncapped | "maximum sampled counts, not hardware ceilings" | paper §5.6, J11 log §6 |
| Cap lifted, overload points | 47.0 vs 80.7 req/min at 128 offered; 46.3 vs 56.7 at 256 | "one run per condition; lifting the cap lowered throughput in three of four cells; at these two tested points" | J11 log §6, §7.4 |
| Capability status | demonstrated, implemented, planned, as in scene 9 | "the self-improvement mechanisms are planned" | `steno-capability.md` |

### Withdrawn or forbidden implications

- The recurrent-state residency ceiling, and "turnover, not headcount".
- Any stated cause of the throughput gap, including cache saturation or "fits more sessions".
- Cheaper-card substitution or fleet savings.
- General quality parity, established capacity, or savings per completed task.
- The self-improvement mechanisms as running.

## 5. Pipeline

0. **Bootstrap and smoke test.** Create a venv with `manim` and `manim-voiceover`. Create `video/style.py`: palette, verified fonts, safe-area constants, `fit_width`, `dim_others`, Text-based number and axis helpers. Create `video/voice.py`: a small `SpeechService` subclass that calls `say -o` (later Kokoro), converts to WAV with ffmpeg, and caches by text hash. Render a 10-second smoke scene with text, a number, an arrow, audio and an `.srt` (`create_subcaption=True`). Nothing else starts until this passes.
1. **Script.** `video/script.md`, per scene: narration split into short beats, one voiceover block per beat, and the claims used, each with its qualifier and source.
2. **Audio first.** Generate and cache all beat audio; measure durations; set each scene's animation budget from them. No bookmarks: the word timing they need is not available from local voices without a Whisper install.
3. **Build.** One file per scene under `video/scenes/`. Each beat is a `with self.voiceover(text=...) as tracker:` block, and animation `run_time` is set explicitly within the beat's duration.
4. **Preview.** Render at `-ql`. Check frames at every animation boundary, not only on a fixed interval (`ffmpeg -vf fps=1/3` plus the end of each `play`). Measure text bounds against the safe area. Watch each scene with audio for sync.
5. **Final.** Render at `-r 1920,1080 --fps 30` (not `-qh`, which is 60 fps and doubles render time). Concatenate with ffmpeg using identical codec settings; add title and end cards; build one `.srt` with cumulative offsets for the cards.
6. **Review.** An independent pass against section 4 and the primary sources: numbers, qualifiers, omissions, visual implications, capability status, and audio sync.

## 6. Prompts

### 6.0 Bootstrap prompt

> Set up `video/` for Manim Community Edition on macOS with no LaTeX. Create a venv and install `manim` and `manim-voiceover`. Write `video/style.py` with the palette, the fonts from section 3 verified via `manimpango.list_fonts()` with fallbacks, safe-area constants (5 percent margins plus caption space), `fit_width`, `dim_others`, and Text-based helpers for numbers and axis ticks. Obey every no-LaTeX rule in section 3. Write `video/voice.py`: a `SpeechService` subclass that renders with `say -o`, converts to WAV with ffmpeg, and caches by text hash. Render a 10-second smoke scene exercising text, a number, an arrow, one voiceover block and an `.srt`. Report the exact package versions and the render time.

### 6.1 Script prompt

> Write `video/script.md` for the nine scenes in section 2, in order, for internal engineering leadership. Read the plan in full and follow the source precedence in section 1. For each scene: narration split into short beats (curious, patient, plain English, no em dashes), the visual for each beat, and every claim used, numeric or not, with its value, its "must say" qualifier from section 4, and its source location. Use nothing outside section 4, and none of the forbidden implications. Where sources conflict, list the conflict instead of choosing. Keep scene 8 to about 30 seconds. After writing, estimate each scene's duration at the chosen voice speed.

### 6.2 Scene prompt (one per scene)

> Build scene N from `video/script.md` as `video/scenes/sceneN.py`, importing only from `video/style.py` and `video/voice.py`. Subclass `VoiceoverScene`, call `set_speech_service` with the local service, and give each beat its own `with self.voiceover(text=...) as tracker:` block, with explicit `run_time` values that fit the beat's measured duration. No bookmarks. Obey the no-LaTeX rules. Keep one persistent object and transform it. Plot only registered numbers, and label illustrative shapes as illustrative. Render at `-ql`; check frames at every animation boundary and every 3 seconds; confirm all text sits inside the safe area at size 28 or larger; watch it with audio. Fix issues before reporting, and report render time and the frames checked.

### 6.3 Review prompt

> Review the rendered video, `video/script.md` and the scene code against this plan and the primary sources it names, independently of the register. Check every number and claim, spoken or shown, for its value, its qualifier and its source. Flag omissions that change meaning, visuals that imply a forbidden claim, capability status shown as further along than `steno-capability.md` records, text overlap or clipping, audio and animation drift, and em dashes. Output findings with scene, timestamp, severity and a fix.

## 7. Resolved decisions

| Decision | Choice | Why |
|---|---|---|
| Voice | `say` while iterating; Kokoro locally for the final | Private, free, no word timing needed with one block per beat. A human recording remains an option for the final. |
| Pilot | Scenes 1 and 8 end to end | Exercises the whole pipeline and the hardest scene before committing to the rest |
| Audience | Internal engineering leadership | The capacity result is still a replay finding; a broader audience would need heavier qualification |
