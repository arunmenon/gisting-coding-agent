#!/bin/bash
# Detached chain: restart gisted vLLM WITH the logits mask, run gen test, then switch to the base
# (teacher) model for session collection. Markers in /root/STATE.
set -uo pipefail
mark() { echo "$(date -u +%FT%TZ) $1" | tee -a /root/STATE; }
wait_health() { for i in $(seq 1 60); do curl -s -m 5 localhost:8000/health -o /dev/null -w "%{http_code}" | grep -q 200 && return 0; sleep 10; done; return 1; }
touch /root/STOP; pkill -f "vllm [s]erve"; sleep 8; rm -f /root/STOP
mv /root/vllm_gist.log /root/vllm_gist_unmasked.log
nohup setsid bash /root/supervise_gist.sh > /root/supervise_gist.log 2>&1 < /dev/null &
mark "gist_masked_launched"
if wait_health; then
  mark "gist_masked_healthy"
  cd /root && python3 gen_test.py > /root/gen_test_masked.log 2>&1; mark "gen_test_masked: $(grep TOTAL /root/gen_test_masked.log)"
else
  mark "gist_masked_FAILED_TO_START"; tr "\r" "\n" < /root/vllm_gist.log | grep -aE "Error|Traceback" | tail -3
fi
touch /root/STOP; pkill -f "vllm [s]erve"; sleep 8; rm -f /root/STOP
nohup setsid bash /root/supervise.sh > /root/supervise.log 2>&1 < /dev/null &
mark "base_launched"
if wait_health; then mark "base_healthy"; else mark "base_FAILED_TO_START"; fi
