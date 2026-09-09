#!/usr/bin/env python3
"""Merge a teacher cache for new examples (indices 0..n-1 in new.jsonl) into the base cache, with the
new examples appended after the base data. Usage: merge_cache.py base.jsonl base_cache.pt new.jsonl new_cache.pt out.jsonl out_cache.pt"""
import sys, torch, shutil
base, base_cache, new, new_cache, out, out_cache = sys.argv[1:7]
n_base = sum(1 for _ in open(base))
b = torch.load(base_cache, map_location="cpu"); nc = torch.load(new_cache, map_location="cpu")
merged = dict(b["cache"]); 
for i, c in nc["cache"].items(): merged[n_base + i] = c
with open(out, "w") as o:
    for f in (base, new):
        for line in open(f): o.write(line)
torch.save({"K": b["K"], "cache": merged}, out_cache)
print("merged: base %d examples (%d cached) + new %d cached -> %d cached of %d" % (n_base, len(b["cache"]), len(nc["cache"]), len(merged), n_base + sum(1 for _ in open(new))))
