# Steno explainer video: production plan and prompts

A 3Blue1Brown-style narrated explainer of our gisting white paper and the Steno capability, generated with Manim Community Edition plus a synced voiceover.

## 1. Brief

| Item | Decision |
|---|---|
| Source | `Gisting-NeurIPS-paper.html`, `steno-capability.md`, `steno-design.md`, and the J10 and J11 journey records |
| Audience | Engineering leaders who know LLMs and coding agents, not gisting internals |
| Length | 6 to 8 minutes, about 1,000 to 1,200 spoken words |
| Tone | 3Blue1Brown: curious, patient, visual first, one idea at a time, no hype |
| Output | 1080p MP4 with burned-in-free captions plus a separate `.srt`, and a 30-second teaser cut |
| Branding | Title card "Steno · PAI"; no personal names |

## 2. Story arc (nine scenes)

Each scene has one job. Numbers come only from the claims register in section 4.

| # | Scene | The one idea | Core visual |
|---|---|---|---|
| 1 | The re-read | A coding agent re-sends the same ~20k-token manual on every call | A conversation grows turn by turn; a thick grey block re-appears before every turn and a token counter climbs |
| 2 | Anatomy of the tax | Most of that block is tool schemas, and it is 0.72 of a short session | The block splits into a proportional bar: tool schemas, rules, per-session values |
| 3 | The shorthand | Replace the fixed span with a few learned tokens | A long ribbon of tokens folds down to one eighth its length; the new tokens glow |
| 4 | Teaching it | Self-distillation with the base model frozen; only new embedding rows train | Teacher reads the full prompt, student reads the shorthand; two output distributions converge; a lock sits on the model, a small new block of rows lights up |
| 5 | Does it still work | Scores held at every ratio; input fell from 24.3k to 9.4k at 8:1 | Four ratio chips flip to 12/12; a token bar shrinks |
| 6 | The one failure | Session values baked into the shorthand send writes to an invented directory; keeping them raw fixes it | A file path travels into the gist and comes out wrong; a "raw" lane routes it around; 11/16 becomes 16/16 |
| 7 | What it buys | H100: 2x the rate within the latency target, +44% peak; H200: level at peak, 1.2 to 1.7x under heavy load | Throughput curves draw left to right; the gap opens under load |
| 8 | The instrument was wrong | Our own load generator capped connections at 100; lifting it showed 123 to 137 resident, and we withdrew our explanation | A gauge pinned at exactly 100 in both arms; the cap lifts and the needles move; a strike-through lands on the old explanation |
| 9 | From experiment to Steno | Harness adapters feed a shared span analysis; a loop runs the suite with bounded self-improvement; next, a Jetstream harness | Harness boxes plug into one analysis; a loop diagram with four small RSI badges; closing card |

Scene 8 is deliberate. The 3Blue1Brown register rewards the honest surprise, and it is the most memorable beat in the program.

## 3. Visual language

- Dark ground (`#0e1417`), one accent per concept, stable across scenes: petrol for the full prompt, plum for Steno, copper for per-session values, green for passing, amber for caveats. Same palette as the deck.
- Geometry before text. Show the mechanism moving, then label it. On-screen text is short labels and numbers, never sentences the narrator is also reading.
- Dim and reveal: when a part is discussed, everything else dims to 30 percent.
- One persistent object per scene, transformed rather than replaced, so the eye can follow it.
- Numbers animate from zero with `DecimalNumber`, and each carries its unit.
- Fonts: a serif for titles, a monospace for numbers and code. Plain `Text` only; no LaTeX.
- No em dashes anywhere on screen or in narration.

## 4. Claims register (the only numbers allowed)

