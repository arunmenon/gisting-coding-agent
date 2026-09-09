#!/bin/bash
# Runs INSIDE the vast container. Destroys the instance after IDLE_MIN minutes with no GPU activity.
# Usage: nohup setsid bash idle_watchdog.sh <instance_id> > /root/watchdog.log 2>&1 &
INSTANCE_ID="$1"; IDLE_MIN="${IDLE_MIN:-60}"
KEY=$(cat /root/.vast_key)
idle=0
while true; do
  util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if [ "${util:-0}" -gt 3 ]; then idle=0; else idle=$((idle+1)); fi
  echo "$(date -u +%FT%TZ) util=${util} idle_min=${idle}"
  if [ "$idle" -ge "$IDLE_MIN" ]; then
    echo "$(date -u +%FT%TZ) IDLE LIMIT REACHED, destroying instance $INSTANCE_ID"
    curl -s -X DELETE -H "Authorization: Bearer $KEY" "https://console.vast.ai/api/v0/instances/$INSTANCE_ID/"
    exit 0
  fi
  sleep 60
done
