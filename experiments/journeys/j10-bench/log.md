# J10 serving-throughput benchmark: ops log

Checklist (experiment-journey protocol):
[x] 1. Freshness: vLLM image vllm/vllm-openai:v0.28.0 (as prior journeys); harness self-tested locally
[x] 2. Journey directory created
[x] 3. Local smoke: loadgen + analyze syntax/self-test passed; corpus built (198 req/arm, median full 26,169 tok, max 35,953)
[ ] 4. Offer selected (H100 NVL 95GB, cheapest verified rel>0.98)
[ ] 5. Instance created + ledger entry written IMMEDIATELY
[ ] 6. Chain launched under nohup setsid; idle watchdog running
[ ] 7. B0 smoke green before walking away
[ ] 8. Monitored; results synced incrementally
[ ] 9. Results in journeys/j10-bench/results/
[ ] 10. Instance destroyed; ledger closed
[ ] 11. journey.md written

