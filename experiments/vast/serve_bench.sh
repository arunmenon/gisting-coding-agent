#!/bin/bash
# Parametrized vLLM serve for the throughput benchmark (BT tuning + B1-B5).
# All knobs via env so the chain can restart with different configs:
#   CKPT            checkpoint dir (default /root/qwen3.8-27b-gist)
#   MAX_MODEL_LEN   context length reserved per sequence (size to the workload, not 131k)
#   MAX_NUM_SEQS    max concurrent sequences (bounded by recurrent-state cache blocks)
#   GPU_UTIL        --gpu-memory-utilization
#   MAX_BATCHED     --max-num-batched-tokens (chunked-prefill batch size)
#   PREFIX_CACHE    1 (default) or 0 -> --no-enable-prefix-caching  (B4 ablation)
#   KV_DTYPE        auto (default) | fp8   (fp8 excluded from tuning unless quality-checked)
#   LP_FLAG         logits-processor flag (default: gist mask)
set -euo pipefail
export HF_HUB_OFFLINE=1 VLLM_LOGGING_LEVEL=INFO GIST_META="${GIST_META:-/root/delta/gist_meta.json}"
cd /root
CKPT="${CKPT:-/root/qwen3.8-27b-gist}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"; MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
GPU_UTIL="${GPU_UTIL:-0.90}"; MAX_BATCHED="${MAX_BATCHED:-8192}"
PREFIX_CACHE="${PREFIX_CACHE:-1}"; KV_DTYPE="${KV_DTYPE:-auto}"
LP_FLAG="${LP_FLAG---logits-processors mask_gist_logits:GistMaskLogitsProcessor}"
EXTRA=""
[ "$PREFIX_CACHE" = "0" ] && EXTRA="$EXTRA --no-enable-prefix-caching"
[ "$KV_DTYPE" != "auto" ] && EXTRA="$EXTRA --kv-cache-dtype $KV_DTYPE"
echo "$(date -u +%FT%TZ) serve_bench: ckpt=$CKPT len=$MAX_MODEL_LEN seqs=$MAX_NUM_SEQS util=$GPU_UTIL batched=$MAX_BATCHED prefix=$PREFIX_CACHE kv=$KV_DTYPE" | tee -a /root/vllm_bench.log
exec env PYTHONPATH=/root vllm serve "$CKPT" \
  --served-model-name qwen3.8-27b-gist \
  --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
  --language-model-only --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --gpu-memory-utilization "$GPU_UTIL" --max-num-batched-tokens "$MAX_BATCHED" --max-logprobs 64 \
  --chat-template /root/chat_template_gist.jinja $LP_FLAG $EXTRA \
  --host 0.0.0.0 --port 8000 2>&1 | tee -a /root/vllm_bench.log
