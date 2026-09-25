Steno explainer: narration script (v1)

Audience: internal engineering leadership. They know LLMs and coding agents,
not gisting. Tone: 3Blue1Brown. Curious, patient, plain English, one idea per
beat, no hype, no em dashes anywhere (narration, on-screen text, or notes).

Source precedence, applied throughout: measurement claims come from the
corrected white paper (`Gisting-NeurIPS-paper.html`) first, then the
reconciled reviews (`review-20260915T073918Z-codex.md`,
`findings-20260915-j11-remediation.md`); framing and capability status come
from the deck (`Gisting-CTO-deck.html`) and `steno-capability.md`; journey
narratives such as `j10-bench/journey.md` and `j11-conn/log.md` are used only
for historical detail already confirmed by the paper.

Only the numbers and claims in plan section 4 are used, each with its "must
say" qualifier. None of the forbidden implications (recurrent-state
residency ceiling, "turnover not headcount", any stated cause of the
throughput gap, cheaper-card substitution or fleet savings, general quality
parity, established capacity, savings per completed task, or the
self-improvement mechanisms described as running) appear anywhere below.

Voice speed for estimates: macOS `say`, Samantha, 175 words per minute
(2.92 words/second), the rate used in `video/voice.py` for iteration audio.

================================================================================
Scene 1: The re-read
================================================================================
Status: demonstrated on one pair (Claude Code, self-hosted Qwen model).
One idea: the agent re-sends the same fixed preamble on every call; prefix
caching already absorbs part of that cost. Steno is named here.

Beat 1.1
Narration: "Here is a coding agent, Claude Code, talking to a model we host
ourselves, a Qwen model. We looked closely at one pair like this."
Visual: A single agent icon and a single model icon, connected by a line.
Label: "one pair, studied closely" (illustrative pairing, not a claim from
section 4).
Claims used: none (framing only; sourced to steno-capability.md and the
deck for "one pair" framing).

Beat 1.2
Narration: "Turn one. The agent sends a long fixed block before it ever asks
its real question. Turn two, the same block again. Turn three, again."
Visual: Three or four turns shown left to right; before each turn, the same
fixed block (petrol) reappears, then a small new question block.
Claims used: none directly (sets up the fixed-block claim in beat 1.3).

Beat 1.3
Narration: "Across the configurations we measured, that fixed block runs
about seventeen and a half thousand to twenty one thousand tokens, and over
ninety percent of it is tool schemas, not conversation."
Visual: A repeat marker replaces the fourth full turn (not an ever-growing
conversation); the fixed block is labelled with its token range.
Claim: Fixed preamble, about 17.5k to 21k tokens, over 90% tool schemas.
Must say: "across the configurations we measured." Source: paper section 1,
section 3.1, Table 1 (17,540 trimmed), section 5.1 (21,109 full catalogue).

Beat 1.4
Narration: "Some of that cost is already absorbed by prefix caching. But
resending it, and re-processing it, still adds up. Steno is how we shrink
that block."
Visual: A caching icon dims part of the fixed block; the block visibly
shrinks to a small glowing plum shape, labelled "Steno": Steno is the
shrinking, not the block itself.
Claims used: none new (framing; "prefix caching already absorbs part" is a
qualification, not a numeric claim in section 4).

Estimated word count: 107 words. Estimated duration: about 37 seconds.

================================================================================
Scene 2: Anatomy of the tax
================================================================================
Status: demonstrated on one pair.
One idea: the block is mostly tool schemas. Separately, across eight logged
sessions the static span averaged 0.72 of cumulative input, falling as
history grows.

Beat 2.1
Narration: "What is actually inside that fixed block? Mostly tool schemas:
the descriptions of every tool the agent could call. A smaller part is
standing rules and instructions."
Visual: A composition bar splits into segments (tool schemas, rules), each
segment labelled outside the bar, not inside it.
Claim: reuses "over 90% tool schemas" from scene 1's claim register row.
Must say: "across the configurations we measured." Source: paper section 1,
section 3.1.

Beat 2.2
Narration: "Now a separate question: as a session goes on, how much of the
total input is this fixed block, versus everything that came before it?
Across eight logged sessions, it averaged seventy two percent of cumulative
input, and that share falls as the history grows."
Visual: The composition bar fades; a separate share display appears (a
single number, 0.72, with a downward-trending marker). The two displays are
never drawn as one bar.
Claim: Session share, 0.72. Must say: "mean share of cumulative input
across eight logged sessions; falls as history grows." Source: paper
section 5.1, Figure 7.

