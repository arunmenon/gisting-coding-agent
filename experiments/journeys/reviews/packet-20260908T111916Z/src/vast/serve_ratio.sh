#!/bin/bash
# On the box: (re)build the gisted checkpoint for one ratio from /root/ratios/<run>/ (segments.json,
# tokenizer/, gist_rows.pt), export the trained rows, relaunch the masked gisted server. Usage: serve_ratio.sh <run>
set -uo pipefail
RUN=$1; D=/root/ratios/$RUN
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
touch /root/STOP; pkill -f "vllm [s]erve"; pkill -f "super[v]ise_gist"; sleep 8; rm -f /root/STOP
rm -rf /root/gist/out && mkdir -p /root/gist/out && cp -r $D/segments.json $D/tokenizer /root/gist/out/
cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare_$RUN.log 2>&1 || { mark "serve_ratio_${RUN}_prepare_FAILED"; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
bash /root/apply_gist_delta.sh > /root/apply_$RUN.log 2>&1 || { mark "serve_ratio_${RUN}_apply_FAILED"; exit 1; }
cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json
python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist $D/gist_rows.pt > /root/export_$RUN.log 2>&1 || { mark "serve_ratio_${RUN}_export_FAILED"; exit 1; }
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
for i in $(seq 1 60); do curl -s -m 20 localhost:8000/v1/models 2>/dev/null | grep -q gist && { mark "serve_ratio_${RUN}_READY $(cat /root/export_$RUN.log | cut -c1-120)"; exit 0; }; sleep 10; done
mark "serve_ratio_${RUN}_FAILED_TO_START"; exit 1
