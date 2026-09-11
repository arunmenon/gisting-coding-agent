#!/bin/bash
# Provision the benchmark box, ship everything it needs, launch the chain + idle watchdog.
# Run from the workstation:  bash vast/bench_provision.sh            (H100 NVL 95GB, cheapest verified)
#   GPU_QUERY / DISK / LABEL / DEADLINE_H / IDLE_MIN overridable via env.
# Writes the ledger row immediately after creation (spend-safety rule).
set -u
cd "$(dirname "$0")/.."
VAST=.venv/bin/vastai; PY=.venv/bin/python3
KEY=$(cat ~/.vast_api_key)
LABEL="${LABEL:-j10-bench}"; DISK="${DISK:-160}"; DEADLINE_H="${DEADLINE_H:-8}"; IDLE_MIN="${IDLE_MIN:-45}"
GPU_QUERY="${GPU_QUERY:-gpu_name=H100_NVL num_gpus=1 verified=true rentable=true reliability>0.98 disk_space>150 inet_down>500}"
S="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
try() { for i in $(seq 1 30); do "$@" 2>/dev/null && return 0; sleep 30; done; return 1; }

# --- credit gate ---
CREDIT=$($PY -c "from vastai import VastAI; print(VastAI(api_key='$KEY').show_user()['credit'])")
echo "credit: \$$CREDIT"; $PY -c "import sys; sys.exit(0 if float('$CREDIT')>=30 else 1)" || { echo "credit below est+reserve, refusing to provision"; exit 1; }

# --- pick offer ---
OFFER=$($PY - <<PY
from vastai import VastAI
v=VastAI(api_key="$KEY")
o=v.search_offers(query="$GPU_QUERY", order="dph_total", limit=1)
print(o[0]["id"] if o else "")
PY
)
[ -n "$OFFER" ] || { echo "no offer for: $GPU_QUERY"; exit 1; }
$PY -c "
from vastai import VastAI; v=VastAI(api_key='$KEY'); o=[x for x in v.search_offers(query='$GPU_QUERY',order='dph_total',limit=5) if x['id']==$OFFER][0]
print('offer',o['id'],o['gpu_name'],o['gpu_ram'],'MB','\$%.2f/h'%o['dph_total'],'disk',int(o['disk_space']),'G inet',int(o['inet_down']),'rel',round(o['reliability2'],3),o['geolocation'])"

# --- create + ledger ---
OUT=$($VAST create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk $DISK --ssh --direct --label $LABEL --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | $PY -c "import sys,json; print(json.loads(sys.stdin.read()).get('new_contract',''))" 2>/dev/null)
[ -n "$IID" ] || { echo "create failed: $OUT"; exit 1; }
PRICE=$($PY -c "from vastai import VastAI; v=VastAI(api_key='$KEY'); print([x for x in v.search_offers(query='$GPU_QUERY',order='dph_total',limit=5) if x['id']==$OFFER][0]['dph_total'])" 2>/dev/null || echo "?")
echo "| $(date -u +%F) | J10 bench | $IID | H100 NVL @ \$$PRICE/hr | (running) | (running) |" >> ledger.md
echo "$(date -u +%FT%TZ) created instance $IID (offer $OFFER, \$$PRICE/hr) label=$LABEL" | tee -a journeys/j10-bench/log.md
echo "$IID" > journeys/j10-bench/instance_id

# --- wait for ssh ---
for i in $(seq 1 40); do
  read H P <<< "$($PY -c "from vastai import VastAI; v=VastAI(api_key='$KEY'); i=[x for x in v.show_instances() if x['id']==$IID]; print((i[0].get('ssh_host') or '')+' '+str(i[0].get('ssh_port') or '') if i else ' ')")"
  [ -n "$H" ] && [ -n "$P" ] && ssh $S -p $P root@$H 'echo ready' 2>/dev/null | grep -q ready && break
  sleep 30
done
[ -n "${H:-}" ] && [ -n "${P:-}" ] || { echo "ssh never came up for $IID"; exit 1; }
echo "$(date -u +%FT%TZ) ssh up: $H:$P" | tee -a journeys/j10-bench/log.md
echo "$H $P" > journeys/j10-bench/ssh

# --- ship files ---
try ssh $S -p $P root@$H 'mkdir -p /root/gist /root/corpus /root/bench_results && echo ok' | grep -q ok || { echo "mkdir failed"; exit 1; }
try scp $S -P $P vast/bench_chain.sh vast/serve_bench.sh vast/supervise_bench.sh vast/apply_gist_delta_bench.sh vast/idle_watchdog.sh \
     gist/mask_gist_logits.py gist/out/chat_template_gist.jinja bench/loadgen.py root@$H:/root/ || { echo "scp scripts failed"; exit 1; }
try scp $S -P $P gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py gist/dataset.py root@$H:/root/gist/ || { echo "scp gist failed"; exit 1; }
try scp $S -P $P -r gist/out_r8v2 gist/out_r16 root@$H:/root/gist/ || { echo "scp maps failed"; exit 1; }
try scp $S -P $P loop/ratios/r8v2/gist_rows.pt root@$H:/root/gist_rows_r8v2.pt || { echo "scp rows r8v2 failed"; exit 1; }
try scp $S -P $P loop/ratios/r16/gist_rows.pt  root@$H:/root/gist_rows_r16.pt  || { echo "scp rows r16 failed"; exit 1; }
try scp $S -P $P bench/corpus/reqs_*.jsonl bench/corpus/corpus_meta.json root@$H:/root/corpus/ || { echo "scp corpus failed"; exit 1; }
# vast key for the watchdog (mode 600, never logged)
try ssh $S -p $P root@$H "umask 077; printf '%s' '$KEY' > /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; echo keyok" | grep -q keyok || { echo "key install failed"; exit 1; }

# --- launch chain + watchdog ---
try ssh $S -p $P root@$H "DEADLINE_H=$DEADLINE_H nohup setsid bash /root/bench_chain.sh > /root/chain.log 2>&1 < /dev/null & IDLE_MIN=$IDLE_MIN nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & sleep 3; tail -2 /root/STATE; pgrep -f 'idle_[w]atchdog' | head -1 | xargs echo watchdog_pid" | tee -a journeys/j10-bench/log.md
echo "$(date -u +%FT%TZ) chain + watchdog launched on $IID" | tee -a journeys/j10-bench/log.md
