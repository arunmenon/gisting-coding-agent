#!/bin/bash
# run_seg.sh <run> : per-segment ratio run on the merged data; hard exam + teacher + coverage exam; teardown.
set -u; cd "$(dirname "$0")/.."; RUN=$1; KEY=$(cat ~/.config/vastai/vast_api_key); J=j9-seg-ratio
mkdir -p journeys/$J/results; [ -f journeys/$J/log.md ] || echo "# J9 ops log: per-segment ratio sweep (rules 8:1, tools 4:1 and 2:1) on base + coverage data, scored on the coverage exam" > journeys/$J/log.md
log() { echo "- $(date -u +%FT%TZ) $1" | tee -a journeys/$J/log.md; }
LINE=$(.venv/bin/vastai search offers "gpu_ram>=90 num_gpus=1 reliability>0.99 inet_down>1500 verified=true rentable=true disk_space>=150 cuda_vers>=12.8 dph_total<1.8" -o dph_total --raw 2>/dev/null | python3 -c "
import sys,json
bad={28810499,28810501,44111199,47849044,46474489,48659459,48659457,49566523,47550078,48778837,34545927}
seen=set(l.split()[0] for l in open('/tmp/j9_offers.txt')) if __import__('os').path.exists('/tmp/j9_offers.txt') else set()
for o in json.load(sys.stdin):
    if o['id'] in bad or str(o['id']) in seen or 'Spain' in (o.get('geolocation') or ''): continue
    print(o['id'], round(o['dph_total'],3), (o.get('geolocation') or '').replace(' ','_')); break")
echo "$LINE" >> /tmp/j9_offers.txt
OFFER=$(echo "$LINE" | awk '{print $1}'); RATE=$(echo "$LINE" | awk '{print $2}')
OUT=$(.venv/bin/vastai create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk 150 --ssh --direct --label j9-$RUN --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('vast/.instance_key_'+str(d['new_contract']),'w').write(d.get('instance_api_key',''))" 2>/dev/null; chmod 600 vast/.instance_key_* 2>/dev/null
NOW=$(date -u +%FT%TZ); log "$RUN: offer $LINE -> instance $IID"
python3 - "$IID" "$OFFER" "$RATE" "$NOW" "$RUN" <<'PY'
import sys; iid,offer,rate,now,run=sys.argv[1:6]; p='ledger.md'; t=open(p).read()
t=t.replace("(none other created by this program)", f"- instance {iid}, RTX PRO 6000 96GB, offer {offer}, ${rate}/hr, created {now}, label j9-{run}. Destroy: `echo y | experiments/.venv/bin/vastai destroy instance {iid}`\n(none other created by this program)")
t=t.rstrip('\n')+f"\n| 2026-09-08 | J9 {run} | {iid} | RTX PRO 6000 @ ${rate}/hr | (live, started {now}) | |\n"; open(p,'w').write(t)
PY
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/j9box_$RUN.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/j9box_$RUN.txt); P=$(awk '{print $3}' /tmp/j9box_$RUN.txt); log "$RUN: box running at $H:$P"; sleep 60
R=$(MAP=gist/out_$RUN DATA=journeys/$J/results/train_$RUN.jsonl.gz CACHE=journeys/j8-coverage/results/teacher_cache_merged.pt bash loop/provision.sh $RUN ${RUN#r} $H $P $IID 2>&1 | tail -1); log "$RUN: provision: $R"
echo "$R" | grep -q gist_count || { log "$RUN: PROVISION_FAILED; destroying"; echo y | .venv/bin/vastai destroy instance $IID | tail -1; exit 1; }
COVEXAM=1 bash loop/train_then_hard_eval.sh $RUN out_$RUN $H $P $IID $J
echo "J9_${RUN}_DONE"
