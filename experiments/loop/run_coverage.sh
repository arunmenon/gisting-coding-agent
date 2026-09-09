#!/bin/bash
# Coverage journey: serve corrected 8:1 (teacher arm = passthrough), collect sessions that exercise the unused
# tools, cache their teacher log-probs, retrain 8:1 on base + coverage data, hard exam + coverage exam, destroy.
set -u; cd "$(dirname "$0")/.."; KEY=$(cat ~/.config/vastai/vast_api_key); J=j8-coverage; RUN=r8v2cov
SCR=/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad
mkdir -p journeys/$J/results/$RUN; [ -f journeys/$J/log.md ] || echo "# J8 ops log: coverage sessions for the 18 unused tools, retrain corrected 8:1 on base + coverage, hard exam + coverage exam" > journeys/$J/log.md
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
OUT=$(.venv/bin/vastai create instance $OFFER --image vllm/vllm-openai:v0.28.0 --disk 150 --ssh --direct --label j8-coverage --raw 2>&1 | sed "s/$KEY/REDACTED/g")
IID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); open('vast/.instance_key_'+str(d['new_contract']),'w').write(d.get('instance_api_key',''))" 2>/dev/null; chmod 600 vast/.instance_key_* 2>/dev/null
NOW=$(date -u +%FT%TZ); log "offer $LINE -> instance $IID"
python3 - "$IID" "$OFFER" "$RATE" "$NOW" <<'PY'
import sys; iid,offer,rate,now=sys.argv[1:5]; p='ledger.md'; t=open(p).read()
t=t.replace("(none other created by this program)", f"- instance {iid}, RTX PRO 6000 96GB, offer {offer}, ${rate}/hr, created {now}, label j8-coverage. Destroy: `echo y | experiments/.venv/bin/vastai destroy instance {iid}`\n(none other created by this program)")
t=t.rstrip('\n')+f"\n| 2026-09-07 | J8 | {iid} | RTX PRO 6000 @ ${rate}/hr | (live, started {now}) | |\n"; open(p,'w').write(t)
PY
destroy() { echo y | .venv/bin/vastai destroy instance $IID | tail -1; log "instance $IID destroyed"; }
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/j8box.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/j8box.txt); P=$(awk '{print $3}' /tmp/j8box.txt); log "box running at $H:$P"
try ssh "${S[@]}" -p "$P" root@"$H" 'mkdir -p /root/gist /root/ratios /root/data && echo ready' | grep -q ready || { log "SSH_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/serve_ratio.sh vast/bootstrap_j5.sh vast/gen_test.py gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@"$H":/root/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/export_rows.py gist/train.py gist/teacher_cache.py root@"$H":/root/gist/ || { log "COPY_FAILED"; destroy; exit 1; }
try scp "${S[@]}" -P "$P" -r loop/ratios/r8v2 root@"$H":/root/ratios/ || { log "COPY_FAILED"; destroy; exit 1; }
try ssh "${S[@]}" -p "$P" root@"$H" "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; pip install -q flash-linear-attention 2>&1 | tail -1; nohup setsid bash /root/bootstrap_j5.sh r8v2 > /root/bootstrap.log 2>&1 < /dev/null & IDLE_MIN=150 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & echo launched"
until OUT=$(ssh "${S[@]}" -p "$P" root@"$H" 'tail -1 /root/STATE' 2>/dev/null) && echo "$OUT" | grep -qE "r8v2_READY|FAILED"; do sleep 30; done
log "bootstrap: $OUT"; echo "$OUT" | grep -q READY || { destroy; exit 1; }
# ---- collect coverage sessions through the teacher (passthrough), 3 passes over the 16 tasks
pkill -f "ssh -N .* -L 8400:" 2>/dev/null; ssh -N "${S[@]}" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p "$P" -L 8400:127.0.0.1:8000 root@"$H" & TUN=$!; sleep 6
.venv/bin/python3 proxy/tap.py --listen 127.0.0.1:8401 --upstream http://127.0.0.1:8400 --log journeys/$J/results/requests_cov.jsonl > journeys/$J/results/tap_cov.log 2>&1 & TAP=$!; sleep 2
log "collecting coverage sessions"
for pass in 1 2 3; do TAP_URL=http://127.0.0.1:8401 MODEL_NAME=qwen3.8-27b-gist KEEP=1 bash driver/run_sessions_local.sh driver/tasks_coverage.txt cov$pass 4 > journeys/$J/results/driver_cov$pass.log 2>&1; done
kill $TAP 2>/dev/null
log "collected: $(grep -c '^s' journeys/$J/results/driver_cov*.log | tr '\n' ' ')"
# teacher-arm coverage score (same sessions) for reference
.venv/bin/python3 driver/eval_coverage.py driver/tasks_coverage.txt journeys/$J/results/requests_cov.jsonl --json journeys/$J/results/teacher_coverage.json > journeys/$J/results/teacher_coverage.txt 2>&1; log "teacher coverage: $(grep SUMMARY journeys/$J/results/teacher_coverage.txt | cut -c1-120)"
# ---- examples + teacher cache for the new turns
GIST_OUT=gist/out_r8v2 .venv/bin/python3 gist/dataset.py journeys/$J/results/requests_cov.jsonl journeys/$J/results/train_cov.jsonl > journeys/$J/results/dataset_cov.log 2>&1; log "dataset: $(tail -1 journeys/$J/results/dataset_cov.log | cut -c1-100)"
gzip -kf journeys/$J/results/train_cov.jsonl; try scp "${S[@]}" -P "$P" journeys/$J/results/train_cov.jsonl.gz root@"$H":/root/data/
ssh "${S[@]}" -p "$P" root@"$H" 'gunzip -c /root/data/train_cov.jsonl.gz > /root/data/train_cov.jsonl; cd /root/gist && python3 teacher_cache.py /root/data/train_cov.jsonl /root/teacher_cache_cov.pt 32 60000 2 > /root/teacher_cache_cov.log 2>&1; tail -1 /root/teacher_cache_cov.log' 2>/dev/null | tee -a journeys/$J/log.md
kill $TUN 2>/dev/null
try scp "${S[@]}" -P "$P" root@"$H":/root/teacher_cache_cov.pt journeys/$J/results/
.venv/bin/python3 loop/merge_cache.py journeys/j5-hard-eval/results/train_r8v2.jsonl journeys/j3-e3-e2/results/teacher_cache.pt journeys/$J/results/train_cov.jsonl journeys/$J/results/teacher_cache_cov.pt journeys/$J/results/train_merged.jsonl journeys/$J/results/teacher_cache_merged.pt | tee -a journeys/$J/log.md
gzip -kf journeys/$J/results/train_merged.jsonl; try scp "${S[@]}" -P "$P" journeys/$J/results/train_merged.jsonl.gz journeys/$J/results/teacher_cache_merged.pt root@"$H":/root/data/
# ---- train on merged data (rows restart from mean-chunk init: the delta on the box is the r8v2 init since serve_ratio wrote the trained rows in; rebuild from the map first)
log "training on merged data"
ssh "${S[@]}" -p "$P" root@"$H" 'touch /root/STOP; pkill -f "vllm [s]erve"; pkill -f "super[v]ise_gist"; sleep 10; rm -f /root/STOP; gunzip -c /root/data/train_merged.jsonl.gz > /root/data/train.jsonl; cd /root/gist && HF_HUB_OFFLINE=1 python3 prepare_checkpoint.py > /root/prepare_cov.log 2>&1 && rm -rf /root/delta && cp -r /root/gist/out/checkpoint_delta /root/delta && bash /root/apply_gist_delta.sh > /root/apply_cov.log 2>&1 && cp /root/delta/gist_meta.json /root/qwen3.8-27b-gist/gist_meta.json && python3 train.py --data /root/data/train.jsonl --model /root/qwen3.8-27b-gist --teacher-cache /root/data/teacher_cache_merged.pt --epochs 1 --accum 8 --lr 1e-3 --student-max-len 30000 --eval-every 40 --eval-n 24 --out /root/gist_rows.pt > /root/train.log 2>&1; grep -E "eval KL" /root/train.log | tr "\n" " "; python3 /root/gist/export_rows.py /root/qwen3.8-27b-gist /root/gist_rows.pt > /root/export.log 2>&1; mkdir -p /root/ratios/r8v2cov && cp /root/gist/out/segments.json /root/ratios/r8v2cov/ && cp -r /root/gist/out/tokenizer /root/ratios/r8v2cov/ && cp /root/gist_rows.pt /root/ratios/r8v2cov/; cat /root/export.log' 2>/dev/null | tee -a journeys/$J/log.md
try scp "${S[@]}" -P "$P" root@"$H":/root/train.log root@"$H":/root/gist_rows.pt journeys/$J/results/$RUN/
mkdir -p loop/ratios/$RUN && cp gist/out_r8v2/segments.json loop/ratios/$RUN/ && cp -r gist/out_r8v2/tokenizer loop/ratios/$RUN/
echo "{\"host\": \"$H\", \"port\": $P, \"instance\": $IID}" > loop/evalbox_$RUN.json
# ---- hard exam (gist arm + teacher arm), then coverage exam in gist mode
.venv/bin/python3 loop/eval_sweep.py loop/evalbox_$RUN.json "$J" driver/tasks_hard.txt "$RUN" teacher > logs/eval_sweep_${RUN}.log 2>&1
pkill -f "ssh -N .* -L 8400:" 2>/dev/null; ssh -N "${S[@]}" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p "$P" -L 8400:127.0.0.1:8000 root@"$H" & TUN=$!; sleep 6
.venv/bin/python3 proxy/tap.py --listen 127.0.0.1:8401 --upstream http://127.0.0.1:8400 --log journeys/$J/results/requests_covexam.jsonl --gist gist/out_r8v2/segments.json --normalize "qwen3.8-27b-gist=qwen3.8-27b" > journeys/$J/results/tap_covexam.log 2>&1 & TAP=$!; sleep 2
TAP_URL=http://127.0.0.1:8401 MODEL_NAME=qwen3.8-27b-gist KEEP=1 bash driver/run_sessions_local.sh driver/tasks_coverage.txt covexam 4 > journeys/$J/results/driver_covexam.log 2>&1
kill $TAP $TUN 2>/dev/null
.venv/bin/python3 driver/eval_coverage.py driver/tasks_coverage.txt journeys/$J/results/requests_covexam.jsonl --json journeys/$J/results/student_coverage.json > journeys/$J/results/student_coverage.txt 2>&1; log "student coverage: $(grep SUMMARY journeys/$J/results/student_coverage.txt | cut -c1-140)"
destroy; echo "J8_DONE"
