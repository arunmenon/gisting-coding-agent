#!/bin/bash
# Detached on the box: wait for the teacher cache file, then run chain_j3b with the J3 training params.
until [ -f /root/teacher_cache.pt ] && ! pgrep -f "teacher_[c]ache.py" > /dev/null; do sleep 60; done
echo "$(date -u +%FT%TZ) cache present, launching chain_j3b" | tee -a /root/STATE
EPOCHS=1 ACCUM=8 LR=1e-3 SMAX=30000 EVAL_N=24 EVAL_EVERY=40 bash /root/chain_j3b.sh > /root/chain_j3b.log 2>&1
