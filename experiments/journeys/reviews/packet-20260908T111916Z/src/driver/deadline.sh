#!/bin/bash
# Stop session collection at a UTC deadline (HHMM) or when both batches finish; writes logs/COLLECTION_DONE.
DEADLINE="$1"; cd "$(dirname "$0")/.."
until { grep -q ALL_SESSIONS_DONE logs/driver_long.log && grep -q ALL_SESSIONS_DONE logs/driver_e2.log; } || [ "$(date -u +%H%M)" -ge "$DEADLINE" ]; do sleep 60; done
pkill -f "run_sessions_[l]ocal"; pkill -f "[c]laude -p"; sleep 3
echo "$(date -u +%FT%TZ) long $(grep -c '^s' logs/driver_long.log) e2 $(grep -c '^s' logs/driver_e2.log) procs_left $(ps aux | grep -c '[c]laude -p')" > logs/COLLECTION_DONE
