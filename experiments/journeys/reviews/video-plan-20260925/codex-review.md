The plan needs revision before production: its numbers largely reproduce, but the arc drops qualifications that materially change their meaning. It risks implying general quality parity, proven deployment capacity, and completed Steno capabilities. Keep the correction scene, shorten it, and connect it directly to what the serving results establish. All nine visuals are feasible in Manim CE without LaTeX, but the current numeric-rendering and voiceover instructions can fail immediately.

V-1: The source list and prompts can reintroduce superseded claims. Severity: major. Section: 1.

**Evidence:** The J10 journey still asserts a recurrent-state ceiling, turnover mechanism, and obsolete price comparison. The correction trail withdraws these; even J11 log §7.2 states a stronger causal explanation than the corrected paper permits.

**Edit:** Explicitly list the approved deck and named reviews. State that corrected paper wording and reconciled reviews govern measurement claims, the deck governs framing, and journey narratives are historical evidence. Require prompt 6.1 to flag conflicts rather than choose whichever source sounds clearest.

V-2: The opening needs the deployment boundary and caching baseline. Severity: major. Section: 2.

**Evidence:** Paper §§2 and 5.1 describe a reusable learned prefix for a particular configuration, with prefix caching already enabled. The deck explicitly limits applicability to models whose weights the operator hosts.

**Edit:** Introduce Steno by name in scene 1 and say: “We studied one coding-agent and self-hosted model pair.” In scenes 2–3, explain that these are trained embedding rows for a fixed preamble, not a textual summary or an arbitrary-context compressor. Mention prefix caching before presenting the benefit, so “re-read” does not imply all prefix computation repeats.

V-3: The fixed-preamble row combines different span configurations without identifying them. Severity: minor. Section: 4.

**Evidence:** The rounded 17.5k–21k range is supported, but paper §3.1 gives 17,540 before the verbatim correction, §5.1 gives 21,109 for the full catalogue, and Table 1 gives 17,343 for the corrected compressed span. “Over 90% tool schemas” is supported.

**Edit:** Say “approximately 17.5k–21k across measured catalogue/span configurations,” cite §§3.1 and 5.1 plus Table 1, and distinguish the corrected span. Do not depict this range as variation within one fixed configuration.

V-4: The 0.72 claim has the right value but an imprecise denominator. Severity: major. Section: 4.

**Evidence:** Paper §5.1 and Figure 7 report the mean integrated static share across eight full-catalogue sessions: static tokens × turns / total session input tokens. This is not a fraction of wall time, serving cost, or one prompt’s composition.

**Edit:** Rename it “Mean share of cumulative input attributable to the static span across eight logged sessions: 0.72.” Cite §5.1/Figure 7 and explain that the share declines as history grows. Scene 2 should show session share separately from schema/rule composition.

V-5: Scene 5 conflates the easy-suite token reduction with general quality preservation. Severity: major. Section: 4.

**Evidence:** Table 2 supports 24,258 → 9,395 input tokens per turn and 12/12 at all four listed ratios. Its caption and paper §§4.5 and 7 qualify these as single runs on small, partly reused tasks, with training caps and subsets changing between runs. The corrected hard-suite comparison is approximately 25.5k → 10.4k, not 24.3k → 9.4k.

**Edit:** Label both register entries “easy-suite development runs.” Replace “Scores held at every ratio” with “Every tested ratio scored 12/12 on this easy suite.” Keep “single runs; partly reused tasks” visible, and do not carry the easy-suite token bar forward as the corrected checkpoint’s universal result.

V-6: “The one failure” and “keeping them raw fixes it” overstate the path repair. Severity: major. Section: 2.

**Evidence:** Paper Table 3 supports the recorded 11/16 → 16/16, but excluding a defective probe gives 11/15 → 15/15. Training pool and evaluation host changed alongside retraining; one invented-path event remained. Paper §5.8 also describes other unscorable experiments.

**Edit:** Rename scene 6 “A boundary failure.” Expand the register with the corrected denominator, changed conditions, and residual event. Narrate that the path tasks passed after exclusion and retraining, without claiming the rule alone caused all gains or eliminated path errors.

V-7: The H100 row needs the exact meaning of “2x” and the replay limits. Severity: major. Section: 4.

**Evidence:** Paper §5.6 supports 42.7 → 61.3 req/min, rounded +44%. The 2x result is the highest tested **target arrival rate** passing each arm’s own criterion, 18 versus 36 req/min, with thresholds approximately 8.5 and 8.0 seconds. The September 15 review identifies short windows, repeated arrival seeds, gist-only tuning, and uncontrolled cache history.

