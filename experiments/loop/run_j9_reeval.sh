#!/bin/bash
# Clean re-eval of the two per-segment ratios from saved rows, one box, sequential, eval concurrency 2.
# Fixes applied: distinct tap/tunnel ports per exam; low concurrency so one SSH tunnel does not drop requests.
set -u; cd "$(dirname "$0")/.."; KEY=$(cat ~/.config/vastai/vast_api_key); J=j9-seg-ratio
SCR=/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad
log() { echo "- $(date -u +%FT%TZ) $1" | tee -a journeys/$J/log.md; }
S=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20)
try() { for i in $(seq 1 30); do "$@" 2>/dev/null && return 0; sleep 40; done; return 1; }
CONC=2
LINE=$(.venv/bin/vastai search offers "gpu_ram>=90 num_gpus=1 reliability>0.99 inet_down>1500 verified=true rentable=true disk_space>=150 cuda_vers>=12.8 dph_total<1.6" -o dph_total --raw 2>/dev/null | python3 -c "
import sys,json
bad={28810499,28810501,44111199,47849044,46474489,48659459,48659457,49566523,47550078,48778837,34545927}
for o in json.load(sys.stdin):
    if o['id'] in bad or 'Spain' in (o.get('geolocation') or ''): continue
    print(o['id'], round(o['dph_total'],3), (o.get('geolocation') or '').replace(' ','_')); break")
OFFER=$(echo "$LINE" | awk '{print $1}'); RATE=$(echo "$LINE" | awk '{print $2}')
OUT=$(.venv/bin/vastai create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk 150 --ssh --direct --label j9-reeval --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('vast/.instance_key_'+str(d['new_contract']),'w').write(d.get('instance_api_key',''))" 2>/dev/null; chmod 600 vast/.instance_key_* 2>/dev/null
NOW=$(date -u +%FT%TZ); log "reeval: offer $LINE -> instance $IID"
python3 - "$IID" "$OFFER" "$RATE" "$NOW" <<'PY'
import sys; iid,offer,rate,now=sys.argv[1:5]; p='ledger.md'; t=open(p).read()
if "## LIVE INSTANCES\n(none created by this program)" in t: t=t.replace("## LIVE INSTANCES\n(none created by this program)", f"## LIVE INSTANCES\n- instance {iid}, RTX PRO 6000 96GB, offer {offer}, ${rate}/hr, created {now}, label j9-reeval. Destroy: `echo y | experiments/.venv/bin/vastai destroy instance {iid}`\n(none created by this program)")
t=t.rstrip('\n')+f"\n| 2026-09-08 | J9 reeval | {iid} | RTX PRO 6000 @ ${rate}/hr | (live, started {now}) | |\n"; open(p,'w').write(t)
PY
destroy() { echo y | .venv/bin/vastai destroy instance $IID | tail -1; log "instance $IID destroyed"; }
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/j9re.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/j9re.txt); P=$(awk '{print $3}' /tmp/j9re.txt); log "box running at $H:$P"
try ssh "${S[@]}" -p "$P" root@"$H" 'mkdir -p /root/gist /root/ratios && echo ready' | grep -q ready || { log "SSH_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/serve_ratio.sh vast/bootstrap_j5.sh gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@"$H":/root/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py root@"$H":/root/gist/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" -r loop/ratios/r8t4 loop/ratios/r8t2 root@"$H":/root/ratios/ || { log "COPY_FAILED"; destroy; exit 1; }
try ssh "${S[@]}" -p "$P" root@"$H" "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; pip install -q flash-linear-attention 2>&1 | tail -1; nohup setsid bash /root/bootstrap_j5.sh r8t4 > /root/bootstrap.log 2>&1 < /dev/null & IDLE_MIN=150 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & echo launched"
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "r8t4_READY|FAILED"; do sleep 30; done
echo "$OUT" | grep -q READY || { log "serve r8t4 failed"; destroy; exit 1; }
run_exam() { # $1 run  $2 tasks  $3 mode(gist|teacher)  $4 map  $5 scorer  $6 tport  $7 pport
  local run=$1 tasks=$2 mode=$3 map=$4 scorer=$5 tp=$6 pp=$7 lbl=re_$1
  pkill -f "ssh -N .* -L $tp:" 2>/dev/null; ssh -N "${S[@]}" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p "$P" -L $tp:127.0.0.1:8000 root@"$H" & local TUN=$!; sleep 6
  local gistarg=""; [ "$mode" = "gist" ] && gistarg="--gist $map --normalize qwen3.8-27b-gist=qwen3.8-27b"
  .venv/bin/python3 proxy/tap.py --listen 127.0.0.1:$pp --upstream http://127.0.0.1:$tp --log journeys/$J/results/reeval/$run.jsonl $gistarg > journeys/$J/results/reeval/$run.tap.log 2>&1 & local TAP=$!; sleep 2
  TAP_URL=http://127.0.0.1:$pp MODEL_NAME=qwen3.8-27b-gist KEEP=1 bash driver/run_sessions_local.sh "$tasks" "$lbl" "$CONC" > journeys/$J/results/reeval/$run.driver.log 2>&1
  kill $TAP $TUN 2>/dev/null; sleep 1
  local un=$(.venv/bin/python3 -c "import json; r=[json.loads(l) for l in open('journeys/$J/results/reeval/$run.jsonl')]; ok=[x for x in r if x.get('status')==200 and (x.get('request') or {}).get('tools')]; print(sum(1 for x in ok if x.get('gist_applied') is False),'unswapped of',len(ok))" 2>/dev/null)
  .venv/bin/python3 driver/$scorer "$tasks" journeys/$J/results/reeval/$run.jsonl "$SCR/work/$lbl" --json journeys/$J/results/reeval/$run.score.json > journeys/$J/results/reeval/$run.score.txt 2>&1
  log "$run: $(grep SUMMARY journeys/$J/results/reeval/$run.score.txt | cut -c1-110) | $un | 502s $(grep -c ' 502 ' journeys/$J/results/reeval/$run.tap.log)"
}
mkdir -p journeys/$J/results/reeval
export PATH="$SCR/sessionvenv/bin:$PATH"
run_exam teacher_hard driver/tasks_hard.txt teacher "" eval_hard.py 8310 8311
run_exam r8t4_hard driver/tasks_hard.txt gist gist/out_r8t4/segments.json eval_hard.py 8320 8321
run_exam r8t4_cov driver/tasks_coverage.txt gist gist/out_r8t4/segments.json eval_coverage.py 8330 8331
ssh "${S[@]}" -p "$P" root@"$H" 'bash /root/serve_ratio.sh r8t2; tail -1 /root/STATE' 2>/dev/null | tee -a journeys/$J/log.md
run_exam r8t2_hard driver/tasks_hard.txt gist gist/out_r8t2/segments.json eval_hard.py 8340 8341
run_exam r8t2_cov driver/tasks_coverage.txt gist gist/out_r8t2/segments.json eval_coverage.py 8350 8351
destroy; echo "J9_REEVAL_DONE"
