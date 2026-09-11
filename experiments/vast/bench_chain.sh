#!/bin/bash
# On-box orchestrator for the serving-throughput benchmark (B0, BT, B1-B4, plus the 16:1 arm).
# Detached under nohup setsid. Progress markers in /root/STATE; results in /root/bench_results/.
# Terminal markers: BENCH_DONE, *_FAILED, DEADLINE.
set -u
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
R=/root/bench_results; mkdir -p $R; touch /root/CHAIN_RUNNING; trap 'rm -f /root/CHAIN_RUNNING' EXIT
LG="python3 /root/loadgen.py --url http://127.0.0.1:8000"
DEADLINE_H="${DEADLINE_H:-8}"; T0=$(date +%s)
over_deadline() { [ $(( ($(date +%s)-T0)/3600 )) -ge "$DEADLINE_H" ]; }
healthy() { curl -s -m 20 localhost:8000/v1/models -o /dev/null -w "%{http_code}" | grep -q 200; }
wait_health() { for i in $(seq 1 90); do healthy && return 0; [ -f /root/SERVE_FAILED ] && return 1; sleep 10; done; return 1; }
stop_server() { touch /root/STOP; pkill -f "vllm [s]erve" 2>/dev/null; pkill -f "super[v]ise_bench" 2>/dev/null; sleep 12; rm -f /root/STOP /root/SERVE_FAILED; }
# start_server LEN SEQS UTIL BATCHED PREFIX CKPT
start_server() {
  stop_server
  MAX_MODEL_LEN=$1 MAX_NUM_SEQS=$2 GPU_UTIL=$3 MAX_BATCHED=$4 PREFIX_CACHE=$5 CKPT=${6:-/root/qwen3.8-27b-gist} \
    nohup setsid bash /root/supervise_bench.sh > /dev/null 2>&1 < /dev/null &
  if wait_health; then mark "server_up len=$1 seqs=$2 util=$3 batched=$4 prefix=$5 ckpt=$(basename ${6:-/root/qwen3.8-27b-gist})"; return 0
  else mark "server_FAILED len=$1 seqs=$2 util=$3 batched=$4 prefix=$5"; stop_server; return 1; fi
}
# run ARM REQFILE TAG MODE VALUE REPEAT DURATION [extra]
run() {
  local arm=$1 req=$2 tag=$3 mode=$4 val=$5 rep=$6 dur=$7; shift 7
  local out; if [ "$mode" = closed ]; then out="$R/${tag}_${arm}_c${val}_r${rep}.json"; v="--concurrency $val"; else out="$R/${tag}_${arm}_rps${val}_r${rep}.json"; v="--rps $val"; fi
  $LG --requests /root/corpus/$req --arm $arm --tag $tag --mode $mode $v --repeat $rep --warmup 15 --duration $dur --out "$out" "$@" >> $R/progress.log 2>&1 \
    && echo "$(date -u +%FT%TZ) ok $out" >> $R/progress.log || echo "$(date -u +%FT%TZ) FAIL $out" >> $R/progress.log
}
prewarm() { $LG --requests /root/corpus/$1 --arm warm --tag warm --mode closed --concurrency 4 --repeat 0 --warmup 0 --duration 25 --out /tmp/warm.json > /dev/null 2>&1; }

mark "chain_start deadline=${DEADLINE_H}h"
FREE_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G'); [ "${FREE_GB:-0}" -lt 120 ] && { mark "disk_FAILED free=${FREE_GB}G"; exit 1; }
export HF_XET_HIGH_PERFORMANCE=1
pip install -q -U "huggingface_hub[hf_xet]" flash-linear-attention aiohttp 2>&1 | grep -vE "WARNING|notice" | tail -1
ok=0; for a in 1 2 3; do mark "download_attempt_$a"; hf download Qwen/Qwen3.8-27B > /root/download.log 2>&1 && { ok=1; break; }; sleep 30; done
[ $ok -eq 1 ] || { mark "download_FAILED"; exit 1; }

# ---- build the 8:1 (r8v2) checkpoint: grow -> apply delta -> write trained rows ----
build_ckpt() {  # build_ckpt OUTDIR_NAME ROWS_PT CKPT_DIR
  rm -rf /root/gist/out && cp -r /root/gist/$1 /root/gist/out
  (cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare_$1.log 2>&1) || { mark "prepare_FAILED $1"; tail -3 /root/prepare_$1.log; return 1; }
  rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta
  OUT=$3 bash /root/apply_gist_delta_bench.sh > /root/apply_$1.log 2>&1 || { mark "apply_FAILED $1"; tail -3 /root/apply_$1.log; return 1; }
  cp /root/delta/gist_meta.json $3/gist_meta.json
  python3 /root/gist/export_rows.py $3 $2 > /root/export_$1.log 2>&1 || { mark "export_FAILED $1"; return 1; }
  mark "ckpt_built $1 -> $3 ($(cat /root/export_$1.log | tail -1))"
}
build_ckpt out_r8v2 /root/gist_rows_r8v2.pt /root/qwen3.8-27b-gist || exit 1

# ---- B0: smoke on the paper's baseline config (also gives 'untuned' reference numbers) ----
start_server 131072 64 0.80 4096 1 || { mark "B0_FAILED"; exit 1; }
run full  reqs_full_smoke.jsonl  B0smoke closed 1 1 30
run gist8 reqs_gist8_smoke.jsonl B0smoke closed 1 1 30
python3 - <<'PY' || { mark "B0_FAILED smoke sanity"; exit 1; }
import json,glob
for f in glob.glob("/root/bench_results/B0smoke_*.json"):
    s=json.load(open(f))["summary"]; assert s["requests_ok"]>0 and s["errors"]==0 and s["ttft_p50"]>0, f
