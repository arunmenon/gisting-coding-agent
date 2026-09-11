# J10 serving-throughput benchmark: ops log

Checklist (experiment-journey protocol):
[x] 1. Freshness: vLLM image vllm/vllm-openai:v0.28.0 (as prior journeys); harness self-tested locally
[x] 2. Journey directory created
[x] 3. Local smoke: loadgen + analyze syntax/self-test passed; corpus built (198 req/arm, median full 26,169 tok, max 35,953)
[x] 4. Offer 24548924: H100 NVL 95GB, $2.64/hr, Bulgaria, rel .995
[x] 5. Instance 50565734 created 07:29Z; ledger row written
[x] 6. Chain + watchdog launched 08:12Z via DIRECT endpoint 87.116.91.146:11377 (proxy ssh7:15734 denied publickey)
[x] 7. B0_smoke_ok 08:23Z on paper baseline config (len131072 seqs64 util0.80 batched4096)
[x] 8. Monitored to BENCH_DONE 16:02Z (167 runs, 0 fails); results synced per milestone
[x] 9. Results in journeys/j10-bench/results/ (H100) and b5-h200/results/ (H200)
[x] 10. H100 50565734 destroyed (verified) 8.76h $23.13; H200 50588749 destroyed 1.56h $5.91; ledger closed
[x] 11. journey.md written 2026-09-11

2026-09-11T07:29:06Z created instance 50565734 (offer 24548924, $?/hr) label=j10-bench
2026-09-11T07:52:25Z ssh up: ssh7.vast.ai:15734
2026-09-11T08:07:14Z proxy ssh (ssh7:15734) denied publickey persistently; provisioner killed; switching to DIRECT 87.116.91.146:11377 (key verified matches registered)
2026-09-11T08:12:05Z shipped via direct endpoint (zsh $S word-split bug fixed with array); chain + watchdog launched on 50565734
2026-09-11T08:43:58Z BT_done: tuned config len40960 seqs256 util0.92 batched16384 (score 68.0 rpm @c32 gist8)
2026-09-11T12:18:26Z B5 attempt 1: instance 50587237 denied ssh key on direct+proxy 20+ min after running; destroyed; host excluded
2026-09-11T12:25:27Z B5 launched manually on 50588749 (H200 NVL, host 214845, .65/hr) after provisioner exit 2
2026-09-11T13:52:21Z H200 B5 BENCH_DONE 13:47Z; results synced (44 files); instance 50588749 destroyed (verified); 1.56h ~$5.91
2026-09-11T16:14:55Z BENCH_DONE 16:02Z; synced; H100 50565734 destroyed (verified); 8.76h $23.13
