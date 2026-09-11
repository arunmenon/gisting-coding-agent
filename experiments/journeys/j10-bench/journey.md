# Journey 10: the serving benchmark, or what the gist actually buys

*In everyday terms.* Two kitchens, one big menu. We had claimed the kitchen with the one-page cheat-sheet turns over more diners per hour, but we had timed it once, with a stopwatch we were not sure of, in a kitchen set up badly. This journey fixed the stopwatch, set both kitchens up properly, and timed them again and again, under steady queues and under random rushes, with and without the head chef's memory of repeat orders, and in a much bigger kitchen for comparison.

**The uncertainty this retires.** Whether the paper's "+16% throughput at eight sessions, one run" is a real capacity gain a CTO can budget against, how big it is, where it comes from, and whether it depends on the hardware.

## The question
On a properly tuned server, with repeated runs and a latency objective, how much more load does the 8:1 gist let one GPU carry than the full prompt, and why?

## What we believed going in
The paper's single replay: +5/15/16 percent throughput at 1/4/8 sessions on a server configured with a 131k context, 64 sequences, 0.80 memory utilisation and 4k batched tokens; a time-to-first-token measurement that counted the first network event rather than the first token; and a layer-mix argument that the gain should be throughput rather than latency. An external review called the evidence direction, not precision.

## What we ran
Harness: a new load generator (closed-loop fixed concurrency and open-loop Poisson arrivals; TTFT from the first content token; usage-based token counts; engine-counter deltas). Corpus: 198 turn-ordered requests per arm from 24 logged sessions, prompts capped at 36k tokens (median full 26,169, gist 10,998, gist16 9,733), fixed 200-token outputs. Server: vLLM 0.28, tuned by throughput at fixed load and applied identically to both arms (context 40,960; 256 sequences; 0.92 utilisation; 16k batched tokens). Blocks on an H100 NVL 95 GB: B0 smoke plus untuned reference; BT tuning; B1 concurrency sweep 1 to 256, three repeats, balanced arm order; B2 resident-sequence probe; B3 open-loop 9 to 72 requests/min, two repeats; B4 prefix-cache ablation; a 16:1 arm with its own full-prompt control. B5 on an H200 NVL 143 GB, same configuration, two repeats. 201 runs, zero failures.

## What the GPU showed us
- **Untuned reference (paper config), c=8:** full 42.7, gist 48.0 req/min (+12%). The paper's server throttled both arms.
- **B1 (tuned, 3 repeats, sd <= 0.6):** peak full 42.7 at 16 sessions, gist 61.3 at 32 (+44%); gist16 54.0 (+27%). Ratio grows with load: 1.12x at 1, 1.38x at 8, 1.44x at 32, 1.65x at 48. Full collapses beyond 32 (KV 100%, 29 req/min); gist declines from 64.
- **B3 (open loop):** within a p95 objective of 2x the unloaded median, full sustains ~18 req/min offered, gist ~36: twice the load.
- **B4:** with prefix caching off, full falls to 14-30% of its cached throughput and gist to 44-53%; gist/full becomes 2.0x, 2.5x, 4.4x at 4/8/16 sessions. With caching on the gist's +16-44% is incremental.
- **B2:** H100 at 256 offered: 54 full vs 66 gist sequences resident, KV 100% both. H200: exactly 100 resident in both arms, KV 83%, no preemptions, yet 85.5 vs 50.0 req/min. The ceiling is the recurrent-state cache (prompt-length independent); the gist wins by turnover.
- **B5 (H200):** peak 85.3 full vs 83.3 gist (-2%); +4-16% at low load; 0.81x at 16 (reproducible; H100-tuned config); +45% at 32; 3.1x at 128 where full collapses. Throughput per dollar-hour: H100 full 16.2, H100 gist 23.2, H200 full 22.5, H200 gist 22.0.

## What we now understand differently
The gist is a cost lever, not a speed lever. Its value is proportional to how memory-constrained the hardware is relative to the prompt: large on a 95 GB card, near zero at normal load on a 143 GB card, and largest of all where prefixes are not shared. It does not fit many more sessions once the recurrent-state ceiling binds; it makes each session finish sooner. 16:1 buys two thirds of 8:1's gain; 8:1 stays the operating point. The paper's original number undersold the result because the server was throttled, and its mechanism ("more sessions fit") was too simple.

## What it cost
H100 NVL 8.76 GPU-hours; H200 NVL 1.56 GPU-hours; three cheap smoke boxes and one aborted H200 host, under 0.6 GPU-hours combined. Six provisioning defects were found and fixed for cents before any expensive box was touched (see the experiment-journey skill field notes).
