# Review brief: Steno explainer video plan

Read-only. Do not create or modify files. Output your review as your final answer.

Review `video/steno-video-plan.md`: a production plan and prompts for a 6 to 8 minute 3Blue1Brown-style narrated explainer, generated with Manim Community Edition and a synced voiceover, about this repository's gisting research and the Steno capability built from it. The audience is engineering leadership who know LLMs and coding agents but not gisting.

Sources the video must be faithful to: `Gisting-NeurIPS-paper.html` (the white paper), `steno-capability.md`, `steno-design.md`, `experiments/journeys/j10-bench/journey.md`, `experiments/journeys/j11-conn/log.md`, and the correction trail under `experiments/journeys/reviews/` (notably `review-20260915T073918Z-codex.md` and `findings-20260915-j11-remediation.md`). The deck (`Gisting-CTO-deck.html`) is the current approved framing.

Local environment facts: ffmpeg, cairo and pango are installed; Manim and LaTeX are not; macOS `say` exists; no GPU is needed.

Assess, concretely:

1. **Story.** Does the nine-scene arc teach the idea in the right order for this audience? Is anything missing, redundant or mis-weighted? Is scene 8 (the connection-cap correction) the right call for this audience, and is it placed well?
2. **Fidelity.** Check every entry in the claims register (section 4) against the sources: value, qualifier and wording. Flag anything overstated, mis-sourced, or missing a qualifier the paper carries. Flag any withdrawn claim the arc could imply even if not stated.
3. **Visual feasibility.** For each scene's core visual, is it achievable in Manim Community Edition without LaTeX, in reasonable effort, and will it read at 1080p? Suggest a simpler or clearer visual where one is weak.
4. **Pipeline and prompts.** Are the three prompts in section 6 specific enough to get good results from a coding agent? What will go wrong first in practice (voiceover timing, layout collisions, render time, font availability, dependency install), and what should the plan say to prevent it?
5. **Decisions.** Give your recommendation on voice, pilot length and audience, with reasons.

Output: a verdict of at most four sentences, then findings as `V-<n>: <one line>. Severity: major | minor. Section: <n>.` with evidence and a concrete edit to the plan. End with the three edits you would make first. No praise. No em dashes.
