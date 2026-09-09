#!/bin/bash
# Detached end-of-journey chain on the box: stop vLLM, smoke-test the trainer, short E2 run, export
# rows, relaunch gisted vLLM with the mask, run gen test. Expects /root/data/train.jsonl.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
wait_health() { for i in $(seq 1 60); do curl -s -m 5 localhost:8000/health -o /dev/null -w "%{http_code}" | grep -q 200 && return 0; sleep 10; done; return 1; }
STEPS="${STEPS:-60}"; ACCUM="${ACCUM:-4}"; LR="${LR:-2e-3}"; MAXLEN="${MAXLEN:-36000}"
touch /root/STOP; pkill -f "vllm [s]erve"; sleep 10; rm -f /root/STOP
# Rebuild the delta from the current segment map (J2 span) and overlay it on the gisted checkpoint dir.
cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare2.log 2>&1 || { mark "prepare2_FAILED"; tail -5 /root/prepare2.log; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
bash /root/apply_gist_delta.sh > /root/apply2.log 2>&1 || { mark "apply2_FAILED"; tail -5 /root/apply2.log; exit 1; }
cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json
mark "delta2_done $(tail -1 /root/apply2.log)"
mark "train_smoke_start"
cd /root/gist && python3 train.py --data /root/data/train.jsonl --model /root/qwen3.8-27b-gist --steps 2 --accum 1 --eval-n 2 --max-len "$MAXLEN" --out /root/gist_rows_smoke.pt > /root/train_smoke.log 2>&1
if [ $? -ne 0 ]; then mark "train_smoke_FAILED"; tail -15 /root/train_smoke.log; exit 1; fi
mark "train_smoke_ok $(grep -E 'step 0 eval|s/step' /root/train_smoke.log | tail -2 | tr '\n' ' ')"
python3 train.py --data /root/data/train.jsonl --model /root/qwen3.8-27b-gist --steps "$STEPS" --accum "$ACCUM" --lr "$LR" --eval-every "${EVAL_EVERY:-25}" --eval-n "${EVAL_N:-6}" --max-len "$MAXLEN" --out /root/gist_rows.pt > /root/train.log 2>&1
if [ $? -ne 0 ]; then mark "train_FAILED"; tail -15 /root/train.log; exit 1; fi
mark "train_done $(grep -E 'eval KL' /root/train.log | tr '\n' ' ')"
python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist /root/gist_rows.pt > /root/export.log 2>&1 && mark "export_done $(cat /root/export.log)" || { mark "export_FAILED"; exit 1; }
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
mark "gist_masked_launched"
if wait_health; then mark "gist_masked_healthy"; cd /root && python3 gen_test.py > /root/gen_test_masked.log 2>&1; mark "gen_test_masked: $(grep TOTAL /root/gen_test_masked.log)"; else mark "gist_masked_FAILED_TO_START"; fi
