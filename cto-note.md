# Note to the CTO: corrected gisting benchmark findings

**Subject line suggestion:** Gisting benchmark correction: measured replay gains, withdrawn mechanism, and revised cost comparison

---

We previously asked you to consider funding on the strength of a serving gain and an explanation of why it occurred. External review found a connection limit in our own load generator. We tested that finding in J11, and the hardware-ceiling explanation did not survive. The lower-concurrency J10 results remain finite-window replay measurements: 2x the target request rate passing the chosen latency criterion and +44% observed peak throughput on H100. Their mechanism and deployment value are not established.

## What we ran

The reviewer verified 202 archived J10 runs with zero recorded request errors. J11 is a separate eight-run follow-up, also with zero request errors, costing 1.15 GPU-hours including an aborted first instance. Neither benchmark measured output quality.

1. **Server configuration.** J10 selected a configuration using the gist arm at 32 concurrent requests and applied it to both arms. The other review findings about tuning fairness remain open.
2. **Load curve.** J10 replayed fixed-length requests at increasing concurrency, with three repeats for the primary H100 comparison. Points above 100 concurrent requests used the capped client.
3. **Random arrivals.** J10 tested target rates of 9 to 72 requests per minute against a p95 latency criterion of twice each arm's unloaded median. The reported 18 and 36 are target rates passing that short-run criterion.
4. **Caching comparison.** Both arms were tested with prefix caching disabled at 4, 8 and 16 concurrent requests, alongside the cache-enabled results. A smaller H200 experiment repeated the core load curve and residency probe using the H100-selected configuration.
5. **Original residency probe, now corrected.** J10 recorded exactly 100 running requests on H200 in both arms. Our instrument could send only 100 at once, so this did not measure a hardware ceiling or explain the mechanism.
6. **Connection-limit control.** J11 tested client caps of 100 and 512, both prompt arms, and 128 and 256 offered requests on H200. There was one run per condition, with a 30-second warm-up and a 180-second request-start measurement window.

## What remains measured in J10

These figures describe finite-window replay on one H100-class GPU, with 200-token outputs. They are not a demonstrated production-capacity or cost-saving commitment.

| Measure | Full prompt | With gist | Change |
|---|---|---|---|
| Target arrival rate passing the chosen latency criterion | 18 req/min | 36 req/min | 2x |
| Observed peak replay throughput | 42.7 req/min | 61.3 req/min | +44% (43.75% unrounded) |

The peak points were measured at 16 and 32 concurrent requests, below the connection cap. J11 does not invalidate them, the cache-off comparisons at 4, 8 and 16, or the tested open-loop arrival rates. The second review's other qualifications remain open.

## Correction to the mechanism we reported

**We withdraw the hardware-ceiling explanation.** External review identified a defect in our load generator, and the follow-up confirmed it. With the cap lifted, sampled residency exceeded 100 in every condition, reaching 123 to 137 requests. At 256 offered requests, the gist reached 137 against 126 for the full prompt. Those are single-run sampled maxima, with nearly full cache and preemptions in both conditions, not precise sustainable ceilings. The observations are consistent with memory pressure affecting admission; they do not establish the cause of the throughput advantage.

**Removing the cap often made throughput worse.** It fell from 59.67 to 47.00 requests per minute for full at 128, from 67.33 to 46.33 for full at 256, and from 88.33 to 56.67 for gist at 256. Only gist at 128 improved, from 74.00 to 80.67. This is consistent with the cap accidentally controlling admission and protecting the engine from overload. The earlier high-concurrency figures were not uniformly conservative.

**The relative advantage also changed.** Gist/full ratios at 128 and 256 were 1.24 and 1.31 with the cap, versus 1.72 and 1.22 without it. The historical capped H200 ratio of 3.1 at 128 therefore cannot be presented as an uncapped capacity estimate.

**Caching remains an uncontrolled difference.** Across J11, the full prompt had prefix-cache hit rates of 0.791 to 0.840, versus 0.580 to 0.626 for the gist. That favours the full prompt in cached fraction, but its effect on total throughput has not been isolated. This persistent asymmetry also appears in J10 and was not controlled for in the program.

## Corrected cost comparison

The earlier table mixed a quoted H100 rental rate with an effective H200 rate. On a consistent quoted-price basis, $2.64/h for H100 and $3.65/h for H200, the figures are:

| Configuration | Observed peak req/min per ($/h) |
|---|---:|
| H100, full prompt | 16.16 |
| H100, with gist | 23.23 |
| H200, full prompt | 23.38 |
| H200, with gist | 22.83 |

H200 running the full prompt slightly exceeds H100 running the gist on this measure. The two are approximately equal at these prices, but the arithmetic does not establish that the cheaper card can replace the more expensive one. These are unconstrained peak replay rates, with unequal hardware tuning effort and no quality measurement at load. They do not measure cost per successfully completed coding task.

## What to fund next

The next work should test output quality on unseen tasks, tune both versions fairly for each GPU, and measure correctly completed work within one common latency requirement. A guarded pilot should follow those checks. J11 settles the connection-limit defect; it does not complete performance validation.

The paper and deck now carry the correction. The historical logs and raw runs remain under `experiments/journeys/j10-bench/` and `experiments/journeys/j11-conn/`, including J11's limitations and the aborted provisioning attempt.
