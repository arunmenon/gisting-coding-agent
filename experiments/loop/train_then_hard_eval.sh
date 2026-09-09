#!/bin/bash
# train_then_hard_eval.sh <run> <ratio_dir_name> <host> <port> <instance> <journey>
# Waits for the worker chain's READY_FOR_EVAL, stages the trained rows as a ratio bundle on the box,
# runs the hard exam for <run> and the teacher arm, then destroys the box.
set -u
RUN=$1; R=$2; H=$3; P=$4; IID=$5; JOURNEY=$6; cd "$(dirname "$0")/.."
S=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20)
log() { echo "- $(date -u +%FT%TZ) $1" | tee -a journeys/$JOURNEY/log.md; }
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "READY_FOR_EVAL|FAILED"; do sleep 120; done
log "$RUN: worker chain -> $OUT"
echo "$OUT" | grep -q READY_FOR_EVAL || { log "$RUN: chain failed; destroying"; echo y | .venv/bin/vastai destroy instance "$IID" | tail -1; exit 1; }
ssh "${S[@]}" -p "$P" root@"$H" "mkdir -p /root/ratios/$RUN && cp /root/gist/out/segments.json /root/ratios/$RUN/ && cp -r /root/gist/out/tokenizer /root/ratios/$RUN/ && cp /root/gist_rows.pt /root/ratios/$RUN/ && cp /root/serve_ratio.sh /root/serve_ratio.sh 2>/dev/null; ls /root/ratios/$RUN" 2>/dev/null
scp "${S[@]}" -P "$P" vast/serve_ratio.sh root@"$H":/root/ 2>/dev/null
mkdir -p loop/ratios/$RUN && cp gist/$R/segments.json loop/ratios/$RUN/ && cp -r gist/$R/tokenizer loop/ratios/$RUN/
echo "{\"host\": \"$H\", \"port\": $P, \"instance\": $IID}" > loop/evalbox_$RUN.json
.venv/bin/python3 loop/eval_sweep.py loop/evalbox_$RUN.json "$JOURNEY" driver/tasks_hard.txt "$RUN" teacher > logs/eval_sweep_${RUN}.log 2>&1
scp "${S[@]}" -P "$P" root@"$H":/root/train.log root@"$H":/root/STATE root@"$H":/root/gist_rows.pt journeys/$JOURNEY/results/$RUN/ 2>/dev/null
if [ -n "${COVEXAM:-}" ]; then
  log "$RUN: coverage exam in gist mode"
  pkill -f "ssh -N .* -L 8500:" 2>/dev/null; ssh -N "${S[@]}" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p "$P" -L $((8600+RANDOM%300)):127.0.0.1:8000 root@"$H" & TUN=$!; sleep 6
  .venv/bin/python3 proxy/tap.py --listen 127.0.0.1:8501 --upstream http://127.0.0.1:8500 --log journeys/$JOURNEY/results/$RUN/requests_covexam.jsonl --gist gist/$R/segments.json --normalize "qwen3.8-27b-gist=qwen3.8-27b" > journeys/$JOURNEY/results/$RUN/tap_covexam.log 2>&1 & TAP=$!; sleep 2
  TAP_URL=http://127.0.0.1:8501 MODEL_NAME=qwen3.8-27b-gist KEEP=1 bash driver/run_sessions_local.sh driver/tasks_coverage.txt covexam_$RUN 4 > journeys/$JOURNEY/results/$RUN/driver_covexam.log 2>&1
  kill $TAP $TUN 2>/dev/null
  .venv/bin/python3 driver/eval_coverage.py driver/tasks_coverage.txt journeys/$JOURNEY/results/$RUN/requests_covexam.jsonl --json journeys/$JOURNEY/results/$RUN/coverage.json > journeys/$JOURNEY/results/$RUN/coverage.txt 2>&1
  log "$RUN: coverage exam: $(grep SUMMARY journeys/$JOURNEY/results/$RUN/coverage.txt | cut -c1-140)"
fi
echo y | .venv/bin/vastai destroy instance "$IID" | tail -1; log "$RUN: exams done, instance $IID destroyed"
