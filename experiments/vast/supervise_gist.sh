#!/bin/bash
export HF_HUB_OFFLINE=1
for attempt in 1 2; do
  echo "$(date -u +%FT%TZ) supervisor: launching gist vllm attempt $attempt"
  bash /root/serve_gist.sh < /dev/null
  echo "$(date -u +%FT%TZ) supervisor: vllm exited with $?"
  [ -f /root/STOP ] && exit 0
  sleep 10
done