print("smoke ok")
PY
mark "B0_smoke_ok"
prewarm reqs_gist8.jsonl; run gist8 reqs_gist8.jsonl B0base closed 8 1 90
prewarm reqs_full.jsonl;  run full  reqs_full.jsonl  B0base closed 8 1 90
mark "B0_done (paper-config reference at c=8 recorded)"

# ---- BT: serving-config tuning (same config will be used for BOTH arms) ----
# candidates: LEN SEQS UTIL BATCHED   (fp8 KV excluded: needs a quality check first)
CANDS="40960,64,0.90,8192 40960,128,0.90,8192 40960,256,0.92,16384 40960,128,0.92,16384"
BEST=""; BEST_SCORE=0
for c in $CANDS; do
  over_deadline && { mark "DEADLINE during BT"; break; }
  IFS=, read LEN SEQS UTIL BAT <<< "$c"
  start_server $LEN $SEQS $UTIL $BAT 1 || continue
  prewarm reqs_gist8.jsonl
  PROBE=$(( SEQS < 32 ? SEQS : 32 ))
  run gist8 reqs_gist8.jsonl "BT_${LEN}_${SEQS}_${UTIL}_${BAT}" closed $PROBE 1 60
  f=$(ls -t $R/BT_${LEN}_${SEQS}_${UTIL}_${BAT}_gist8_c${PROBE}_r1.json 2>/dev/null | head -1)
  score=$(python3 -c "import json,sys; s=json.load(open('$f'))['summary']; print(int(s['throughput_rpm']*100) if s['errors']==0 else 0)" 2>/dev/null || echo 0)
  mark "BT cand len=$LEN seqs=$SEQS util=$UTIL batched=$BAT probe_c=$PROBE score=$score"
  if [ "$score" -gt "$BEST_SCORE" ]; then BEST_SCORE=$score; BEST="$c"; fi
done
[ -n "$BEST" ] || { mark "BT_FAILED no config started"; exit 1; }
IFS=, read LEN SEQS UTIL BAT <<< "$BEST"; echo "$BEST" > $R/best_config.txt
mark "BT_done best=len:$LEN,seqs:$SEQS,util:$UTIL,batched:$BAT (score=$BEST_SCORE)"

# ---- B1: saturation & capacity curve, full vs gist8, 3 repeats, balanced arm order ----
LADDER="1 2 4 8 16 32 48 64"; [ "$SEQS" -ge 128 ] && LADDER="$LADDER 96 128"; [ "$SEQS" -ge 256 ] && LADDER="$LADDER 192 256"
echo "$LADDER" > $R/ladder.txt
start_server $LEN $SEQS $UTIL $BAT 1 || { mark "B1_FAILED server"; exit 1; }
for rep in 1 2 3; do
  over_deadline && { mark "DEADLINE during B1"; break; }
  if [ $((rep % 2)) -eq 1 ]; then ARMS="full gist8"; else ARMS="gist8 full"; fi
  for arm in $ARMS; do
    req=$([ $arm = full ] && echo reqs_full.jsonl || echo reqs_gist8.jsonl)
    prewarm $req
    for c in $LADDER; do run $arm $req B1 closed $c $rep 90; done
  done
  mark "B1_repeat_${rep}_done"
done
mark "B1_done"

# ---- B2: KV-cache ceiling (max concurrent sequences, kv usage, preemptions) ----
for arm in full gist8; do
  over_deadline && { mark "DEADLINE during B2"; break; }
  req=$([ $arm = full ] && echo reqs_full.jsonl || echo reqs_gist8.jsonl)
  prewarm $req; run $arm $req B2 closed $SEQS 1 120 --sample-every 2
done
mark "B2_done"

# ---- B3: open-loop Poisson arrivals, rising RPS, 2 repeats ----
for rep in 1 2; do
  over_deadline && { mark "DEADLINE during B3"; break; }
  for arm in full gist8; do
    req=$([ $arm = full ] && echo reqs_full.jsonl || echo reqs_gist8.jsonl)
    prewarm $req
    for rps in 0.15 0.3 0.45 0.6 0.9 1.2; do run $arm $req B3 open $rps $rep 90; done
  done
done
mark "B3_done"

# ---- B4: prefix-cache OFF ablation (cache-ON values come from B1) ----
if ! over_deadline; then
  if start_server $LEN $SEQS $UTIL $BAT 0; then
    for rep in 1 2; do for arm in full gist8; do
      req=$([ $arm = full ] && echo reqs_full.jsonl || echo reqs_gist8.jsonl)
      for c in 4 8 16; do run $arm $req B4nocache closed $c $rep 90; done
    done; done
    mark "B4_done"
  else mark "B4_FAILED server"; fi
fi

# ---- 16:1 arm on its own checkpoint (same tuned config) ----
if ! over_deadline; then
  stop_server
  if build_ckpt out_r16 /root/gist_rows_r16.pt /root/qwen3.8-27b-gist16 && start_server $LEN $SEQS $UTIL $BAT 1 /root/qwen3.8-27b-gist16; then
    for rep in 1 2; do
      over_deadline && { mark "DEADLINE during gist16"; break; }
      for arm in gist16 full16; do
        req=reqs_${arm}.jsonl; prewarm $req
        for c in $LADDER; do run $arm $req B1 closed $c $rep 90; done
      done
    done
    mark "B1_gist16_done"
  else mark "gist16_FAILED"; fi
fi

stop_server
cp /root/vllm_bench.log $R/ 2>/dev/null; cp /root/STATE $R/ 2>/dev/null; cp /root/corpus/corpus_meta.json $R/ 2>/dev/null
mark "BENCH_DONE"
