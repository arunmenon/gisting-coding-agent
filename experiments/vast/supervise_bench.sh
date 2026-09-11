#!/bin/bash
# Restart-on-death supervisor for serve_bench.sh. Stops cleanly when /root/STOP exists.
# Env knobs are inherited by serve_bench.sh (CKPT, MAX_MODEL_LEN, MAX_NUM_SEQS, GPU_UTIL, MAX_BATCHED, PREFIX_CACHE, KV_DTYPE).
export HF_HUB_OFFLINE=1
for attempt in 1 2 3; do
  echo "$(date -u +%FT%TZ) supervise_bench: launching vllm attempt $attempt" | tee -a /root/supervise_bench.log
  bash /root/serve_bench.sh < /dev/null
  echo "$(date -u +%FT%TZ) supervise_bench: vllm exited with $?" | tee -a /root/supervise_bench.log
  [ -f /root/STOP ] && exit 0
  sleep 10
done
echo "$(date -u +%FT%TZ) supervise_bench: giving up after 3 attempts" | tee -a /root/supervise_bench.log
touch /root/SERVE_FAILED
