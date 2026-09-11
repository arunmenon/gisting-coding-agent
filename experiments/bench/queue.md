# Serving-throughput benchmark queue

Goal: turn the whitepaper's "throughput direction" (one replay, +16% at c=8) into a
defensible capacity number a CTO can budget against: **max concurrent agent sessions
per GPU under a latency SLO**, full prompt vs 8:1 gist, with error bars.

Decisions (2026-09-11):
- Scope: B0-B5 (everything), pending budget.
- SLO: capacity = highest concurrency where **p95 end-to-end latency <= 2x the c=1 median**.
- Primary GPU: 80-96 GB class (H100 / A100-80G), to stay comparable to the paper.
- Arms: full prompt + 8:1 gist (r8v2) primary; 16:1 added as an extra arm in B1.

Rigor (all experiments): >=3 repeats per point; discard warmup; measure only a
steady-state window; balanced arm order; reset/prewarm cache per arm; fixed workload
seed; client metrics cross-checked against vLLM engine counters; report mean +/- CI.
Metric definitions: TTFT = time to first token carrying content (parsed from stream
delta/usage, not first SSE event); TPOT = mean inter-token latency; E2E = request start
to last token; throughput = completed req/min and output tokens/s; goodput = req/min
meeting the SLO.

| ID | Objective | Method | Key output | ~GPU-h |
|----|-----------|--------|-----------|--------|
| B0 | Harness + smoke | closed-loop + open-loop load driver, corrected TTFT; smoke on cheapest box | validated harness (client vs engine counters agree) | 1-2 |
| BT | vLLM serving tuning | on the target GPU, find a strong serving config (gpu-mem-util, max-num-seqs, max-model-len, chunked prefill / max-num-batched-tokens, prefix caching, KV dtype); pick by throughput at fixed p95 SLO | documented tuned config, applied IDENTICALLY to both arms | 2-3 |
| B1 | Saturation & capacity curve | caching ON; sweep concurrency 1..saturation; full/8:1/16:1; 3 repeats | throughput(conc) curve, p50/p95 E2E/TTFT/TPOT, max sessions @ SLO | 5-7 |
| B2 | KV-cache capacity ceiling | deep-context workload; measure max concurrent seqs before preemption, KV blocks/seq, prefix-hit rate | why capacity rises: fewer prompt tokens -> more sessions fit | 2 |
| B3 | Realistic open-loop load | Poisson arrivals at rising RPS; prompt/output length mix from logged sessions | max sustainable RPS @ SLO (goodput), tail latency under burst | 3 |
| B4 | Prefix-cache ablation | full vs gist, caching ON vs OFF, a few concurrencies | incremental gain of gist over prefix caching alone | 2 |
| B5 | 2nd GPU class / cost norm | repeat B1 core on a cheaper class (L40S / A100-80G) | sessions-per-GPU per hardware-hour (cost per session) | 4 |

vLLM config (BT) is due diligence: we do NOT report numbers on a suboptimal server.
We tune on the target GPU and use the SAME tuned config for both arms, so any gap is
the prompt, not the setup. Parameters considered: --gpu-memory-utilization (as high as
stable), --max-num-seqs (as high as the recurrent-state cache blocks allow; the paper hit
a 64 cap), --max-model-len (sized to the workload, not wastefully large), chunked prefill
and --max-num-batched-tokens, --enable-prefix-caching, and --kv-cache-dtype (fp8 only if
it passes a quality check). The chosen config and the reason for each value are recorded
in the journey log.

Workload: replay pre-rendered request payloads (one file per arm) so serving is
measured directly; full-arm payloads carry the ~24k-token prompt, gist-arm payloads
carry the gist tokens + conditional template. Built from logged sessions
(short + deep turns) with fixed output-token budgets per class.

Spend safety (per experiment-journey skill): ledger entry the moment an instance
exists; idle watchdog on every box; sync-before-destroy; destroy same session;
check credit before each provision (do not provision below est + $10 reserve).
Do NOT touch pre-existing RTX 3060 instance 49274914.
