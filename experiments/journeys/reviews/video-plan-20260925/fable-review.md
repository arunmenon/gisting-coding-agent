<!-- Fable (claude-fable-5-1) review of video/steno-video-plan.md, read-only, 2026-09-25. Verbatim. -->

**Verdict.** The arc is right in outline and the claims register is numerically accurate, but the plan is not yet buildable as written: it relies on Manim features that need LaTeX (DecimalNumber, axis numbers), on manim-voiceover bookmarks that need a speech service with word timing or a Whisper install, and on a `style.py` and voice service that do not exist. Several register entries drop qualifiers the paper carries, and scene 7 spends the cap-lifted H200 numbers before scene 8 explains the cap. Scene 8 is the right call for this audience and belongs where it is, but it should absorb the heavy-load numbers rather than follow them.

**V-1: Scene 7 uses "cap lifted" H200 figures before the cap has been introduced. Severity: major. Section: 2.**
Evidence: register row "H200 heavy load, cap lifted" is placed in scene 7; the cap only appears in scene 8. J11 log 7.4 and 7.5 also say the uncapped c=256 cells are "a measurement of overload behaviour" and the ratios "are not portable". Edit: scene 7 carries H100 only plus "H200 level at peak"; scene 8 ends with the uncapped 128 and 256 numbers as what the corrected instrument showed, spoken as one run per condition, with the awkward fact that lifting the cap lowered throughput in three of four cells.

**V-2: "Keeping them raw fixes it" overstates Table 3. Severity: major. Section: 2 and 4.**
Evidence: paper 5.5: "Retraining, a changed training pool, and a new evaluation host accompany the repair, so the improvement is not attributable to the rule alone"; excluding the defective probe it is 11/15 to 15/15 with the teacher at 15/15; "one residual invented-path event was observed". The deck carries all three. Edit: register row becomes "11/16 to 16/16 (11/15 to 15/15 excluding one defective probe); retraining, pool and host also changed; one path error remained", and scene 6's idea line reads "keeping them raw, plus retraining, brought it level".

**V-3: The register lacks a "must say" column, so qualifiers will be lost in narration. Severity: major. Section: 4.**
Evidence: paper 5.6 key callout: "finite-window replay measurements on one hardware class... do not establish deployment capacity or savings per successful coding task"; the 2x is "each arm's own" p95 criterion (Codex F-1-2: a common 9 s threshold gives 1.33x); the +44% compares peaks at 16 and 32 sessions; Limitations: easy suite overlaps training data, single runs. Scene 5's "Scores held at every ratio" and scene 7's "What it buys" have none of this. Edit: add a fourth column with the spoken qualifier per row, and rename scene 7 "What the replay showed".

**V-4: Preamble row is mis-sourced. Severity: minor. Section: 4.**
Evidence: 17,540 (trimmed, 15,994 schemas) is in 3.1 and Table 1; 21,109 and 0.72 are in 5.1 and Figure 7; "over 90 percent tool schemas" is Section 1. Section 4.3 is the span method with no such figure. Note 9.4k is the Table 2 pre-fix checkpoint; the corrected 8:1 reads about 10.4k against 25.5k on the hard suite. Edit: correct sources; add the 10.4k note so the script does not pair 9.4k with the hard-suite fix.

**V-5: Scene 8's visual can re-imply a withdrawn mechanism. Severity: minor. Section: 2 and 4.**
Evidence: paper 5.6 reports 137 versus 126 resident as one run, "consistent with KV saturation", cause "unestablished". Needles moving to different values, with "the full prompt fell as the cache filled" narration, reads as "the gist fits more sessions". Edit: add to the withdrawn list "any stated cause of the throughput gap, including cache saturation and fits-more-sessions"; needles land on "more than 100", not on arm-specific values.

