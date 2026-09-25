# Review request: the Lattice framing of the gisting CTO deck

Run read-only from the repository root, at commit `a016efd`. Emit your review to stdout.

## 1. Who this deck is for and what it must do

The audience is our CTO. He already knows about gisting: he is the person who sent us the Shopify blog post on the technique. He also already knows about **Lattice**, our umbrella initiative for anything related to AI cost optimization, and about its existing tracks. The deck does **not** need to explain gisting from first principles or explain what Lattice is.

The deck's job is to pitch this gisting work as **a new pillar within Lattice**, blended into the total-cost-of-ownership story, and to ask for the next step.

The deck should be **hybrid in density**: enough to show what we did and what we found, without run-by-run detail. Run-level material belongs in the appendix or the white paper, not the main flow.

## 2. The framing the author specified (treat these as requirements)

The author gave these instructions verbatim in spirit. Check the deck against each one.

1. **Lattice's existing tracks are to be named, not elaborated.** They are: the **meta-harness** (an adapter that routes different harnesses to underlying models, like a meta CLI), **adaptive routing**, and **model distillation**. Most are research tracks, so **no numbers** are to be quoted for them.
2. **Do not invent integrations between gisting and the other tracks.** The author explicitly rejected an earlier version that described how gisting could plug into the meta-harness and how it would interact with adaptive routing. Those were the deck-writer's own inferences and were removed.
3. **The only synergy to state** is: distil a model first, then run gisting on the distilled model. It must be framed as a proposal, not a result.
4. **Jetstream PDLC** is a separate programme with an inner loop (ticket to PR), an outer loop (vision, PRD, HLD and similar), and a memory track. The deck should only say, **as a proposal**, that gisting could be plugged into the **inner loop**. It should not go into the outer loop, memory, or how the plumbing would work.
5. **The span analysis must be made explicit as per-pair work.** The experiment in this repository was done for one pairing only: the Claude Code harness with the Qwen3.8-27B model. The deck must say that this experiment suite, starting with the span study, has to be **re-run for each harness and distilled-model pair**.
6. **Portability is a hope, not a result.** The recipe was proven on one harness and model pair. The deck may say it is designed to carry over, but must not claim it has been shown to.
7. **The white paper should not change.** Review only the deck.

## 3. What to read

| Path | What it is |
|---|---|
| `Gisting-CTO-deck.html` | The deck under review, HTML version (15 slides: 12 main, 3 appendix) |
| `experiments/journeys/reviews/deck-lattice-20260925/pptx_text.txt` | Text extracted from the PowerPoint version, slide by slide |
| `Gisting-CTO-deck.pptx` | The PowerPoint itself, if you can inspect it |
| `paper/build_deck.py`, `paper/build_pptx.py` | The generators for both versions |
| `Gisting-NeurIPS-paper.html` | The white paper: the source of truth for every number in the deck |
| `experiments/journeys/j10-bench/`, `experiments/journeys/j11-conn/` | Serving benchmark and its correction, with raw run files |
| `experiments/journeys/reviews/review-20260915T073918Z-codex.md` | Your own earlier review of the program's claims |
| `experiments/journeys/reviews/findings-20260915-j11-remediation.md` | The correction work order that followed it |

## 4. What to check

**A. Framing fidelity.** For each of the seven requirements in section 2, state whether the deck meets it, quoting the slide text that shows it. Flag any sentence that still describes how gisting would integrate with the meta-harness or adaptive routing, any description of the other tracks beyond naming them, and any sentence that presents the distillation synergy or the inner-loop placement as more than a proposal.

**B. Unsupported inference.** Flag every claim in the deck that is not traceable either to the white paper, to a journey record, or to the author's framing above. Pay particular attention to sentences that sound like findings but are actually design reasoning.

**C. Numerical and claim accuracy.** Verify each number in the deck against the white paper or the raw results. Check that the corrections from your 2026-09-15 review are respected: the withdrawn residency mechanism must not reappear; the per-dollar comparison must be on one consistent price basis and must not claim cheaper-card substitution; the headline throughput figures must carry an honest qualifier.

**D. CTO readability and density.** Is the main flow (slides 1 to 12) the right length and depth for a CTO who already knows the technique and Lattice? Is anything still too detailed for the main flow, or conversely, is something essential now missing, such as the TCO link? Is the ask concrete enough to act on?

**E. HTML and PowerPoint parity.** Do the two versions carry the same slides, the same claims and the same numbers? Report any divergence.

**F. House style.** No em dashes anywhere. Plain international English.

## 5. Output format

Open with a verdict of at most five sentences: is the deck ready to send, and if not, what blocks it.

Then findings, each in the form:

```
D-<n>: <one-line statement>. Severity: blocking | major | minor. Slide: <number>.
<Quoted deck text. What is wrong. The evidence or requirement it conflicts with. A suggested replacement sentence.>
```

Blocking means it must change before the CTO sees the deck. Major means it weakens the pitch or risks a factual challenge. Minor is polish.

Close with the requirement checklist from section 2, each marked met or not met.

Do not praise. Do not soften. If a slide is fine, one sentence saying so is enough.