**Edit:** Use “Short, fixed-output H100 replays: twice the highest tested target arrival rate passing arm-relative thresholds; +44% observed peak throughput.” State that caching was enabled, quality at load was not measured, and sustainable capacity was not established. Scene 7’s singular “the latency target” must become “each arm’s threshold.”

V-8: The H200 peak values support a descriptive tie, not established equivalence. Severity: minor. Section: 4.

**Evidence:** Paper §5.6 supports 85.3 full versus 83.3 gist req/min, using H100-selected settings and two repeats. It explicitly warns that the selected peaks come from curves with unequal variability.

**Edit:** Say “Similar observed best points under H100-selected settings; two repeats with unequal variability.” Identify the arm order and avoid an equality sign or a precisely established zero difference.

V-9: The H200 heavy-load row omits conditions that prevent generalization. Severity: major. Section: 4.

**Evidence:** J11 §6 confirms all four rounded values: 47.0/80.7 at 128 and 46.3/56.7 at 256. These are offered concurrent requests, one run per condition, with the connector limit raised to 512. J11 §8 identifies overload at 256, unequal cache hit rates, and no quality measurement.

**Edit:** Add those conditions and label the derived gains approximately 1.7x and 1.2x at the respective points. Replace “under heavy load” as a general promise with “at these two tested overload points.”

V-10: Scene 8 omits the correction’s most consequential operational result. Severity: major. Section: 2.

**Evidence:** The register’s 100 and 123–137 are correct as **maximum sampled running-request counts**, not precise hardware ceilings. The remediation order §2.4 requires disclosing that lifting the cap reduced throughput in three of four comparisons. The corrected paper leaves the throughput mechanism unestablished.

**Edit:** Keep scene 8 immediately after scene 7, but limit it to roughly 25–35 seconds. Say that external review exposed the client cap, the follow-up invalidated the ceiling explanation, removing the cap often reduced throughput, and the lower-load H100 peak arithmetic survives with other limits intact. Add these qualifications to the register. Replace the struck-through old mechanism with “Explanation withdrawn,” avoiding a confident animation of a claim the plan otherwise forbids.

V-11: The closing scene overstates implementation status and omits the leadership decision. Severity: major. Section: 2.

**Evidence:** `steno-capability.md` records offline backend verification, a J11 dry run whose span gate fails closed, pending live executor work, and uncompleted B8/B10 self-improvement mechanisms. The deck asks for a next harness/distilled-model pair, held-out validation, then a guarded Jetstream trial.

**Edit:** Separate “demonstrated on one pair,” “implemented but awaiting live verification,” and “planned.” Replace four active RSI badges with a brief planned-capability label. Show both harness and model adapters, then close on the deck’s staged ask. Describe Jetstream as a proposed trial environment, not an already selected next harness.

V-12: Scenes 1–3 need simpler geometry and explicit scale semantics. Severity: minor. Section: 2.

**Evidence:** All three are straightforward with rectangles, `Text`, and transforms, but a growing conversation can become illegible; a proportional bar can conflate denominators; literal folding suggests reversible compression.

**Edit:** Scene 1: show a few turns, then indicate repetition. Scene 2: use a composition bar plus a separate session-share display, with small segments labeled outside. Scene 3: transform a schematic ribbon into a shorter block while keeping the raw-value lane unchanged. Label 8:1 as the **selected span’s** ratio, not the whole request’s reduction.

V-13: Scenes 4–6 need to distinguish illustrations from measured results. Severity: minor. Section: 2.

**Evidence:** Scene 4’s training description matches paper §3, but the actual teacher target is cached, truncated, and renormalized; perfectly converging distributions imply stronger equivalence. Scenes 5–6 are visually simple but can turn development scores into assurances.

**Edit:** Scene 4: show one frozen model used in two passes, highlighted new rows, and schematic probability bars moving closer without becoming identical. Scene 5: use large score tiles labeled “easy suite.” Scene 6: use an abbreviated path with its changing component highlighted, then retain an amber residual-risk marker after the bypass. These require no LaTeX or elaborate effects.

V-14: Scenes 7–9 contain more information than their proposed visuals can responsibly carry. Severity: major. Section: 2.

**Evidence:** Scene 7 combines an arrival-rate criterion, H100 concurrency results, H200 peaks, and two J11 points. Section 4 supplies insufficient data to reconstruct curves. Scene 8’s gauge resembles a newly discovered ceiling; scene 9’s adapters, loop, and badges overload one frame.