**V-6: Scene 9 implies the self-improvement loop is running. Severity: minor. Section: 2.**
Evidence: steno-capability.md marks B8 and B10 (triage, lessons, gated promotion, proposer) unbuilt; the deck separates "Runs today" from "Bounded self-improvement". The Jetstream pilot is "subject to validation". Edit: scene 9 idea line: "the loop runs the suite today; four bounded self-improvement mechanisms are designed; a Jetstream harness is the proposed next pair". Add one beat for the deck's "Not yet" ledger.

**V-7: The arc omits deployment. Severity: minor. Section: 2.**
Evidence: paper contributions: proxy-side substitution, conditional template, sampling mask, "no patch to the inference engine"; the shorthand ships as vocabulary rows. This is the part leadership will ask about. Edit: give scene 4 a closing beat: new rows ship in the model; a proxy swaps the span; the agent and engine are unchanged.

**V-8: "No LaTeX" conflicts with the Manim objects named. Severity: major. Section: 3 and 6.2.**
Evidence: in Manim CE, `DecimalNumber` and `Integer` default to `mob_class=MathTex`; `Axes`/`NumberLine` tick labels and `BarChart` labels render through the same path. Scene 7's curves and every animated number would fail on this machine. Edit: style.py rule: `DecimalNumber(..., mob_class=Text)`; axes built with `include_numbers=False` and hand-placed `Text` ticks (or `label_constructor=Text`); ban `Tex`, `MathTex`, `Brace` labels; lock and badge icons drawn from primitives, not emoji glyphs.

**V-9: Bookmarks need timing data the chosen voices cannot give. Severity: major. Section: 5 and 7.**
Evidence: manim-voiceover ships azure, coqui, elevenlabs, gtts, openai, pyttsx3 and recorder services; bookmarks on non-Azure services require Whisper transcription (a torch install). macOS `say` and Kokoro are not services; pyttsx3 file export is unreliable on recent macOS. Edit: write a small `SpeechService` subclass that calls `say -o` (or Kokoro) and converts with ffmpeg; drop bookmarks and use one short `voiceover` block per beat; state this in prompt 6.2 and in section 5.

**V-10: Prompt 6.2 assumes files and settings that do not exist. Severity: major. Section: 6.**
Evidence: `video/style.py`, the voice service, font names, resolution flags and the frame-extraction command are unspecified; Pango falls back silently on a missing font. Edit: add a step 0 prompt: create style.py (palette, named macOS fonts such as Georgia and Menlo verified via `manimpango.list_fonts()`, `fit_width`, `dim_others`, safe-area constants), install `manim manim-voiceover` in a venv, and render a ten-second smoke scene with audio and `.srt` (`create_subcaption=True`) before any story scene. Specify `-r 1920,1080 --fps 30` for finals (`-qh` is 1080p60 and doubles render time) and `ffmpeg -vf fps=1/3` for previews.

**V-11: Weak visuals. Severity: minor. Section: 2.**
Scene 3's "ribbon folds" is hard to animate legibly; use a `VGroup` of 64 small squares transformed into 8 glowing ones. Scene 4's converging distributions: two `BarChart`s of top-k probabilities with y numbers off, one `Transform`. Scene 9's four badges will clutter at 1080p; show them as one row of labels at font size 28 or larger.

**Decisions.**
Voice: `say` for every iteration render, Kokoro for the final; the script contains internal numbers, so no cloud service. Pilot: not a separate two-minute story; render scenes 1 and 8 end to end first, which exercises the pipeline and the hardest visual for a few hours' work. Audience: internal leadership only; the Codex review still rates the capacity claim a hypothesis, and a broader cut would need heavier qualification.

**Three edits first.** (1) Move the cap-lifted numbers into scene 8 and add the qualifier column to the register (V-1, V-3). (2) Add the LaTeX-free rules and the custom `say` service without bookmarks to section 5 and prompt 6.2 (V-8, V-9). (3) Add the step 0 style.py and smoke-scene prompt (V-10).
