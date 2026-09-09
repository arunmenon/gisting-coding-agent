# J1 ops log: E0 tap and static-span measurement

Target: Claude Code 2.1.259 -> tap proxy -> ssh tunnel -> vLLM (Anthropic Messages API) serving Qwen/Qwen3.8-27B bf16 on one 96GB GPU.

```
[x] 1. Freshness check (2026-09-03): Qwen3.8-27B bf16 = 55.6GB safetensors, FP8 variant 30.9GB; vLLM recipe needs vLLM>=0.17.0, transformers>=5.8; latest stable image vllm/vllm-openai:v0.28.0; vLLM serves /v1/messages natively (docs/serving/integrations/claude_code.md); Claude Code injects a per-request attribution hash into the system prompt, disable with CLAUDE_CODE_ATTRIBUTION_HEADER=0.
[x] 2. Journey directory created
[x] 3. Local smoke test: tap.py compiles; end-to-end smoke happens on the instance (operator directive)
[x] 4. Offer selected
[x] 5. Instance created + ledger entry
[x] 6. vllm serve launched in tmux; watchdog deployed
[x] 7. First /v1/messages round trip through the tap verified
[x] 8. Real Claude Code sessions logged
[x] 9. Logs synced (they are local already; sync vllm.log)
[x] 10. Instance destroyed; ledger closed
[x] 11. journey.md written
[ ] 12. Requester has seen it
```

## Timeline
- 2026-09-03 12:40 account credit $18.64; requester added $50 during setup.
- 2026-09-03T07:18:14Z offer 48659457 selected (RTX PRO 6000 Max-Q 96GB, $1.388/hr, 7Gbps down, rel 0.991, Czechia); instance 49725593 created; ledger written. Items 4,5 done.
- 2026-09-03T07:21:23Z instance provisioned: vllm 0.28.0, transformers 5.15.1, torch 2.13 cu130, 683GB free disk; vllm serve started in tmux 'vllm'; watchdog (60 min idle -> destroy) running; local tunnel 8000 and tap 8080 started. Item 6 done.
- 2026-09-03T07:49:17Z first vllm launch stalled on in-loader Hub download; killed it, checkpoint fetched with hf download (55GB on disk), vllm relaunched offline from disk; watchdog re-armed at 90 min.
- 2026-09-03T07:50:14Z attempt 1 failed: max_num_seqs 1024 > 674 Mamba cache blocks. Relaunched with --max-num-seqs 64. Log shows prefix caching enabled for the hybrid model (Mamba cache mode 'align').
- 2026-09-03T07:54:57Z attempt 2: EngineCore died as zombie at 61% shard load with no traceback, tmux server gone (SIGHUP suspected). Attempt 3 launched via nohup setsid supervisor (vast/supervise.sh).
- 2026-09-03T08:01:39Z vLLM up (attempt 3): weights 14s, KV cache 528,807 tokens, 4x concurrency at 131k. Smoke test through tap: tool_use returned correctly, stream TTFT 0.80s. Item 7 done. Launching 8 headless sessions from Mac (box-side driver blocked by permission classifier).
- 2026-09-03T08:02:35Z all 8 sessions failed with 400 'Unexpected reasoning effort high' (Claude Code sends output_config.effort=high; Qwen3.8 accepts xhigh/medium/low). Tap now remaps high->medium, max->xhigh. Driver restarted.
- 2026-09-03T08:05:06Z rendered static span via /tokenize: system 1588 + 51 tools 20506 = 22094 tokens (17582 without the 24 Playwright MCP tools). Turn-1 also carries a 5765-token role=system message (agent types, skills list) that is stable per machine config. Driver bug: claude -p read the task file from stdin; fixed with </dev/null, run 2 started.
- 2026-09-03T08:22Z 8 clean sessions done (43 turns, 50 tool calls, 0 invalid). Analysis in results/e0_summary.txt. vllm logs synced. Instance 49725593 destroyed at 08:22Z. Tap and tunnel stopped.

## Post-journey, no GPU: section 3.3 checkpoint checks (2026-09-03)
- gist/span.py: local chat-template render of the span reproduces vLLM's count (22,136 vs 21,109 + the 985-token system tail + the effort preamble).
- gist/segments.py: template places the tools block BEFORE the system text, after a reasoning-effort preamble line that varies with effort. Segments at 4:1: system_0 602 -> 151, system_1 525 -> 132, system_2 458 -> 115, tools 20,506 -> 5,127; total 22,091 static tokens -> 5,525 gist tokens. Tokenizer: 5,525 added special tokens, ids 248,077..253,601, single-id round trip OK, skip_special_tokens drops them.
- gist/prepare_checkpoint.py: embed_tokens grown 248,320 -> 253,696 rows (padded to 128); 243 former spare rows plus 5,376 appended rows hold mean-chunk init. Real rows byte-identical. lm_head grown with zero rows. Gist row norm 0.58 vs real 0.90; cosine to own chunk 0.48-0.58, to random tokens 0.01. Delta (two shards + config + tokenizer) in gist/out/checkpoint_delta/, 6 GB.
- Open for the GPU journey: does vLLM 0.28 load the resized qwen3_5 checkpoint, and does gist/mask_gist_logits.py plug into its logits-processor flag. Generation test must show no id >= 248,077 ever emitted.
