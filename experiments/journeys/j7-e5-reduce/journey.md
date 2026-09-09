# Journey 7: Does how you average the loss matter?

*In everyday terms.* When grading a stack of essays, you can average each essay's score and then average the essays, or pool every sentence and average once. The first way gives a one-line essay the same weight as a ten-page one. Shopify said the first way made their model make things up.

**The uncertainty this retires.** E5, the loss-reduction ablation: batch-level versus per-response averaging of the KL, at the corrected 8:1 span.

## What we ran

Identical to the corrected 8:1 retrain (2,171 gist tokens, 1,494 examples, one epoch, learning rate 1e-3, 30k cap) except that the loss is averaged within each response first and then across the eight responses in a step. Hard exam and teacher rerun on the same box.

## What the GPU showed us

| Run | Held-out KL, init to final | Hard exam | Path writes correct |
|---|---|---|---|
| Batch-level (journey 5) | 0.0219 to 0.0088 | 16 of 16 | 3 of 3 |
| Per-response (this journey) | 0.0218 to 0.0107 | 14 of 16 | 3 of 3 |
| Teacher, same box | | 15 of 16 | 3 of 3 |

The per-response model's real miss was the Agent task: it researched with the sub-agent and never wrote the notes file. Its other miss is the defective delete probe, which the teacher also failed on this rerun. No invented paths, no malformed calls.

## What we now understand differently

Shopify's direction holds: batch-level averaging ends lower in KL and passes one more task. The magnitude here is mild, a 22 percent higher final KL and one task, not the hallucination they described. One plausible reason is that our responses vary less in length than a customer-facing agent's, so per-response weighting distorts less. With sixteen tasks and one run each, this is a lean, not a proof; batch-level stays the default.

## What it cost

5.4 hours at $1.228, about $6.60, plus about $0.50 on a first host that never accepted SSH.
