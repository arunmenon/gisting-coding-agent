# Journey 6: What the shorter handbook actually buys in speed

*In everyday terms.* The contractor with the one-page summary reads less. Does the job get done faster? For one contractor working alone, barely: most of the time goes into doing the work, not reading. For a crew of eight sharing one workshop, yes: less reading means the workshop turns over more jobs per hour.

**The uncertainty this retires.** E8, the real latency and throughput effect of the gist on this hybrid-attention model, with prefix caching on in both arms.

## The question

With the corrected 8:1 gist (2,171 tokens for 17,343) serving on one 96 GB GPU, how do time to first token, per-turn latency, and throughput compare with the full prompt at concurrencies of 1, 4, and 8?

## What we believed going in

Shopify reported 19 percent lower median time to first token, 38 percent lower end-to-end latency, and 16 percent higher throughput at 4:1 on a standard transformer. Section 3.5 of the plan predicted a materially smaller effect here because only 16 of 64 layers pay the decode-time cost over the prefix.

## What we ran

One box, the corrected 8:1 checkpoint served by vLLM 0.28 with the logits mask and the conditional template, prefix caching on. Twelve logged sessions of six turns each replayed in turn order so caching sees realistic sharing; each request generates exactly 200 tokens at temperature 0 with end-of-sequence ignored. Teacher arm uses the full rendered prompt (median 25,465 tokens), gist arm the same conversation with the span replaced (median 10,294). Client timings measured on the box against localhost; engine counters read before and after each arm. Concurrency 1, 4, and 8; 72 requests per arm.

## What the GPU showed us

| Concurrency | Arm | Prompt tokens | TTFT median | TTFT p90 | Latency median | Requests per minute | Engine prefill per request | Prefix hit rate |
|---|---|---|---|---|---|---|---|---|
| 1 | teacher | 25,465 | 1.10 s | 2.69 s | 8.2 s | 6.9 | 1.56 s | 0.75 |
| 1 | gist | 10,294 | 0.95 s | 2.37 s | 8.0 s | 7.2 | 1.31 s | 0.51 |
| 4 | teacher | 25,465 | 2.11 s | 8.96 s | 13.0 s | 16.4 | 2.56 s | 0.72 |
| 4 | gist | 10,294 | 1.62 s | 5.46 s | 11.5 s | 18.9 | 1.88 s | 0.51 |
| 8 | teacher | 25,465 | 2.02 s | 12.72 s | 14.9 s | 20.0 | 2.72 s | 0.73 |
| 8 | gist | 10,294 | 1.46 s | 11.52 s | 13.1 s | 23.2 | 2.08 s | 0.51 |

Gist relative to teacher: at concurrency 1, throughput +5 percent, median latency −3 percent; at concurrency 4, throughput +15 percent, latency −11 percent, TTFT p90 −39 percent; at concurrency 8, throughput +16 percent, latency −12 percent, TTFT median −28 percent.

## What we now understand differently

- **The prediction held.** Shopify's throughput gain (+16 percent) reproduces almost exactly; their latency gain (−38 percent) does not, and lands at −12 percent. On this model decode time barely depends on prefix length, so a single session sees little; the gain appears under load, where less prefill per request frees the scheduler for decode.
- **Tail latency is where users would feel it.** At concurrency 4 the p90 time to first token fell 39 percent, from 9.0 to 5.5 seconds. That is the metric a person waiting for an agent notices.
- **Prefix caching and gisting compose, but caching's share shrinks.** The gist's prefix is 51 percent cache-served against the teacher's 72 to 75, because a shorter static prefix is a smaller fraction of each request. Both arms still had caching on; the gain is over the cached baseline.
- **The business case is throughput, not latency, on this architecture.** 16 percent more sessions per GPU at saturation, against the retraining cost on every client or catalogue change. That is the number to weigh.

## What it cost

0.9 instance-hours at $1.335, about $1.25. The benchmark itself took 37 minutes.
