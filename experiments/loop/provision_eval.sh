#!/bin/bash
# provision_eval.sh <instance> <host> <port> <first_ratio> <journey> <tasks> <runs...>
set -u
IID=$1; H=$2; P=$3; FIRST=$4; JOURNEY=$5; TASKS=$6; shift 6; RUNS="$@"
cd "$(dirname "$0")/.."
S=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20)
try() { for i in $(seq 1 10); do "$@" 2>/dev/null && return 0; sleep 15; done; return 1; }
try ssh "${S[@]}" -p "$P" root@"$H" 'mkdir -p /root/gist /root/ratios && echo ready' | grep -q ready || { echo "SSH_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/serve_ratio.sh vast/bootstrap_j5.sh vast/gen_test.py gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@"$H":/root/ || { echo "COPY1_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py root@"$H":/root/gist/ || { echo "COPY2_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" -r loop/ratios/r2 loop/ratios/r4 loop/ratios/r8 loop/ratios/r16 root@"$H":/root/ratios/ || { echo "COPY3_FAILED"; exit 1; }
echo copied
try ssh "${S[@]}" -p "$P" root@"$H" "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; ls /root/ratios | tr '\n' ' '; nohup setsid bash /root/bootstrap_j5.sh $FIRST > /root/bootstrap.log 2>&1 < /dev/null & IDLE_MIN=120 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & sleep 3; pgrep -f 'idle_[w]atchdog' | head -1 | xargs echo watchdog"
echo "{\"host\": \"$H\", \"port\": $P, \"instance\": $IID}" > loop/evalbox.json
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "${FIRST}_READY|FAILED"; do sleep 30; done
echo "bootstrap: $OUT"; echo "$OUT" | grep -q READY || exit 1
nohup .venv/bin/python3 loop/eval_sweep.py loop/evalbox.json "$JOURNEY" "$TASKS" $RUNS > logs/eval_sweep_${JOURNEY}.log 2>&1 &
echo "EVAL_SWEEP_STARTED pid $!"
