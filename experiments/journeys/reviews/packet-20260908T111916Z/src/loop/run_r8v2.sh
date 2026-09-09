#!/bin/bash
set -u; cd "$(dirname "$0")/.."
IID=$(cat /tmp/r8v2_iid.txt)
until .venv/bin/vastai show instance $IID --raw 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('actual_status'), d.get('ssh_host'), d.get('ssh_port')); raise SystemExit(0 if d.get('actual_status')=='running' else 1)" > /tmp/r8v2box.txt; do sleep 20; done
H=$(awk '{print $2}' /tmp/r8v2box.txt); P=$(awk '{print $3}' /tmp/r8v2box.txt); echo "box running at $H:$P"
sleep 60
R=$(MAP=gist/out_r8v2 DATA=journeys/j5-hard-eval/results/train_r8v2.jsonl.gz bash loop/provision.sh r8v2 8v2 $H $P $IID 2>&1 | tail -1); echo "$R"
echo "$R" | grep -q gist_count || { echo "PROVISION_FAILED"; exit 1; }
bash loop/train_then_hard_eval.sh r8v2 out_r8v2 $H $P $IID j5-hard-eval