**Edit:** Scene 7: use sequential paired bars unless the register gains exact plotted datasets and axis definitions; never fabricate smooth curves. Scene 8: animate a client gate opening, then show sampled counts as dots. Scene 9: reveal the adapter chain and validation roadmap in separate beats. All are reasonable-effort CE visuals that can read at 1080p.

V-15: The mandated numeric class contradicts the no-LaTeX requirement. Severity: major. Section: 3.

**Evidence:** `DecimalNumber` defaults to `MathTex`, so “plain Text only” does not prevent a LaTeX failure. [Manim reference](https://docs.manim.community/en/stable/reference/manim.mobject.text.numbers.DecimalNumber.html)

**Edit:** Require tested Text-based numeric rendering, including axis ticks and units. Avoid automatic TeX labels throughout shared helpers. Remove the requirement to count every number from zero: ratios and task scores are clearer as discrete labels, and unnecessary per-frame text updates add render work.

V-16: The pipeline needs a dependency and font smoke test before scene production. Severity: major. Section: 5.

**Evidence:** Manim is absent, and the plan specifies neither a tested dependency combination nor a speech-service implementation. Installed Cairo/Pango do not verify Python bindings. Generic font categories leave substitutions and glyph coverage uncontrolled.

**Edit:** Add a bootstrap stage with an isolated environment, pinned tested dependencies, named installed fonts and fallbacks, and a short render exercising text, numbers, arrows, audio, and captions. Use the Cairo renderer; no GPU is needed. This is the first likely operational blocker, followed by implicit LaTeX use and missing speech-service setup.

V-17: Voiceover contexts do not automatically fit animations to speech. Severity: major. Section: 5.

**Evidence:** The context waits when animation finishes early; animation durations still need explicit control. Bookmarks require timing information, not merely a list of trigger words. [Voiceover quickstart](https://voiceover.manim.community/en/stable/quickstart.html), [bookmark timing implementation](https://voiceover.manim.community/en/stable/_modules/manim_voiceover/tracker.html)

**Edit:** Specify `set_speech_service`, unique inline bookmark IDs, word-boundary generation or manually timed short clips, and explicit animation budgets between bookmarks. Generate and cache audio before final timing, detect overruns, and lock voice settings before final rendering. Neither `say` nor Kokoro should be presented as a configured integration merely because it can produce audio.

V-18: The three prompts lack enforceable scientific and production contracts. Severity: major. Section: 6.

**Evidence:** Prompt 6.1 freezes the arc and checks only registered numbers; 6.2 assumes shared helpers and audio setup exist; 6.3 can approve a faithfully reproduced but misleading register.

**Edit:** Add to 6.1 a source locator, required qualifier, evidence status, and duration for every claim, including nonnumeric ones. Give 6.2 the shared helper interface, speech configuration, exact render settings, and data inputs. Make 6.3 independently check primary sources, omissions, visual implications, capability status, audio synchronization, and the final export. Permit sourced chart ticks and illustrative labels, clearly distinguished from empirical claims.

V-19: Preview and export checks will miss transient collisions and synchronization defects. Severity: minor. Section: 5.

**Evidence:** Frames every three seconds can miss a brief overlapping transform; low-resolution previews cannot establish final-size readability. “Burned-in-free captions” is ambiguous, and concatenation requires consistent media settings and caption offsets.

**Edit:** Define minimum text size, measured text bounds, safe margins, caption space, and exact palette values. Inspect animation boundaries, watch each scene with audio, and check representative 1080p frames. Specify resolution, frame rate, audio format, clean MP4 versus optional subtitle track, and cumulative SRT offsets including cards. Give the teaser its own qualified script and timing pass.

V-20: Resolve the voice, pilot, and audience decisions around comprehension risk. Severity: minor. Section: 7.

**Evidence:** A 1,000–1,200-word script can crowd a patient six-minute treatment once pauses and visual holds are included. The intended audience needs the mechanism and decision boundary more than training internals or four RSI mechanisms.

**Edit:** Keep internal engineering leadership. Start with a two-minute pilot covering the repeated prefix, learned replacement, raw-value boundary, and one qualified result. Use installed macOS `say` for this timing prototype; for the final leadership version, prefer a human recording, with a short local synthetic-voice audition if automated narration is required. Set scene budgets from measured audio duration rather than word count alone.

The three edits I would make first:

1. Rewrite section 4 with exact scope, required qualifiers, source precedence, and the additional withdrawn implications identified above.
2. Rework scenes 6–9 around the residual path failure, bounded replay findings, concise correction, implementation status, and staged leadership ask.
3. Replace the assumed pipeline with a tested no-LaTeX audio smoke test, then produce the two-minute pilot before building all nine scenes.
