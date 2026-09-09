# Reviewer Brief: "Gisting a Coding Agent"

Hi, thanks for agreeing to look at this. Below is context and what I'd value most from your review. Please be as critical as a NeurIPS reviewer would be. I would rather hear the paper is not ready than have it read as overclaiming.

## What the paper is
A study of *gisting*: replacing the large fixed preamble (behavioural rules + tool schemas) that a coding agent prepends to every model call with a small set of learned token embeddings, trained by self-distillation with all base-model weights frozen. The question is whether a technique demonstrated on prose system prompts transfers to a schema-dominated coding-agent prompt, on a self-hosted 27B hybrid linear-attention model (Qwen3.8-27B), served with no changes to the client or the inference engine.

## Framing I want you to hold me to
The paper deliberately calls itself a *development study, not a validated benchmark*. Every evaluation is a single run of small, partly reused, author-designed task sets; some suites overlap with training data; one suite guided the fix it later scores. An independent adversarial review was already run and its findings folded in. I do not want the writing to quietly drift back into benchmark-strength claims anywhere. If it does, flag the sentence.

## What I most want your judgment on
1. **Claim calibration.** Does any result read as stronger than a single-run, author-designed evaluation can support? Point to specific sentences.
2. **The architecture argument.** The central technical claim is that on a hybrid-attention model (full attention in only ~16 of 64 layers) the benefit is throughput, not single-request latency, and that this was predicted from the layer mix before measurement. Is that reasoning sound, and is the evidence (Section 5.6, Table 3, Figure 8) sufficient for the claim as stated?
3. **The failure-and-fix result.** Dynamic values (paths, identifiers) compressed into the gist get reconstructed incorrectly; a pattern rule that keeps verbatim-critical content raw restores an 8:1 gist from 11/16 to 16/16. Is this convincing, or does keeping that content raw undercut the compression claim? Is the mechanism explained well enough?
4. **Negatives handled honestly.** Two experiments returned no usable score (a coverage suite invalidated by an infrastructure fault; a per-segment ratio sweep lost to harness faults). Are these reported the right way, or should they be cut vs. kept as null results?
5. **Novelty and positioning.** Given prior work on gist tokens, prompt compression, and the industrial report the paper compares against, is the contribution clearly delineated? Is anything miscredited or missing from related work?
6. **Reproducibility.** Could someone rebuild the method from Sections 3-4 and the appendix? What is missing?
7. **Figures and abstract.** Do the figures carry real information or decorate? Is the abstract's structure (four findings + two non-results) accurate to the body?

## Logistics
- Paper link: <PASTE ARTIFACT LINK HERE>  (I will grant you access.)
- Length is short by design; depth panels / appendix hold the reproducibility detail.
- Feel free to answer in whatever form is easiest: inline comments, a marked-up list, or prose. Severity tags (blocker / major / minor / nit) would help me triage.

Any verdict is welcome, including "this is not a paper yet, here is why."
