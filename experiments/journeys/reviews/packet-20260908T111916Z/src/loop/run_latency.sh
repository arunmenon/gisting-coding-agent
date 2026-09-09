#!/bin/bash
# End-to-end E8 latency journey: rent, provision, serve corrected 8:1, benchmark both arms, sync, destroy.
set -u; cd "$(dirname "$0")/.."
KEY=$(cat ~/.config/vastai/vast_api_key); J=j6-latency
log() { echo "- $(date -u +%FT%TZ) $1" | tee -a journeys/$J/log.md; }
S=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20)
try() { for i in $(seq 1 30); do "$@" 2>/dev/null && return 0; sleep 40; done; return 1; }
[ -f journeys/$J/log.md ] || echo "# J6 ops log: clean latency and throughput, teacher vs corrected 8:1 gist, one box" > journeys/$J/log.md
OFFER_LINE=$(.venv/bin/vastai search offers "gpu_ram>=90 num_gpus=1 reliability>0.99 inet_down>1500 verified=true rentable=true disk_space>=150 cuda_vers>=12.8 dph_total<1.8" -o dph_total --raw 2>/dev/null | python3 -c "
import sys,json
bad={28810499,28810501,44111199,47849044,46474489,48659459,48659457,49566523,47550078,48778837,34545927}
for o in json.load(sys.stdin):
    if o['id'] in bad or 'Spain' in (o.get('geolocation') or ''): continue
    print(o['id'], round(o['dph_total'],3), round(o['reliability2'],3), (o.get('geolocation') or '').replace(' ','_')); break")
OFFER=$(echo "$OFFER_LINE" | awk '{print $1}'); RATE=$(echo "$OFFER_LINE" | awk '{print $2}')
OUT=$(.venv/bin/vastai create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk 150 --ssh --direct --label j6-latency --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('vast/.instance_key_'+str(d['new_contract']),'w').write(d.get('instance_api_key',''))" 2>/dev/null; chmod 600 vast/.instance_key_* 2>/dev/null
NOW=$(date -u +%FT%TZ); log "offer $OFFER ($OFFER_LINE) -> instance $IID"
python3 - "$IID" "$OFFER" "$RATE" "$NOW" <<'PY'
import sys; iid,offer,rate,now=sys.argv[1:5]
p='ledger.md'; t=open(p).read()
t=t.replace("(none other created by this program)", f"- instance {iid}, RTX PRO 6000 96GB, offer {offer}, ${rate}/hr, created {now}, label j6-latency. Destroy: `echo y | experiments/.venv/bin/vastai destroy instance {iid}`\n(none other created by this program)")
t=t.rstrip('\n')+f"\n| 2026-09-07 | J6 | {iid} | RTX PRO 6000 @ ${rate}/hr | (live, started {now}) | |\n"; open(p,'w').write(t)
PY
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/j6box.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/j6box.txt); P=$(awk '{print $3}' /tmp/j6box.txt); log "box running at $H:$P; waiting for SSH (up to 20 min)"
try ssh "${S[@]}" -p "$P" root@"$H" 'mkdir -p /root/gist /root/ratios /root/data && echo ready' | grep -q ready || { log "SSH_FAILED; destroying"; echo y | .venv/bin/vastai destroy instance $IID | tail -1; exit 1; }
try scp "${S[@]}" -P "$P" vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/serve_ratio.sh vast/bootstrap_j5.sh vast/bench_latency.py gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@"$H":/root/ || { log "COPY1_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py root@"$H":/root/gist/ || { log "COPY2_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" -r loop/ratios/r8v2 root@"$H":/root/ratios/ || { log "COPY3_FAILED"; exit 1; }
try scp "${S[@]}" -P "$P" journeys/j5-hard-eval/results/train_r8v2.jsonl.gz root@"$H":/root/data/ || { log "COPY4_FAILED"; exit 1; }
log "copied; launching bootstrap (download + serve r8v2) and watchdog"
try ssh "${S[@]}" -p "$P" root@"$H" "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; gunzip -c /root/data/train_r8v2.jsonl.gz > /root/data/train.jsonl; nohup setsid bash /root/bootstrap_j5.sh r8v2 > /root/bootstrap.log 2>&1 < /dev/null & IDLE_MIN=90 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & sleep 2; echo launched"
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "r8v2_READY|FAILED"; do sleep 30; done
log "bootstrap: $OUT"; echo "$OUT" | grep -q READY || { echo y | .venv/bin/vastai destroy instance $IID | tail -1; exit 1; }
log "benchmark start"
ssh "${S[@]}" -p "$P" root@"$H" 'cd /root && python3 bench_latency.py /root/data/train.jsonl /root/bench.json > /root/bench.log 2>&1; tail -2 /root/bench.log' 2>/dev/null
try scp "${S[@]}" -P "$P" root@"$H":/root/bench.json root@"$H":/root/bench.log root@"$H":/root/vllm_gist.log journeys/$J/results/
log "benchmark done: $(tail -1 journeys/$J/results/bench.log | cut -c1-80)"
echo y | .venv/bin/vastai destroy instance $IID | tail -1; log "instance $IID destroyed"
echo "J6_DONE"
