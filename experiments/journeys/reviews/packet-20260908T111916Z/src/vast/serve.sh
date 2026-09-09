#!/bin/bash
# Runs INSIDE the vast container (image vllm/vllm-openai). Launches the bf16 teacher checkpoint
# with the flags from the vLLM Qwen3.8-27B recipe, text-only, prefix caching on (vLLM default).
set -euo pipefail
MODEL="${MODEL:-Qwen/Qwen3.8-27B}"
SERVED_NAME="${SERVED_NAME:-qwen3.8-27b}"
MAX_LEN="${MAX_LEN:-131072}"
export HF_HUB_ENABLE_HF_TRANSFER=1
export VLLM_LOGGING_LEVEL=INFO
df -h /root /workspace 2>/dev/null || true
nvidia-smi --query-gpu=name,memory.total --format=csv
exec vllm serve "$MODEL" \
  --served-model-name "$SERVED_NAME" \
  --max-model-len "$MAX_LEN" \
  --language-model-only \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --gpu-memory-utilization 0.92 --max-num-seqs 64 \
  --host 0.0.0.0 --port 8000 2>&1 | tee -a /root/vllm.log
