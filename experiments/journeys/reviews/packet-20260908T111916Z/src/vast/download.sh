#!/bin/bash
# Parallel checkpoint download on the instance, in tmux, so vLLM loads from local disk.
pkill -f "vllm serve" 2>/dev/null
pip install -q -U "huggingface_hub[hf_xet]" 2>&1 | grep -v WARNING | tail -1
tmux new-session -d -s dl 'HF_XET_HIGH_PERFORMANCE=1 hf download Qwen/Qwen3.8-27B 2>&1 | tee /root/download.log; echo DL_DONE >> /root/download.log'
A=$(du -sb /root/.cache/huggingface 2>/dev/null | cut -f1); sleep 45; B=$(du -sb /root/.cache/huggingface 2>/dev/null | cut -f1)
echo "rate MB/s: $(( (B-A)/45/1000000 ))  total GB: $(( B/1000000000 ))"
tmux ls; tail -c 400 /root/download.log | tr "\r" "\n" | grep -v "^$" | tail -2
