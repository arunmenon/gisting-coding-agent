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
JDIR="${JDIR:-$JDIR}"; LEDGER_LABEL="${LEDGER_LABEL:-J10 bench}"; GPU_LABEL="${GPU_LABEL:-H100 NVL}"
CHAIN_ENV="${CHAIN_ENV:-}"        # e.g. FIXED_CFG=40960,256,0.92,16384 B1_LADDER='1 2 4 8 16 32 64 128' B1_REPEATS=2 RUN_B3=0
SMOKE="${SMOKE:-0}"              # 1: ship + launch a trivial chain on a cheap box, verify milestones, destroy. Tests the provisioning path.
mkdir -p $JDIR/results
GPU_QUERY="${GPU_QUERY:-gpu_name=H100_NVL num_gpus=1 verified=true rentable=true reliability>0.98 disk_space>150 inet_down>500}"
S="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
RSH=vast/rsh.sh; LAUNCH_DEADLINE_MIN="${LAUNCH_DEADLINE_MIN:-25}"
STATEF=$JDIR/provision_state; : > $STATEF
ms() { echo "$(date -u +%FT%TZ) $1" | tee -a $STATEF $JDIR/log.md; }   # milestone: visible immediately
abort() {  # stall/failure after creation: destroy the box so a stuck provision is a bounded cost, not an open meter
  ms "ABORT: $1 -> destroying instance ${IID:-?}"
  [ -n "${IID:-}" ] && { $VAST destroy instance $IID >/dev/null 2>&1; sed -i '' "s/| $LEDGER_LABEL | $IID | \(.*\) | (running) | (running) |/| $LEDGER_LABEL | $IID | \1 | aborted | ~\$$(python3 -c "print(round((\$(date +%s)-$T_CREATE)/3600*${PRICE:-2.64},2))") |/" ledger.md; }
  exit 1
}
check_deadline() { [ $(( ($(date +%s)-T_CREATE)/60 )) -ge "$LAUNCH_DEADLINE_MIN" ] && abort "launch deadline ${LAUNCH_DEADLINE_MIN}m exceeded during: $1"; }

# --- credit gate ---
CREDIT=$($PY -c "from vastai import VastAI; print(VastAI(api_key='$KEY').show_user()['credit'])")
echo "credit: \$$CREDIT"; $PY -c "import sys; sys.exit(0 if float('$CREDIT')>=(5 if '$SMOKE'=='1' else 30) else 1)" || { echo "credit below est+reserve, refusing to provision"; exit 1; }

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
OUT=$($VAST create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk $DISK --ssh --direct --label $LABEL --raw 2>&1)
IID=$(echo "$OUT" | $PY -c "import sys,json; print(json.loads(sys.stdin.read()).get('new_contract',''))" 2>/dev/null)
[ -n "$IID" ] || { echo "create failed: $OUT"; exit 1; }
T_CREATE=$(date +%s)
PRICE=$($PY -c "from vastai import VastAI; v=VastAI(api_key='$KEY'); print([x for x in v.search_offers(query='$GPU_QUERY',order='dph_total',limit=5) if x['id']==$OFFER][0]['dph_total'])" 2>/dev/null || echo "?")
echo "| $(date -u +%F) | $LEDGER_LABEL | $IID | $GPU_LABEL @ \$$PRICE/hr | (running) | (running) |" >> ledger.md
echo "$(date -u +%FT%TZ) created instance $IID (offer $OFFER, \$$PRICE/hr) label=$LABEL" | tee -a $JDIR/log.md
echo "$IID" > $JDIR/instance_id

# --- wait for ssh: first endpoint that answers (direct, then proxy) ---
ms "waiting for ssh on $IID"
EP=$($RSH pick $IID) || abort "no ssh endpoint answered"
read H P <<< "$EP"; check_deadline "ssh wait"
ms "ssh up: $H:$P"; echo "$H $P" > $JDIR/ssh

# --- ship files (each step is a milestone; failures are printed, not swallowed) ---
$RSH run $H $P 'mkdir -p /root/gist /root/corpus /root/bench_results' || abort "mkdir"; ms "shipping scripts"
$RSH put $H $P vast/bench_chain.sh vast/serve_bench.sh vast/supervise_bench.sh vast/apply_gist_delta_bench.sh vast/idle_watchdog.sh gist/mask_gist_logits.py gist/out/chat_template_gist.jinja bench/loadgen.py /root/ || abort "scp scripts"
$RSH put $H $P gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py gist/dataset.py /root/gist/ || abort "scp gist"
$RSH put $H $P gist/out_r8v2 gist/out_r16 /root/gist/ || abort "scp maps"; check_deadline "ship maps"
$RSH put $H $P loop/ratios/r8v2/gist_rows.pt /root/gist_rows_r8v2.pt || abort "scp rows r8v2"
$RSH put $H $P loop/ratios/r16/gist_rows.pt /root/gist_rows_r16.pt || abort "scp rows r16"; ms "shipping corpus"
$RSH put $H $P bench/corpus/reqs_*.jsonl bench/corpus/corpus_meta.json /root/corpus/ || abort "scp corpus"; check_deadline "ship corpus"
$RSH put $H $P ~/.vast_api_key /root/.vast_key && $RSH run $H $P 'chmod 600 /root/.vast_key; chmod +x /root/*.sh' || abort "key install"
ms "shipped; launching chain"

# --- launch chain + watchdog ---
if [ "$SMOKE" = 1 ]; then $RSH run $H $P "printf '#!/bin/bash\necho \$(date -u +%%FT%%TZ) chain_start >> /root/STATE; sleep 30; echo \$(date -u +%%FT%%TZ) BENCH_DONE >> /root/STATE\n' > /root/bench_chain.sh"; fi
$RSH run $H $P "$CHAIN_ENV DEADLINE_H=$DEADLINE_H nohup setsid bash /root/bench_chain.sh > /root/chain.log 2>&1 < /dev/null & IDLE_MIN=$IDLE_MIN nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & sleep 4; tail -2 /root/STATE" || abort "launch"
$RSH run $H $P "pgrep -f 'bench_[c]hain' >/dev/null && pgrep -f 'idle_[w]atchdog' >/dev/null" || abort "chain or watchdog not running after launch"
ms "LAUNCHED chain + watchdog on $IID ($H:$P) after $(( ($(date +%s)-T_CREATE)/60 ))m"
if [ "$SMOKE" = 1 ]; then
  sleep 40; $RSH run $H $P 'cat /root/STATE' | grep -q BENCH_DONE && ms "SMOKE OK: provisioning path verified end to end" || ms "SMOKE FAILED: no BENCH_DONE marker"
  $VAST destroy instance $IID >/dev/null 2>&1 && ms "smoke box $IID destroyed"
  sed -i '' "s/| $LEDGER_LABEL | $IID | \(.*\) | (running) | (running) |/| $LEDGER_LABEL | $IID | \1 | smoke | ~\$0.05 |/" ledger.md
fi
