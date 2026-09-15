#!/bin/bash
# Wait for provisioning to finish, then poll the box until a terminal marker,
# syncing results as they land. Emits only new STATE lines.
cd "$(dirname "$0")/../.."
J=journeys/j11-conn
while pgrep -f "bench_[p]rovision" > /dev/null; do sleep 20; done
read H P < $J/ssh
: > $J/seen
for i in $(seq 1 200); do
  S=$(bash vast/rsh.sh run $H $P 'cat /root/STATE 2>/dev/null' 2>/dev/null)
  [ -n "$S" ] && { echo "$S" | comm -13 $J/seen - 2>/dev/null; echo "$S" > $J/seen; }
  echo "$S" | grep -qE "BENCH_DONE|_FAILED|DEADLINE" && { echo "=== TERMINAL MARKER ==="; break; }
  sleep 60
done
bash vast/rsh.sh get $H $P '/root/bench_results/*' $J/results/ 2>/dev/null
bash vast/rsh.sh get $H $P '/root/STATE' $J/results/ 2>/dev/null
echo "=== synced $(ls $J/results | wc -l) files ==="
tail -20 $J/results/STATE 2>/dev/null
