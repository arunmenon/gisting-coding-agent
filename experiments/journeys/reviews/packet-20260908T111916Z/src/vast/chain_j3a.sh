#!/bin/bash
# J3 part A (detached): download base, build delta from the J3 segment map, serve the gisted model
# with the logits mask, the conditional chat template, and prompt-logprobs enabled.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
export HF_XET_HIGH_PERFORMANCE=1
pip install -q -U "huggingface_hub[hf_xet]" flash-linear-attention 2>&1 | grep -vE "WARNING|notice" | tail -1
mark "download_start"
hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 || { mark "download_FAILED"; exit 1; }
mark "download_done"
cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare.log 2>&1 || { mark "prepare_FAILED"; tail -5 /root/prepare.log; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
bash /root/apply_gist_delta.sh > /root/apply.log 2>&1 || { mark "apply_FAILED"; tail -5 /root/apply.log; exit 1; }
cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json
cp /root/chat_template_gist.jinja /root/qwen3.8-27b-gist/chat_template.jinja   # conditional template ships with the checkpoint
mark "delta_done $(tail -1 /root/apply.log)"
rm -f /root/STOP
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
mark "serve_gist_launched"
for i in $(seq 1 60); do curl -s -m 5 localhost:8000/health -o /dev/null -w "%{http_code}" | grep -q 200 && { mark "serve_gist_healthy"; exit 0; }; sleep 10; done
mark "serve_gist_FAILED_TO_START"; tr "\r" "\n" < /root/vllm_gist.log | grep -aE "Error|Traceback" | tail -3
