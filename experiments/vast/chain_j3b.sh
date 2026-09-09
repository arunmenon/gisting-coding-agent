#!/bin/bash
# J3 part B (detached): stop vLLM, train against the teacher cache for EPOCHS, export rows, relaunch
# the gisted server (mask + template), run the gen test. Expects /root/data/train.jsonl and /root/teacher_cache.pt.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
EPOCHS="${EPOCHS:-1}"; ACCUM="${ACCUM:-8}"; LR="${LR:-1e-3}"; SMAX="${SMAX:-34000}"; EVAL_N="${EVAL_N:-24}"; EVAL_EVERY="${EVAL_EVERY:-40}"
touch /root/STOP; pkill -f "vllm [s]erve"; sleep 10; rm -f /root/STOP
mark "train_start epochs=$EPOCHS accum=$ACCUM lr=$LR smax=$SMAX"
cd /root/gist && python3 train.py --data /root/data/train.jsonl --model /root/qwen3.8-27b-gist --teacher-cache /root/teacher_cache.pt --epochs "$EPOCHS" --accum "$ACCUM" --lr "$LR" --student-max-len "$SMAX" --eval-every "$EVAL_EVERY" --eval-n "$EVAL_N" --out /root/gist_rows.pt > /root/train.log 2>&1
if [ $? -ne 0 ]; then mark "train_FAILED"; grep -vE "Warning|warn" /root/train.log | tail -8; exit 1; fi
mark "train_done $(grep -E 'eval KL' /root/train.log | tr '\n' ' ')"
python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist /root/gist_rows.pt > /root/export.log 2>&1 && mark "export_done $(cat /root/export.log)" || { mark "export_FAILED"; exit 1; }
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
mark "gist_trained_launched"
for i in $(seq 1 60); do curl -s -m 5 localhost:8000/health -o /dev/null -w "%{http_code}" | grep -q 200 && break; sleep 10; done
curl -s -m 5 localhost:8000/health -o /dev/null -w "%{http_code}" | grep -q 200 || { mark "gist_trained_FAILED_TO_START"; exit 1; }
mark "gist_trained_healthy"
cd /root && python3 gen_test.py > /root/gen_test_trained.log 2>&1; mark "gen_test_trained: $(grep TOTAL /root/gen_test_trained.log)"
