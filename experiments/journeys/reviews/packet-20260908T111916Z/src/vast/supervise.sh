#!/bin/bash
# Detached supervisor for vllm serve: independent of tmux and ssh. Restarts on death up to 3 times.
# Usage: nohup setsid bash /root/supervise.sh > /root/supervise.log 2>&1 < /dev/null &
export HF_HUB_OFFLINE=1
for attempt in 1 2 3; do
  echo "$(date -u +%FT%TZ) supervisor: launching vllm attempt $attempt"
  bash /root/serve.sh < /dev/null
  echo "$(date -u +%FT%TZ) supervisor: vllm exited with $?"
  [ -f /root/STOP ] && { echo "STOP marker present, not restarting"; exit 0; }
  sleep 10
done
