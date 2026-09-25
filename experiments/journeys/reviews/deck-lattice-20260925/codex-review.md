The deck is not ready to send. It breaches the naming-only requirement, overstates portability, and adds serving-boundary detail to the Jetstream proposal. Its quality summary overgeneralises the results, and its 2x headline conceals the definition of the latency objective. The corrected price arithmetic holds, but unsupported causal statements remain.

Reviewed read-only at `a016efd`; the tracked deck, generators and paper match that commit. I inspected the PowerPoint’s slide and chart XML and compared it with the supplied extraction and HTML. I did not render the slides, so visual clipping and projection readability remain unverified.

D-1: Slide 3 elaborates existing Lattice tracks. Severity: blocking. Slide: 3.

> “Meta-harness: Adapter that routes different harnesses to underlying models.”  
> “Adaptive routing: Research track.”  
> “Model distillation: Research track.”

Requirement 1 says to name these tracks without elaborating. The adapter definition directly violates it; the research-status labels are also unnecessary descriptions. No numbers are assigned to the other tracks.

Suggested replacement: “Existing Lattice tracks: meta-harness, adaptive routing and model distillation.”

D-2: Reuse across untested pairs is presented as established. Severity: blocking. Slide: 5, 11, 12.

> “REUSED AS IS: Training loop, proxy, evaluation harness, and the automated GPU lab that runs them.”  
> “Swapping in a new harness or model changes the inputs, not the machinery.”  
> “Shows the recipe carries.”

Only Claude Code with Qwen3.8-27B was tested. The paper’s limitations explicitly make the span dependent on client version, plugins and tool configuration. No second pairing establishes unchanged proxy, training or evaluation machinery. “Shows” also presupposes the outcome of the proposed experiment.

Suggested replacement: “The existing lab is intended to support another pairing; the next experiment will establish what transfers and what needs adaptation.”

On slide 12, replace “Shows the recipe carries” with “Tests whether the recipe carries.”

D-3: Jetstream’s proposed placement acquires prohibited implementation detail. Severity: blocking. Slide: 12.

> “Proposed for the Jetstream inner loop, with rule-audit and write-target checks at the serving boundary.”

The checks are supported by the paper’s deployment recommendations, but requirement 4 explicitly limits the deck to proposing inner-loop placement without plumbing detail. Their location “at the serving boundary” exceeds that scope.

Suggested replacement: “Subject to validation, propose a guarded trial in the Jetstream inner loop.”

D-4: The established quality claim is false across the suites. Severity: blocking. Slide: 10.

> “Equal task scores at every ratio on our suites.”

Paper Table 2 reports 12/12 at every ratio on the **easy suite**. Table 3 reports hard-suite scores of 12, 11, 11 and 12 out of 16 before the repair, against a teacher score of 15/16. Only corrected 8:1 reached 16/16 against the same-host teacher’s 16/16.

Suggested replacement: “All four ratios scored 12/12 on the easy suite; corrected 8:1 matched the same-host teacher on the hard suite.”

D-5: The 2x headline does not identify target rates or separate latency thresholds. Severity: major. Slide: 2, 7, 10.

> “2x the request rate within the latency target”  
> “18 → 36 req/min”

The short-replay qualification is present, but “the latency target” suggests one common service objective. Paper Figure 9 and Table 5 use twice **each arm’s own** unloaded median, approximately 8.5 seconds for full and 8.0 seconds for gist. The raw B3 runs contain measured-window arrival rates of 14.67 and 30.00 req/min at the selected targets, not 18 and 36.

The earlier review also showed that a common nine-second threshold selects target rates of 27 and 36, a 1.33x comparison. The 2x arithmetic is conditional on the chosen criterion.

Suggested replacement: “In short replays, the highest tested target arrival rate passing each arm’s relative latency threshold doubled from 18 to 36 req/min.”

Keep a compact definition of the thresholds beside that claim.

D-6: The token range is incorrectly attached to the whole compression sweep. Severity: major. Slide: 6.

> “Every compression ratio matched the full prompt on the task suite, while input per turn fell from ~24k to ~9–11k tokens.”

Paper Table 2 gives 24,258 tokens for the teacher, then 16,083, 11,410, 9,395 and 8,245 for 2:1, 4:1, 8:1 and 16:1. The displayed range excludes both endpoints of the sweep. “More than halved” on slide 2 and “Half to two thirds fewer” on slide 10 likewise need an identified operating point.

