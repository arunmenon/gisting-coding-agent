#!/bin/bash
# Serve the gisted checkpoint (resized embeddings, gist tokens registered) under a distinct name.
set -euo pipefail
export HF_HUB_OFFLINE=1 VLLM_LOGGING_LEVEL=INFO GIST_META=/root/delta/gist_meta.json
cd /root
LP_FLAG="${LP_FLAG---logits-processors mask_gist_logits:GistMaskLogitsProcessor}"   # set LP_FLAG="" to run unmasked
echo "logits processor flag: '$LP_FLAG'"
exec env PYTHONPATH=/root vllm serve /root/qwen3.8-27b-gist \
  --served-model-name qwen3.8-27b-gist \
  --max-model-len 131072 --max-num-seqs 64 \
  --language-model-only --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --gpu-memory-utilization 0.80 --max-num-batched-tokens 4096 --max-logprobs 64 --chat-template /root/chat_template_gist.jinja $LP_FLAG \
  --host 0.0.0.0 --port 8000 2>&1 | tee -a /root/vllm_gist.log