Estimated word count: 72 words. Estimated duration: about 25 seconds.

================================================================================
Scene 3: The shorthand
================================================================================
Status: demonstrated on one pair.
One idea: the fixed span becomes a small set of trained embedding rows, not
a text summary and not arbitrary-context compression. Per-session values
stay raw. 8:1 is the ratio for the selected span, not the whole request.

Beat 3.1
Narration: "Here is the idea. Take that fixed span and replace it with a
small set of trained rows, numbers the model learns to read the same way it
reads the original text."
Visual: 64 small squares (illustrative count, not a measured value)
transform into 8 glowing ones (plum), representing an 8 to 1 ratio.
Label: "illustrative, not a measured value" on the square count.
Claims used: none from section 4 directly here; the visual is illustrative.

Beat 3.2
Narration: "This is not a text summary, and it is not compressing whatever
context happens to be in the window. It is a fixed substitution, learned
once, for one specific span."
Visual: A crossed-out "summary" label and a crossed-out "arbitrary context"
label, dimmed to the side, to rule them out visually.
Claims used: none (conceptual clarification).

Beat 3.3
Narration: "Everything specific to a session, like file paths or recent
turns, stays raw and passes through unchanged."
Visual: A separate raw lane (copper) runs alongside the shrinking block,
untouched by the transformation.
Claims used: none.

Beat 3.4
Narration: "Eight to one is the ratio for that selected span, not for the
whole request that goes to the model."
Visual: The 8 glowing squares are labelled "8:1, selected span only," with
the raw lane pointedly left out of the ratio.
Claims used: the "8:1" ratio itself is only fully evidenced later (scenes 5
and 6, easy suite and hard suite); this beat is the definitional qualifier
plan section 2 calls for, not a new numeric claim.

Estimated word count: 99 words. Estimated duration: about 34 seconds.

================================================================================
Scene 4: Teaching it, and shipping it
================================================================================
Status: demonstrated on one pair (training) / implemented (the shipped
proxy path).
One idea: one frozen model is run twice, once with the full prompt and once
with the shorthand; only the new rows train. The rows ship in the model; a
proxy swaps the span; the agent and engine code are unchanged.

Beat 4.1
Narration: "To teach the shorthand, we freeze the model completely. We run
it once with the full prompt, and once with the shorthand standing in for
that span."
Visual: A lock icon closes over the model shape (drawn from primitives, not
an emoji).
Claims used: none (method description; sourced to the paper's training
method and to steno-capability.md; the plan's claims register does not
assign this a specific section number, so no section citation is invented
here).

Beat 4.2
Narration: "Only the new rows move. We nudge them until the model's two
probability outputs, one from each run, land close to each other."
Visual: A small block of new rows lights up next to the locked model; two
schematic probability bars move closer together without becoming
identical.
Claims used: none (method description, same sourcing note as 4.1).

Beat 4.3
Narration: "Once trained, those rows ship inside the model itself. A proxy
sitting in front of it swaps the long span for the short one. The agent and
the inference engine code do not change."
Visual: Closing beat: three icons in a row, agent, proxy, model, with the
proxy highlighted as the only new piece.
Claims used: capability status ("implemented" for the proxy path).
Must say: "the self-improvement mechanisms are planned" does not apply here
(that qualifier belongs to scene 9); this beat instead states plainly that
the proxy and shipped rows are implemented, not planned. Source:
steno-capability.md.

Estimated word count: 84 words. Estimated duration: about 29 seconds.

================================================================================
Scene 5: Does it still work
================================================================================
Status: demonstrated on one pair, easy suite.
One idea: on the easy suite, every tested ratio scored 12 out of 12, and at
8:1 the input per turn fell from 24.3k to 9.4k tokens.

Beat 5.1
Narration: "Before trusting this, we needed to know the agent still gets
the job done. On an easier suite of tasks, in single runs with partly
reused tasks, every ratio we tried, two to one, four to one, eight to one,
sixteen to one, scored twelve out of twelve."
Visual: Four large score tiles, one per ratio, labelled "easy suite," all
showing 12/12.
Claim: Easy-suite scores, 12/12 at 2:1, 4:1, 8:1, 16:1. Must say: "single
runs, partly reused tasks." Source: paper Table 2, section 4.5, section 7.

Beat 5.2
Narration: "And at eight to one, on this development run, the input per
turn fell from twenty four point three thousand tokens down to nine point
four thousand."
Visual: A token bar shrinks from 24.3k to 9.4k, labelled "easy suite,
development run."
Claim: Easy-suite tokens at 8:1, 24.3k to 9.4k per turn. Must say: "easy
suite, development run." Source: paper Table 2.