Suggested replacement: “All four ratios scored 12/12 on the easy suite; at 8:1, input per turn fell from 24.3k to 9.4k tokens.”

D-7: The path repair is given more causal certainty than the evidence supports. Severity: major. Slide: 6, 15.

> “Fixing that took a harder suite from 11/16 to 16/16.”  
> “Keeping session-specific values raw restored the score 11/16 → 16/16 at 8:1.”

Those scores are recorded, but paper Table 3 explicitly says retraining, a changed training pool and a new host accompanied the repair. One probe was defective; excluding it gives 11/15 to 15/15. One residual invented-path event remained. The paper therefore does not attribute the entire improvement to the rule alone.

Suggested replacement: “After excluding session values and retraining, corrected 8:1 scored 16/16; other run conditions also changed, and one path error remained.”

Put the defective-probe qualification in appendix C.

D-8: The TCO sentence turns an observed association into a general causal result. Severity: major. Slide: 3.

> “The model reads fewer tokens on every agent call, so the same GPU does more work.”

The paper establishes fewer input tokens and higher observed H100 replay throughput. It does not establish their causal mechanism or a general throughput benefit: the H200 peak comparison is roughly unchanged. “Every agent call” also ignores child sessions that the paper says remain unswapped.

The TCO link should stay, but it needs to distinguish the proposed economic benefit from measured results.

Suggested replacement: “Gisting targets serving cost by shortening repeated prompts; the H100 replay showed higher throughput, while savings per successful task remain unproven.”

D-9: Slide 13 reintroduces an unsupported architecture explanation. Severity: major. Slide: 13.

> “The model mixes 16 full-attention layers with 48 linear-attention layers, which is why its behaviour under load differs from a standard transformer.”

The layer counts match the paper. “Which is why” does not. Paper Section 6 explicitly treats the layer mix as motivation for an expectation, not a confirmed explanation, and says the cross-model comparison is uncontrolled.

The specific withdrawn recurrent-state residency ceiling does not reappear, but this sentence preserves causal certainty around the architecture.

Suggested replacement: “The model has 16 full-attention and 48 linear-attention layers; their contribution to the observed throughput difference has not been isolated.”

D-10: The deck predicts properties of every future harness without evidence. Severity: major. Slide: 4, 15.

> “Any harness that exposes tools pays a version of this...”  
> “Every new harness and model pair will hit this boundary...”

The study covers one harness and model pair. The paper itself names tool selection and lazy schema loading as alternatives to sending the same full catalogue. Future pairs must be examined for fixed and dynamic content, but they have not been shown to incur this repeated overhead or exhibit this failure.

Suggested replacement: “For each new pair, measure the repeated prompt and check which session-specific values must remain raw.”

D-11: Additional quality risk at 16:1 is asserted without a demonstrated comparison. Severity: major. Slide: 6.

> “16:1 bought only about 60% of the serving gain for more risk.”

The gain fraction is correct: 26.5625% divided by 43.75% is 60.7%. “For more risk” is not an observed result. The easy-suite scores tie, and the serving checkpoints differ in span treatment and training history, as the earlier review records.

Suggested replacement: “We selected 8:1: the tested 16:1 checkpoint delivered about 61% of its peak-throughput improvement.”

D-12: The next-pair cost claim lacks an estimate, and the ask lacks a bounded decision. Severity: major. Slide: 11, 12.

> “The next pairing is cheap to try.”  
> “Run the experiment suite...”  
> “Held-out tasks, repeated runs, and quality checked at production load.”

The repository supports the existence of the automated controller and spending controls. It does not establish the total effort or cost of adapting to an untested pair. A watchdog limits exposure; it does not quantify engineering effort.

The ask names activities but supplies no selected pair, accountable owner, spending limit, review date or measurable pilot gate.

Suggested replacement: “Approve one next-pair evaluation, with the pair, owner, budget cap and review date agreed before launch; use held-out quality, sustained-load performance and cost per successful task to decide on a pilot.”

D-13: Jetstream’s use of different harnesses is an unsupported programme detail. Severity: minor. Slide: 9.

> “The Jetstream inner loop takes a ticket to a PR through coding agents on different harnesses.”

The author supplied ticket-to-PR scope, but did not establish that Jetstream currently uses different harnesses. I found no supporting journey or paper statement.

