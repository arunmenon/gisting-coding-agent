#!/usr/bin/env python3
"""Write trained gist rows (gist_rows.pt, [gist_count, hidden] fp32) into the gisted checkpoint's
embedding shard in place. Usage: export_rows.py <ckpt_dir> <gist_rows.pt>"""
import json, os, sys, torch
from safetensors import safe_open
from safetensors.torch import save_file
ckpt, rows_path = sys.argv[1], sys.argv[2]
meta = json.load(open(os.path.join(ckpt, "gist_meta.json")))
shard = os.path.join(ckpt, "model-00003-of-00018.safetensors")
key = "model.language_model.embed_tokens.weight"
tensors, metadata = {}, None
with safe_open(shard, framework="pt") as h:
    metadata = h.metadata()
    for k in h.keys(): tensors[k] = h.get_tensor(k)
rows = torch.load(rows_path, map_location="cpu").float()
first, count = meta["first_gist_id"], meta["gist_count"]
assert rows.shape == (count, tensors[key].shape[1]), (rows.shape, tensors[key].shape)
before = tensors[key][first:first + count].float()
delta = (rows - before).norm(dim=1)
tensors[key][first:first + count] = rows.to(tensors[key].dtype)
if os.path.islink(shard): os.unlink(shard)
save_file(tensors, shard, metadata=metadata)
print("wrote %d gist rows into %s | mean row change %.4f (max %.4f) | row norm before %.3f after %.3f" % (count, shard, delta.mean(), delta.max(), before.norm(dim=1).mean(), rows.norm(dim=1).mean()))