Estimated word count: 75 words. Estimated duration: about 26 seconds.

================================================================================
Scene 6: A boundary failure
================================================================================
Status: demonstrated on one pair, hard suite, after remediation.
One idea: session values baked into the shorthand once sent writes to an
invented directory; keeping them raw, together with retraining, brought the
harder suite back up to a comparable level; one path error remained.

Beat 6.1
Narration: "A harder suite of tasks found a real failure. When session
specific details got baked into the shorthand instead of staying raw, the
agent once wrote files to a directory that did not exist. It had invented
the path."
Visual: A path travels into the shorthand block and comes out wrong, drawn
as a broken line landing outside the model shape.
Claims used: none new (this is the failure narrative that motivates the
fix; the forbidden general-quality-parity implication is avoided by scene 6
being explicitly about a hard-suite regression, not a general claim).

Beat 6.2
Narration: "The fix was to keep those session specific values raw, outside
the shorthand, and retrain. On the corrected eight to one setup, after the
pool and the host also changed, the hard suite scored between eleven and
sixteen out of sixteen, eleven to fifteen out of fifteen if you set aside
one defective probe, with input around twenty five point five thousand
down to ten point four thousand tokens. One path error remained."
Visual: The raw lane (copper) routes the path around the shorthand
correctly; an amber residual-risk marker stays on screen through the end of
the scene.
Claim: Hard suite, corrected 8:1, 11/16 to 16/16 (11/15 to 15/15 excluding
one defective probe); input about 25.5k to 10.4k. Must say: "retraining,
pool and host also changed; one path error remained." Source: paper
section 5.5, Table 3.

Estimated word count: 112 words. Estimated duration: about 38 seconds.

================================================================================
Scene 7: What the replay showed
================================================================================
Status: demonstrated on one pair, replay conditions.
One idea: on an H100, short fixed-output replays with caching on reached
twice the highest tested arrival rate that passed each arm's own latency
threshold, and a +44% observed peak throughput; on an H200, similar best
points.

Beat 7.1
Narration: "We also replayed traffic to see how the shorthand behaves under
load. On an H100, with short, fixed-length replays and caching turned on,
the shorthand's arm passed its own latency threshold, about eight point
five seconds, at up to thirty six requests per minute. The full prompt's
arm, with its own threshold near eight seconds, passed at up to eighteen.
Twice the highest tested rate."
Visual: Paired bars in sequence, one pair per tested rate, not a smooth
curve. Only registered numbers are plotted.
Claim: H100 arrival rate, 18 to 36 req/min, highest tested target rate
passing. Must say: "each arm's own threshold, about 8.5 s and 8.0 s; short
fixed-output replays; caching on." Source: paper section 5.6.

Beat 7.2
Narration: "Looking at observed peaks rather than the pass or fail rates,
throughput went from forty two point seven up to sixty one point three
requests per minute, a forty four percent increase. This is what we
observed at these points. We did not measure quality under load, and we
have not established a capacity limit."
Visual: A single paired bar highlighting the peak values, labelled
"observed peak, not a ceiling."
Claim: H100 peak, 42.7 to 61.3 req/min, +44%. Must say: "observed peaks;
quality at load not measured; capacity not established." Source: paper
section 5.6.

Beat 7.3
Narration: "On an H200, using the same settings tuned for the H100, the
best points landed close together, eighty five point three against eighty
three point three requests per minute, across two repeats with unequal
variability."
Visual: A second paired bar for the H200, visually similar in height,
labelled "similar best points."
Claim: H200 peak, 85.3 vs 83.3 req/min. Must say: "similar best points;
H100-tuned settings; two repeats, unequal variability." Source: paper
section 5.6.

Estimated word count: 155 words. Estimated duration: about 53 seconds.

================================================================================
Scene 8: The instrument was wrong
================================================================================
Status: demonstrated on one pair, replay conditions, after external review.
Target length: about 30 seconds.
One idea: an external review found our load generator capped connections at
100; lifting the cap showed more than 100 sessions resident and withdrew
our explanation; it also lowered throughput in three of four cells; at the
two overload points tested, the compressed prompt held up better; cause
still open.

