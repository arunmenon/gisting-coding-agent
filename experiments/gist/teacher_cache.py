#!/usr/bin/env python3
"""E3: precompute teacher top-k log-probs at response positions using vLLM's prompt_logprobs.

For each example, send teacher_ids + response_ids as a prompt with max_tokens=1 and
prompt_logprobs=K. vLLM returns, for every prompt position, the top-K (token -> logprob) plus the
actual token's logprob. We keep the last len(response_ids) positions. Prefix caching makes turns
of the same session cheap. Output: one torch file with per-example tensors:
  topk_ids [R, K] int32, topk_logp [R, K] float16, actual_logp [R] float16
Usage: teacher_cache.py train.jsonl teacher_cache.pt [K] [max_total_len] [concurrency]
"""
import json, sys, time, concurrent.futures as cf, urllib.request
import torch
BASE = "http://127.0.0.1:8000"
path, out_path = sys.argv[1], sys.argv[2]
K = int(sys.argv[3]) if len(sys.argv) > 3 else 32
MAX_LEN = int(sys.argv[4]) if len(sys.argv) > 4 else 60000
CONC = int(sys.argv[5]) if len(sys.argv) > 5 else 4

def query(example):
    ids = example["teacher_ids"] + example["response_ids"]
    body = {"model": "qwen3.8-27b-gist", "prompt": ids, "max_tokens": 1, "temperature": 0, "prompt_logprobs": K}
    req = urllib.request.Request(BASE + "/v1/completions", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    plp = r["choices"][0]["prompt_logprobs"]  # list aligned with prompt positions; entry i = dist predicting token i
    R = len(example["response_ids"])
    tail = plp[-R:]
    topk_ids = torch.zeros(R, K, dtype=torch.int32); topk_logp = torch.full((R, K), -1e4, dtype=torch.float16); actual = torch.zeros(R, dtype=torch.float16)
    for i, entry in enumerate(tail):
        items = sorted(((int(t), v["logprob"]) for t, v in entry.items()), key=lambda x: -x[1])[:K]
        for j, (t, lp) in enumerate(items):
            topk_ids[i, j] = t; topk_logp[i, j] = lp
        actual[i] = entry[str(example["response_ids"][i])]["logprob"] if str(example["response_ids"][i]) in entry else float("nan")
    return {"topk_ids": topk_ids, "topk_logp": topk_logp, "actual_logp": actual}

examples = [json.loads(l) for l in open(path)]
keep = [i for i, e in enumerate(examples) if len(e["teacher_ids"]) + len(e["response_ids"]) <= MAX_LEN]
# sort by teacher prefix so same-session turns hit the prefix cache back to back
keep.sort(key=lambda i: (examples[i].get("session", ""), examples[i].get("turn_index", 0)))
print("examples", len(examples), "| within max_len", len(keep), "| K", K, "| concurrency", CONC, flush=True)
cache = {}
started = time.time()
with cf.ThreadPoolExecutor(CONC) as pool:
    futures = {pool.submit(query, examples[i]): i for i in keep}
    for n, fut in enumerate(cf.as_completed(futures), 1):
        i = futures[fut]
        try:
            cache[i] = fut.result()
        except Exception as error:
            print("example %d failed: %s" % (i, str(error)[:200]), flush=True)
        if n % 50 == 0 or n == len(keep):
            print("%d/%d done, %.0fs elapsed" % (n, len(keep), time.time() - started), flush=True)
torch.save({"K": K, "cache": cache}, out_path)
covered = sum(1 for c in cache.values() if not torch.isnan(c["actual_logp"]).any())
mass = torch.cat([c["topk_logp"].float().exp().sum(1) for c in cache.values()])
print("saved %d examples to %s | actual token inside top-%d for %d examples | top-%d mass: mean %.3f p10 %.3f" % (len(cache), out_path, K, covered, K, mass.mean(), mass.quantile(0.1)))
