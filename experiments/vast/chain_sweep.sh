#!/bin/bash
# Hardened sweep chain for one ratio, detached on the box. Markers in /root/STATE; terminal markers
# end in _FAILED or READY_FOR_EVAL. Retries: download x3, training OOM -> shorter cap, crash -> warm
# start from saved rows for the remaining epoch fraction, server start x2.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
if [ -f /root/CHAIN_RUNNING ]; then mark "chain_already_running"; exit 0; fi; touch /root/CHAIN_RUNNING
trap 'rm -f /root/CHAIN_RUNNING' EXIT
healthy() { curl -s -m 20 localhost:8000/v1/models -o /dev/null -w "%{http_code}" | grep -q 200; }
wait_health() { for i in $(seq 1 60); do healthy && return 0; sleep 10; done; return 1; }
stop_server() { touch /root/STOP; pkill -f "vllm [s]erve"; pkill -f "super[v]ise_gist"; sleep 10; rm -f /root/STOP; }
export HF_XET_HIGH_PERFORMANCE=1
FREE_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G'); [ "${FREE_GB:-0}" -lt 100 ] && { mark "disk_FAILED free=${FREE_GB}G"; exit 1; }
pip install -q -U "huggingface_hub[hf_xet]" flash-linear-attention 2>&1 | grep -vE "WARNING|notice" | tail -1
ok=0; for a in 1 2 3; do mark "download_attempt_$a"; hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 && { ok=1; break; }; sleep 30; done
[ $ok -eq 1 ] || { mark "download_FAILED"; exit 1; }
cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare.log 2>&1 || { mark "prepare_FAILED"; tail -5 /root/prepare.log; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
bash /root/apply_gist_delta.sh > /root/apply.log 2>&1 || { mark "apply_FAILED"; tail -5 /root/apply.log; exit 1; }
cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json
mark "delta_done $(tail -1 /root/apply.log)"
python3 -c "import torch; c=torch.load('/root/teacher_cache.pt', map_location='cpu'); print(len(c['cache']))" > /root/cache_check.log 2>&1 || { mark "cache_FAILED"; exit 1; }
mark "cache_ok examples=$(cat /root/cache_check.log)"

EPOCHS="${EPOCHS:-1}"; ACCUM="${ACCUM:-8}"; LR="${LR:-1e-3}"; EVAL_N="${EVAL_N:-24}"; EVAL_EVERY="${EVAL_EVERY:-40}"; REDUCE="${REDUCE:-batch}"
train_once() {  # $1 = smax, $2 = epochs, $3 = init rows or ""
  local init=""; [ -n "$3" ] && init="--init $3"
  cd /root/gist && python3 train.py --data /root/data/train.jsonl --model /root/qwen3.8-27b-gist --teacher-cache /root/teacher_cache.pt --epochs "$2" --accum "$ACCUM" --lr "$LR" --student-max-len "$1" --eval-every "$EVAL_EVERY" --eval-n "$EVAL_N" --reduce "$REDUCE" --out /root/gist_rows.pt $init >> /root/train.log 2>&1
}
SMAX="${SMAX:-32000}"; remaining="$EPOCHS"; init=""; attempts=0; done_train=0
while [ $attempts -lt 4 ]; do
  attempts=$((attempts+1)); mark "train_start attempt=$attempts smax=$SMAX epochs=$remaining reduce=$REDUCE init=${init:-none}"
  if train_once "$SMAX" "$remaining" "$init"; then done_train=1; break; fi
  if grep -q "OutOfMemoryError" /root/train.log; then
    SMAX=$((SMAX*4/5)); mark "train_OOM: lowering smax to $SMAX"
  fi
  if [ -f /root/gist_rows.pt ]; then
    last=$(grep -E "^step [0-9]+ " /root/train.log | tail -1 | awk '{print $2}'); total=$(grep -E "steps for" /root/train.log | tail -1 | awk '{print $NF}')
    if [ -n "$last" ] && [ -n "$total" ] && [ "$total" -gt 0 ]; then remaining=$(python3 -c "print(max(0.1, round(1 - $last/$total, 2)))"); fi
    init="/root/gist_rows.pt"; mark "train_retry: warm start from saved rows, remaining epochs $remaining"
  fi
  sleep 15
done
[ $done_train -eq 1 ] || { mark "train_FAILED after $attempts attempts"; grep -vE "Warning|warn" /root/train.log | tail -6; exit 1; }
mark "train_done $(grep -E 'eval KL' /root/train.log | tr '\n' ' ' | cut -c1-300)"
python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist /root/gist_rows.pt > /root/export.log 2>&1 && mark "export_done $(cat /root/export.log)" || { mark "export_FAILED"; exit 1; }
for a in 1 2; do
  stop_server; rm -f /root/STOP
  nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
  mark "gist_trained_launch_attempt_$a"
  if wait_health; then
    cd /root && python3 gen_test.py > /root/gen_test_trained.log 2>&1; mark "gen_test_trained: $(grep TOTAL /root/gen_test_trained.log)"
    mark "READY_FOR_EVAL"; exit 0
  fi
done
mark "gist_trained_FAILED_TO_START"; exit 1
