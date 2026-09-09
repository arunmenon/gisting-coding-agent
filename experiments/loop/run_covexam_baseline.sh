#!/bin/bash
# Eval-only: serve the pre-coverage corrected 8:1 (r8v2) and run the coverage exam in gist mode, then destroy.
set -u; cd "$(dirname "$0")/.."; KEY=$(cat ~/.config/vastai/vast_api_key); J=j8-coverage
log() { echo "- $(date -u +%FT%TZ) $1" | tee -a journeys/$J/log.md; }
S=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20)
try() { for i in $(seq 1 30); do "$@" 2>/dev/null && return 0; sleep 40; done; return 1; }
LINE=$(.venv/bin/vastai search offers "gpu_ram>=90 num_gpus=1 reliability>0.99 inet_down>1500 verified=true rentable=true disk_space>=150 cuda_vers>=12.8 dph_total<1.8" -o dph_total --raw 2>/dev/null | python3 -c "
import sys,json
bad={28810499,28810501,44111199,47849044,46474489,48659459,48659457,49566523,47550078,48778837,34545927}
for o in json.load(sys.stdin):
    if o['id'] in bad or 'Spain' in (o.get('geolocation') or ''): continue
    print(o['id'], round(o['dph_total'],3), (o.get('geolocation') or '').replace(' ','_')); break")
OFFER=$(echo "$LINE" | awk '{print $1}'); RATE=$(echo "$LINE" | awk '{print $2}')
OUT=$(.venv/bin/vastai create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk 150 --ssh --direct --label j8-baseline --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('vast/.instance_key_'+str(d['new_contract']),'w').write(d.get('instance_api_key',''))" 2>/dev/null; chmod 600 vast/.instance_key_* 2>/dev/null
NOW=$(date -u +%FT%TZ); log "baseline coverage exam: offer $LINE -> instance $IID"
python3 - "$IID" "$OFFER" "$RATE" "$NOW" <<'PY'
import sys; iid,offer,rate,now=sys.argv[1:5]; p='ledger.md'; t=open(p).read()
t=t.replace("(none other created by this program)", f"- instance {iid}, RTX PRO 6000 96GB, offer {offer}, ${rate}/hr, created {now}, label j8-baseline. Destroy: `echo y | experiments/.venv/bin/vastai destroy instance {iid}`\n(none other created by this program)")
t=t.rstrip('\n')+f"\n| 2026-09-07 | J8 baseline | {iid} | RTX PRO 6000 @ ${rate}/hr | (live, started {now}) | |\n"; open(p,'w').write(t)
PY
destroy() { echo y | .venv/bin/vastai destroy instance $IID | tail -1; log "instance $IID destroyed"; }
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/j8bbox.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/j8bbox.txt); P=$(awk '{print $3}' /tmp/j8bbox.txt); log "box running at $H:$P"
try ssh "${S[@]}" -p "$P" root@"$H" 'mkdir -p /root/gist /root/ratios && echo ready' | grep -q ready || { log "SSH_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/serve_ratio.sh vast/bootstrap_j5.sh vast/gen_test.py gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@"$H":/root/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py root@"$H":/root/gist/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" -r loop/ratios/r8v2 root@"$H":/root/ratios/ || { log "COPY_FAILED"; destroy; exit 1; }
try ssh "${S[@]}" -p "$P" root@"$H" "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; nohup setsid bash /root/bootstrap_j5.sh r8v2 > /root/bootstrap.log 2>&1 < /dev/null & IDLE_MIN=90 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & echo launched"
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "r8v2_READY|FAILED"; do sleep 30; done
log "bootstrap: $OUT"; echo "$OUT" | grep -q READY || { destroy; exit 1; }
pkill -f "ssh -N .* -L 8400:" 2>/dev/null; ssh -N "${S[@]}" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p "$P" -L 8400:127.0.0.1:8000 root@"$H" & TUN=$!; sleep 6
.venv/bin/python3 proxy/tap.py --listen 127.0.0.1:8401 --upstream http://127.0.0.1:8400 --log journeys/$J/results/requests_covexam_baseline.jsonl --gist gist/out_r8v2/segments.json --normalize "qwen3.8-27b-gist=qwen3.8-27b" > journeys/$J/results/tap_covexam_baseline.log 2>&1 & TAP=$!; sleep 2
log "baseline coverage exam running"
TAP_URL=http://127.0.0.1:8401 MODEL_NAME=qwen3.8-27b-gist KEEP=1 bash driver/run_sessions_local.sh driver/tasks_coverage.txt covexam_base 4 > journeys/$J/results/driver_covexam_baseline.log 2>&1
kill $TAP $TUN 2>/dev/null
.venv/bin/python3 driver/eval_coverage.py driver/tasks_coverage.txt journeys/$J/results/requests_covexam_baseline.jsonl --json journeys/$J/results/baseline_coverage.json > journeys/$J/results/baseline_coverage.txt 2>&1; log "baseline (pre-coverage r8v2) coverage: $(grep SUMMARY journeys/$J/results/baseline_coverage.txt | cut -c1-140)"
destroy; echo "J8B_DONE"
