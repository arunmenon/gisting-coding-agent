#!/bin/bash
# On the box: deps, base download, then build+serve the first ratio given as $1.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
export HF_XET_HIGH_PERFORMANCE=1
pip install -q -U "huggingface_hub[hf_xet]" 2>&1 | grep -vE "WARNING|notice" | tail -1
ok=0; for a in 1 2 3; do hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 && { ok=1; break; }; sleep 30; done
[ $ok -eq 1 ] || { mark "download_FAILED"; exit 1; }
mark "download_done"
bash /root/serve_ratio.sh "$1"
