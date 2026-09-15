#!/bin/bash
# J11 / B6: does the engine hold more than 100 concurrent sequences once the
# client stops capping them? Review finding F-4-1 showed aiohttp's default
# 100-connection limit, not the hardware, produced the "100 resident in both
# arms" observation on the H200 that the turnover mechanism was built on.
#
# Design: same tuned server config as B5, both arms, two concurrencies, with the
# client connection cap set explicitly to 100 (reproduces the confound) and to
# 512 (removes it). If residency stays at 100 with the cap lifted, the ceiling is
# real. If it exceeds 100, the mechanism claim must be withdrawn.
set -u
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
R=/root/bench_results; mkdir -p $R; touch /root/CHAIN_RUNNING; trap 'rm -f /root/CHAIN_RUNNING' EXIT
LG="python3 /root/loadgen.py --url http://127.0.0.1:8000"
DEADLINE_H="${DEADLINE_H:-3}"; T0=$(date +%s)
CFG="${FIXED_CFG:-40960,256,0.92,16384}"
CONCS="${CONCS:-128 256}"; CONNS="${CONNS:-100 512}"; DUR="${DUR:-180}"; WARM="${WARM:-30}"
over_deadline() { [ $(( ($(date +%s)-T0)/3600 )) -ge "$DEADLINE_H" ]; }
healthy() { curl -s -m 20 localhost:8000/v1/models -o /dev/null -w "%{http_code}" | grep -q 200; }
wait_health() { for i in $(seq 1 90); do healthy && return 0; [ -f /root/SERVE_FAILED ] && return 1; sleep 10; done; return 1; }
stop_server() { touch /root/STOP; pkill -f "vllm [s]erve" 2>/dev/null; pkill -f "super[v]ise_bench" 2>/dev/null; sleep 12; rm -f /root/STOP /root/SERVE_FAILED; }
start_server() {
  stop_server
  MAX_MODEL_LEN=$1 MAX_NUM_SEQS=$2 GPU_UTIL=$3 MAX_BATCHED=$4 PREFIX_CACHE=1 CKPT=/root/qwen3.8-27b-gist \
    nohup setsid bash /root/supervise_bench.sh > /dev/null 2>&1 < /dev/null &
  if wait_health; then mark "server_up len=$1 seqs=$2 util=$3 batched=$4"; return 0
  else mark "server_FAILED len=$1 seqs=$2 util=$3 batched=$4"; return 1; fi
}
prewarm() { $LG --requests /root/corpus/$1 --arm warm --tag warm --mode closed --concurrency 8 --repeat 0 --warmup 0 --duration 30 --conn-limit 0 --out /tmp/warm.json > /dev/null 2>&1; }

mark "conn_chain_start deadline=${DEADLINE_H}h cfg=$CFG concs='$CONCS' conns='$CONNS' dur=${DUR}s"
FREE_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G'); [ "${FREE_GB:-0}" -lt 120 ] && { mark "disk_FAILED free=${FREE_GB}G"; exit 1; }
export HF_XET_HIGH_PERFORMANCE=1
pip install -q -U "huggingface_hub[hf_xet]" flash-linear-attention aiohttp 2>&1 | grep -vE "WARNING|notice" | tail -1
ok=0; for a in 1 2 3; do mark "download_attempt_$a"; hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 && { ok=1; break; }; sleep 30; done
[ $ok -eq 1 ] || { mark "download_FAILED"; exit 1; }

# 8:1 (r8v2) checkpoint, identical to the one B1/B2/B5 served
rm -rf /root/gist/out && cp -r /root/gist/out_r8v2 /root/gist/out
(cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare.log 2>&1) || { mark "prepare_FAILED"; tail -3 /root/prepare.log; exit 1; }
rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
OUT=/root/qwen3.8-27b-gist bash /root/apply_gist_delta_bench.sh > /root/apply.log 2>&1 || { mark "apply_FAILED"; tail -3 /root/apply.log; exit 1; }
cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json
python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist /root/gist_rows_r8v2.pt > /root/export.log 2>&1 || { mark "export_FAILED"; exit 1; }
mark "ckpt_built ($(tail -1 /root/export.log))"

IFS=, read LEN SEQS UTIL BAT <<< "$CFG"
start_server $LEN $SEQS $UTIL $BAT || exit 1

# B6: conn-limit x arm x concurrency. Order interleaved so drift cannot favour one cap.
for conn in $CONNS; do
  for arm in full gist8; do
    req=$([ $arm = full ] && echo reqs_full.jsonl || echo reqs_gist8.jsonl)
    prewarm $req
    for c in $CONCS; do
      over_deadline && { mark "DEADLINE during B6"; break 3; }
      out="$R/B6_conn${conn}_${arm}_c${c}_r1.json"
      $LG --requests /root/corpus/$req --arm $arm --tag "B6conn${conn}" --mode closed \
          --concurrency $c --conn-limit $conn --repeat 1 --warmup $WARM --duration $DUR --out "$out" >> $R/progress.log 2>&1 \
        && mark "B6 $(python3 -c "
import json;s=json.load(open('$out'))['summary'];e=s['engine']
print('conn=$conn arm=$arm c=$c rpm=%.1f max_running=%s kv_max=%.3f preempt=%s ok=%d err=%d'%(s['throughput_rpm'],e.get('max_running_seqs'),e.get('kv_usage_max') or 0,e.get('preemptions'),s['requests_ok'],s['errors']))")" \
        || mark "B6_FAILED conn=$conn arm=$arm c=$c"
    done
  done
done
mark "B6_done"

python3 - <<'PY' | tee -a /root/STATE
import json,glob
print("=== VERDICT: max resident sequences by client connection cap ===")
rows={}
for f in sorted(glob.glob("/root/bench_results/B6_*.json")):
    s=json.load(open(f))["summary"]; e=s["engine"]
    rows[(s["conn_limit"],s["arm"],s["concurrency"])]=(e.get("max_running_seqs"),s["throughput_rpm"],e.get("kv_usage_max"))
for k in sorted(rows): print("conn=%-4s %-6s c=%-4s max_running=%-6s rpm=%-6s kv=%s"%(k[0],k[1],k[2],*rows[k]))
hi=[v[0] for k,v in rows.items() if k[0]==512 and v[0]]
if hi: print("RESULT: with the cap lifted, max resident =",max(hi),"->", "ceiling is NOT 100, mechanism claim must be withdrawn" if max(hi)>100 else "ceiling holds at ~100, mechanism survives")
PY
mark "BENCH_DONE"
