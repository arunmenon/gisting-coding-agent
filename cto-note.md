# Note to the CTO: what the last round of experiments settled

**Subject line suggestion:** Gisting benchmark results: one GPU, twice the sessions, and what it does to cost

---

Following up on the gisting work we discussed against the Shopify blog. The whitepaper had one throughput number in it from a single run, and it was the number you pushed on: is this a real capacity gain, or an artifact of how we set the server up. We spent the last week answering exactly that. Short version: the gain is real, it is bigger than we first reported, and it is a cost lever rather than a speed lever.

## What we ran

Six blocks of experiments on rented GPUs, 201 runs, zero failures, about 10 GPU-hours total.

1. **Tune the server first.** Your objection, correctly, would have been that we were comparing two arms on a badly configured engine. So we swept the serving configuration and picked the best one by throughput, then applied that same configuration identically to both arms. Our original paper number came from a throttled setup.
2. **Load curve.** Both arms driven at fixed concurrency from 1 to 256 sessions, three repeats each, arm order balanced so warm-up cannot favour one side. Run-to-run spread was under 1 percent.
3. **Realistic arrivals.** Requests arriving randomly rather than in lockstep, from 9 to 72 per minute, measured against a latency objective: 95th percentile end to end no worse than twice the unloaded median.
4. **Caching ablation.** The obvious challenge is that prefix caching already solves this. So we ran both arms with caching off to see how much of the gain caching was already capturing.
5. **Where the ceiling actually is.** We instrumented how many sessions the engine holds resident and how full its memory is, to explain the mechanism instead of asserting it.
6. **Different hardware.** The whole thing repeated on a larger GPU to test whether the result travels.

## What came back

Two numbers worth remembering, both on the H100-class card the paper used.

| Measure | Full prompt | With gist | Change |
|---|---|---|---|
| Sustainable load within the latency objective | 18 req/min | 36 req/min | 2x |
| Peak throughput | 42.7 req/min | 61.3 req/min | +44% |

The advantage widens as the box gets busier: about 1.1x at one session, 1.4x at eight, 1.65x at forty-eight. Past that the full-prompt arm collapses outright when its memory fills, while the gist arm keeps serving.

Three findings behind those numbers that matter more than the numbers.

- **It is incremental over caching, not redundant with it.** With prefix caching switched off, the gist arm runs 2 to 4.4 times the full-prompt arm. Caching absorbs a lot of the repeated preamble; the gist still adds 16 to 44 percent on top, and it is the part that survives when prefixes are not shared, which is the normal case across many concurrent users.
- **The mechanism is turnover, not headcount.** We expected the gist to let more sessions sit resident at once. It does not, past a point: on the larger card both arms held exactly the same number of resident sessions, and the gist arm still did 1.7 times the work. The shorter prompt makes each session finish sooner, so slots recycle faster. That is a better story for us than the one we had, because it does not depend on a memory argument that stops applying on bigger hardware.
- **The gain is proportional to how memory-constrained the hardware is.** On the larger card, at normal load, the peak gain vanished: minus 2 percent. It reappeared only under heavy pressure, up to 3.1 times at 128 sessions. We are reporting that plainly rather than leading with the favourable card.

## Why this is a cost lever

That last finding is the one with budget implications, and it cuts in our favour.

| Configuration | Throughput per dollar-hour |
|---|---|
| H100, full prompt | 16.2 req/min |
| H100, with gist | 23.2 req/min |
| H200, full prompt | 22.5 req/min |
| H200, with gist | 22.0 req/min |

Read the middle two rows together. The cheaper card running the gist matched the more expensive card running the full prompt, on throughput per dollar. Gisting is not a way to make an expensive GPU faster. It is a way to keep serving the same load on the cheaper GPU, or to defer the upgrade. On a fleet, that is the line item.

Practical consequence: the tuning is per hardware generation, not set once. Our larger-card numbers used a configuration tuned for the smaller card, which is part of why one point on that curve went backwards.

## What is still open

- Generalisation on work the gist was not trained against. This is the real risk, and it is the next thing to fund.
- Per-hardware tuning, as above.
- Quality under the compression ratio we picked, 8 to 1. A 16 to 1 gist gave us about two thirds of the throughput gain, so the aggressive setting is not obviously worth the extra quality risk.

## The ask

Two weeks of held-out validation on unseen sessions, then a guarded pilot behind a flag with a fallback to the full prompt. The capacity number is now measured rather than projected, so the remaining question is quality, not performance.

Attached: the deck walks the journey in fifteen minutes; the whitepaper has the full method, the tables, and the failure modes. Benchmark code and every run file are in the repository if anyone wants to rerun it.