Suggested replacement: “We propose trialling gisting in Jetstream’s ticket-to-PR inner loop, one harness and model pair at a time.”

D-14: The serving caveat omits material limits behind the cost interpretation. Severity: major. Slide: 7, 13.

> “The gain comes on top of prefix caching.”  
> “The throughput figures measured below that limit stand.”

Both statements have support, but their presentation can imply that the client-limit correction clears the benchmark more broadly. The remediation order explicitly preserves the other review findings. The benchmark uses fixed 200-token outputs, does not score quality at load, and has uncontrolled prefix-cache asymmetry. The main flow needs a short qualifier; appendix A can hold the remaining measurement limitations.

Suggested replacement: “The peak difference survives the client-limit correction; these short, fixed-output replays did not measure task quality at load or isolate prefix-cache effects.”

D-15: HTML and PowerPoint differ in evidence annotations. Severity: minor. Slide: 7, 11, 15.

> HTML only: “full collapses (KV 100%)”  
> HTML only: “random arrivals”  
> HTML only: “verify every swap”

Both versions contain the same 15 slides and matching numerical chart series. However:

- Slide 7’s PowerPoint omits the HTML’s KV annotation and random-arrival label. Its chart title adds “H100”; both identify three repeats.
- Slide 11’s PowerPoint omits “verify every swap.”
- Slide 15 changes “writes to the right place” to “writes correctly,” broadening the wording slightly.
- Slide 7 changes “cost comparison between the two cards” to the more precise “per-dollar comparison.”

The supplied extraction matches the PowerPoint slide text, but its chart placeholder hides these chart-level differences.

Suggested replacement for the slide 7 caption in both versions: “H100 replay, mean of three repeats; throughput declined beyond the observed peak.”

Use “writes to the intended path” in both versions of slide 15.

D-16: The main flow spends too much space restating context and machinery. Severity: minor. Slide: 2–5, 10–12.

> “The answer in four lines”  
> “A new pillar under Lattice”  
> “Four steps, most of them reusable”  
> “The next pairing is cheap to try”

Twelve main slides are viable, and run-level results are largely absent. The density problem is repetition: placement appears on slides 1–3 and 12, the ask on 2 and 12, and the evidence summary on 2 and 10. Slide 5 explains a technique the CTO already knows; slide 11 lists operational controls without establishing next-pair effort.

Condense slides 4–5 around the span finding and mandatory per-pair rerun. Move the detailed lab controls to the appendix. Use the recovered space for the bounded decision and TCO measurement plan.

Suggested replacement: “For the next pair, rerun the span study and experiment suite, then measure quality and cost per successful task.”

Numerical verification: the model identifier, four ratios and easy-suite scores match the paper. The ~16,000 schema tokens, >90% share and ~1.3k corrected instruction tokens match Section 4.3; 17.5–21k summarises earlier span configurations, while 0.72 is the mean across eight logged sessions, not a universal session fraction. All 16 plotted throughput values reproduce from the raw H100 runs after rounding, and 42.6667 to 61.3333 gives +43.75%. The 100-connection correction reproduces from J11, and the 16/48 layer counts match the paper. Slide 14’s four values, 16.16, 23.23, 23.38 and 22.83, reproduce using quoted prices of $2.64/h and $3.65/h; it explicitly rejects established cheaper-card substitution.

House style: zero em dashes in the HTML and PowerPoint XML. Replace “attacks both costs at once” on slide 8 with “aims to reduce model size and prompt length” for plain English.

Requirement checklist:

1. **Not met.** Slide 3 defines the meta-harness and labels the other tracks “Research track.” No other-track numbers appear.
2. **Met.** “Alongside the meta-harness, adaptive routing and model distillation tracks” states placement without inventing integrations. No gisting-to-meta-harness or adaptive-routing integration sentence remains.
3. **Met.** Slide 8 says “Distil first, then gist the distilled model” and explicitly labels it “proposal · not yet tested.”
4. **Not met.** Slide 9 proposes inner-loop placement, but slide 12 adds checks “at the serving boundary.” Outer-loop and memory-track material are absent.
5. **Met.** Slide 5 explicitly says: “The whole experiment suite, span study first, runs again for each harness and distilled-model pair.”
6. **Not met.** “REUSED AS IS” and “changes the inputs, not the machinery” present untested portability as established.
7. **Met.** The white paper was used only as evidence. No files were changed.