| Claim | Value | Source |
|---|---|---|
| Fixed preamble per call | 17.5k to 21k tokens, over 90% tool schemas | paper Section 4.3 |
| Share of a short session | 0.72 (mean of eight sessions) | paper, J1 |
| Tokens per turn at 8:1 | 24.3k to 9.4k | paper Table 2 |
| Easy-suite scores | 12/12 at 2:1, 4:1, 8:1 and 16:1 | paper Table 2 |
| Path failure fix | 11/16 to 16/16 at 8:1, retraining also changed | paper Table 3 |
| H100 serving | 2x rate within each arm's latency threshold; peak 42.7 to 61.3 req/min (+44%) | paper Section 5.6 |
| H200 at peak | 85.3 vs 83.3 req/min, level | paper Section 5.6 |
| H200 heavy load, cap lifted | 47.0 vs 80.7 req/min at 128 sessions; 46.3 vs 56.7 at 256 | J11 log |
| Connection-cap correction | resident sessions 100 in both arms capped; 123 to 137 uncapped | J11 log |

Withdrawn claims must not appear: the recurrent-state residency ceiling, "turnover not headcount", and cheaper-card substitution.

## 5. Pipeline

1. **Plan.** Produce `video/script.md`: per scene, the narration text, the bookmarks (the word that triggers each animation), the visual beats, and the claims used, each checked against section 4.
2. **Build.** One Python file per scene under `video/scenes/`, all importing a shared `video/style.py` (palette, fonts, safe text layout, arrows, a `dim_others()` helper). Each scene subclasses `VoiceoverScene` and wraps its animation blocks in `with self.voiceover(text=...) as tracker:` so animation length follows the audio.
3. **Preview.** Render every scene at low quality (`-ql`), extract a frame every few seconds, and check them: no text overlapping, nothing off-frame, labels readable, colours consistent. Fix, re-render.
4. **Final.** Render at 1080p, concatenate with ffmpeg, add an intro and outro card, and export captions from the narration text and audio timings.
5. **Review.** An independent pass checks every spoken and on-screen number against section 4 and flags any withdrawn claim.

Tooling: Manim Community Edition, `manim-voiceover`, ffmpeg (installed), cairo and pango (installed). No LaTeX needed.

## 6. Prompts

### 6.1 Planning prompt

> You are writing the script for a 6 to 8 minute 3Blue1Brown-style explainer. Read `video/steno-video-plan.md` in full, then the sources it names. Follow the nine-scene arc in section 2 exactly. For each scene write: the narration (spoken, plain English, curious and patient, short sentences, no jargon without a one-clause definition, no em dashes), the bookmarks that should trigger each animation, the visual beats in order, and the claims used with their source from section 4. Use no number that is not in section 4, and none of the withdrawn claims. Target 1,000 to 1,200 spoken words in total. Output `video/script.md`.

### 6.2 Scene-building prompt (one per scene)

> Build scene N from `video/script.md` as `video/scenes/sceneN.py` in Manim Community Edition. Import only from `video/style.py` for colours, fonts and helpers. Subclass `VoiceoverScene`; put each narration block in a `with self.voiceover(...)` context and fire animations on its bookmarks. Keep one persistent object per scene and transform it rather than replacing it. Geometry first, labels second; on-screen text is labels and numbers only. Stay inside the 16:9 safe area. Render with `-ql`, save frames every 3 seconds to `video/previews/sceneN/`, inspect them, and fix any overlap, clipping or unreadable label before reporting. Report the render time and the frames checked.

### 6.3 Review prompt

> Review the rendered video and `video/script.md` against `video/steno-video-plan.md`. For every number spoken or shown, confirm it matches section 4. Flag any withdrawn claim, any on-screen sentence that duplicates the narration, any text overlap or clipping in the preview frames, and any em dash. Output findings with the scene, timestamp and a fix.

## 7. Decisions needed before building

1. **Voice.** Local and private: macOS `say` (free, robotic) or Kokoro (open-source, runs locally, good quality, one model download). Or a cloud voice (OpenAI or edge-tts), which sends the script text to an external service.
2. **Length.** Six to eight minutes as planned, or a two-minute cut first as a pilot.
3. **Audience.** Internal leadership (as planned), or broader engineering.
