#!/bin/bash
# provision.sh <run> <ratio> <host> <port> <instance>: copy everything a worker needs, launch chain + watchdog, verify.
set -u
RUN=$1; R=$2; H=$3; P=$4; IID=$5; cd "$(dirname "$0")/.."
S="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
try() { for i in $(seq 1 30); do "$@" 2>/dev/null && return 0; sleep 40; done; return 1; }
try ssh $S -p $P root@$H 'mkdir -p /root/gist/out /root/data && echo ready' | grep -q ready || { echo "$RUN: ssh failed"; exit 1; }
try scp $S -P $P vast/chain_sweep.sh vast/serve_gist.sh vast/supervise_gist.sh vast/idle_watchdog.sh vast/apply_gist_delta.sh vast/gen_test.py gist/mask_gist_logits.py gist/out/chat_template_gist.jinja vast/.instance_key_$IID root@$H:/root/ || { echo "$RUN: scp scripts failed"; exit 1; }
try scp $S -P $P gist/span.py gist/segments.py gist/prepare_checkpoint.py gist/dataset.py gist/train.py gist/export_rows.py root@$H:/root/gist/ || { echo "$RUN: scp gist failed"; exit 1; }
try scp $S -P $P -r ${MAP:-gist/out_r$R}/segments.json ${MAP:-gist/out_r$R}/tokenizer root@$H:/root/gist/out/ || { echo "$RUN: scp map failed"; exit 1; }
try scp $S -P $P ${DATA:-journeys/j4-ratio-sweep/results/train_r$R.jsonl.gz} root@$H:/root/data/train_r$R.jsonl.gz || { echo "$RUN: scp data failed"; exit 1; }
try scp $S -P $P ${CACHE:-journeys/j3-e3-e2/results/teacher_cache.pt} root@$H:/root/teacher_cache.pt || { echo "$RUN: scp cache failed"; exit 1; }
OUT=$(try ssh $S -p $P root@$H "mv /root/.instance_key_$IID /root/.vast_key; chmod 600 /root/.vast_key; chmod +x /root/*.sh; gunzip -c /root/data/train_r$R.jsonl.gz > /root/data/train.jsonl; wc -l < /root/data/train.jsonl; python3 -c \"import json; print('gist_count', json.load(open('/root/gist/out/segments.json'))['gist_count'])\"; df -BG / | awk 'NR==2{print \$4}'; nvidia-smi --query-gpu=name --format=csv,noheader; SMAX=${SMAX:-30000} REDUCE=${REDUCE:-batch} nohup setsid bash /root/chain_sweep.sh > /root/chain.log 2>&1 < /dev/null & IDLE_MIN=150 nohup setsid bash /root/idle_watchdog.sh $IID > /root/watchdog.log 2>&1 < /dev/null & sleep 4; tail -1 /root/STATE; pgrep -f 'idle_[w]atchdog' | head -1 | xargs echo watchdog")
echo "$RUN: $(echo "$OUT" | tr '\n' ' | ')"