Beat 8.1
Narration: "A correction. Our own load generator capped connections at one
hundred, in both arms. Our earlier explanation used that number. It is
withdrawn."
Visual: A client gate at 100 opens; the old explanation text is struck
through and replaced with "explanation withdrawn," in place of the old
claim, not alongside it.
Claim: Connection cap, 100 resident in both arms capped. Must say: "maximum
sampled counts, not hardware ceilings." Source: paper section 5.6, J11 log
section 6.

Beat 8.2
Narration: "Cap lifted, sampled counts showed more than one hundred
sessions resident: one hundred twenty three to one hundred thirty seven."
Visual: Sampled counts appear as dots above the old line, labelled "more
than 100." The dots are not labelled per arm; they are a shared observation
across both arms.
Claim: Connection cap, more than 100 (123 to 137 sampled) uncapped. Must
say: "maximum sampled counts, not hardware ceilings." Source: paper section
5.6, J11 log section 6.

Beat 8.3
Narration: "Lifting the cap lowered throughput in three of four cells. At
two tested overload points, one run each, the compressed prompt held up
better: forty seven against eighty point seven at one hundred twenty eight
offered, forty six point three against fifty six point seven at two
hundred fifty six. Cause still open."
Visual: The two overload points shown as paired bars (plum ahead of
petrol), with a plain caption: "one run per condition; cause still open."
Claim: Cap lifted, overload points, 47.0 vs 80.7 req/min at 128 offered;
46.3 vs 56.7 at 256. Must say: "one run per condition; lifting the cap
lowered throughput in three of four cells; at these two tested points."
Source: J11 log section 6, section 7.4.

Estimated word count: 92 words. Estimated duration: about 32 seconds, close
to the roughly 30 second target in plan section 2.

================================================================================
Scene 9: From experiment to Steno
================================================================================
Status: mixed, stated explicitly per the ladder below.
One idea: demonstrated is one pair; implemented is the harness adapters,
shared span analysis, and a run loop with gates and verified teardown,
awaiting live verification; planned is four bounded self-improvement
mechanisms; proposed next is a harness and distilled-model pair, possibly a
Jetstream harness, then held-out validation, then a guarded trial.

Beat 9.1
Narration: "So where does this leave us? The pieces fit together as an
adapter chain: a harness adapter, a shared span analysis, and a model
adapter, the same shorthand idea we just walked through."
Visual: The adapter chain (harness adapter, shared analysis, model adapter)
drawn as one beat, one persistent object transformed rather than replaced.
Claims used: none new (structural summary of implemented components).

Beat 9.2
Narration: "Here is the honest status ladder. Demonstrated: one pair, the
agent and model we studied throughout this video. Implemented: the harness
adapters, the shared span analysis, and a run loop with gates and verified
teardown, though that loop is still awaiting live verification. Planned:
four bounded self-improvement mechanisms. Those are planned, not running."
Visual: A status ladder, three rungs (demonstrated, implemented, planned),
each labelled plainly; the planned rung is visually distinct (dimmer,
dashed) from the implemented rung.
Claim: Capability status, demonstrated, implemented, planned. Must say:
"the self-improvement mechanisms are planned." Source: steno-capability.md.

Beat 9.3
Narration: "What we are proposing next: a harness and a distilled model
pair, possibly a Jetstream harness, then held out validation, then a
guarded trial. Each step earns the next."
Visual: The closing card: a staged sequence of three cards (harness and
distilled pair, held-out validation, guarded trial), title card "Steno,
PAI" beneath.
Claims used: none new (forward-looking framing, sourced to the deck and
steno-capability.md; explicitly not claimed as already running).

Estimated word count: 115 words. Estimated duration: about 39 seconds.

================================================================================
Totals
================================================================================
Total narration word count across all nine scenes: 915 words.
Total estimated narration duration at 175 wpm: approximately 5 minutes 13
seconds of raw narration, before title card, end card, and the pacing
pauses and visual holds between beats (see plan section 5 step 2: each
scene's animation budget is set from measured audio, not word counts, so
the built scenes will run longer than narration alone). This word-count
estimate falls short of the 6 to 8 minute target in plan section 1 on
narration alone; reaching that target depends on title/end cards and
per-beat visual pacing added during the build step, and should be
re-checked against actual rendered audio once all nine scenes exist.

Note on scene 4's sourcing: the training method description (freeze the
model, run twice, train only the new rows) is not assigned a specific paper
section number in the plan's claims register (section 4). It is treated
here as method description rather than a registered numeric claim, and is
sourced generally to the paper's training methodology and to
steno-capability.md. If a specific section number is required before
recording, it should be confirmed against the paper before this scene is
built.
