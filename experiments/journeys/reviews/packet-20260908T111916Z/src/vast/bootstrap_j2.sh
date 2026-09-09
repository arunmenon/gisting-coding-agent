#!/bin/bash
# Runs INSIDE the vast container, detached (nohup setsid). One chain: download base checkpoint,
# build the gist delta on the box, overlay it, serve the gisted model. Markers in /root/STATE.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
export HF_XET_HIGH_PERFORMANCE=1
pip install -q -U "huggingface_hub[hf_xet]" 2>&1 | grep -v WARNING | tail -1
apt-get install -y -qq tmux >/dev/null 2>&1 || true
mark "download_start"
hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 || { mark "download_FAILED"; exit 1; }
mark "download_done $(du -sh /root/.cache/huggingface/hub | cut -f1)"
mkdir -p /root/gist/out
cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare.log 2>&1 || { mark "prepare_FAILED"; tail -5 /root/prepare.log; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
mark "delta_done $(tail -1 /root/prepare.log)"
bash /root/apply_gist_delta.sh > /root/apply.log 2>&1 || { mark "apply_FAILED"; tail -5 /root/apply.log; exit 1; }
mark "apply_done $(tail -1 /root/apply.log)"
cp /root/mask_gist_logits.py /root/mask_gist_logits.py 2>/dev/null
rm -f /root/STOP
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
mark "serve_gist_launched"
