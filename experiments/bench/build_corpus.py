#!/usr/bin/env python3
"""Build replay corpora for the serving benchmark from the distillation datasets.

Each dataset record has teacher_ids (full prompt), student_ids (gist prompt),
session and turn_index. We pick K sessions (seeded), keep turns in order so
prefix caching sees realistic sharing, and emit one request file per arm:
  reqs_full.jsonl    prompt = teacher_ids   (from the r8v2 corpus)
  reqs_gist8.jsonl   prompt = student_ids   (r8v2, 8:1 with verbatim rule)
  reqs_gist16.jsonl  prompt = student_ids   (r16 corpus, 16:1)
  reqs_full16.jsonl  prompt = teacher_ids   (r16 corpus; control for the 16:1 server)
plus *_smoke.jsonl (first 8 requests) for the harness smoke test.
"""
import gzip, json, random, sys, os
from collections import defaultdict

def load(path):
    op=gzip.open if path.endswith(".gz") else open
    with op(path,"rt") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def pick_sessions(records, k, seed, min_turns=3, max_prompt=36000):
    by=defaultdict(list)
    for r in records:
        if len(r["teacher_ids"])<=max_prompt: by[r["session"]].append(r)
    eligible=[s for s,ts in by.items() if len(ts)>=min_turns]
    rnd=random.Random(seed); rnd.shuffle(eligible)
    chosen=eligible[:k]
    out=[]
    for s in chosen:
        for r in sorted(by[s], key=lambda x: x["turn_index"]): out.append(r)
    return out, len(eligible)

def write(path, recs, key):
    with open(path,"w") as f:
        for r in recs:
            f.write(json.dumps({"prompt":r[key],"session":r["session"],"turn":r["turn_index"]})+"\n")
    return len(recs)

def main():
    r8=sys.argv[1]; r16=sys.argv[2]; out=sys.argv[3]; k=int(sys.argv[4]) if len(sys.argv)>4 else 24; seed=int(sys.argv[5]) if len(sys.argv)>5 else 7
    os.makedirs(out,exist_ok=True)
    recs8,n8=pick_sessions(list(load(r8)),k,seed)
    recs16,n16=pick_sessions(list(load(r16)),k,seed)
    stats={}
    stats["full"]=write(f"{out}/reqs_full.jsonl",recs8,"teacher_ids")
    stats["gist8"]=write(f"{out}/reqs_gist8.jsonl",recs8,"student_ids")
    stats["gist16"]=write(f"{out}/reqs_gist16.jsonl",recs16,"student_ids")
    stats["full16"]=write(f"{out}/reqs_full16.jsonl",recs16,"teacher_ids")
    write(f"{out}/reqs_full_smoke.jsonl",recs8[:8],"teacher_ids"); write(f"{out}/reqs_gist8_smoke.jsonl",recs8[:8],"student_ids")
    def med(xs): xs=sorted(xs); return xs[len(xs)//2]
    meta={"k_sessions":k,"seed":seed,"max_prompt_tokens":36000,"eligible_sessions":{"r8v2":n8,"r16":n16},"requests":stats,
          "prompt_tokens_median":{"full":med([len(r["teacher_ids"]) for r in recs8]),"gist8":med([len(r["student_ids"]) for r in recs8]),
                                  "gist16":med([len(r["student_ids"]) for r in recs16])},
          "prompt_tokens_max":{"full":max(len(r["teacher_ids"]) for r in recs8)}}
    json.dump(meta,open(f"{out}/corpus_meta.json","w"),indent=1)
    print(json.dumps(meta,indent=1))

if __name__=="__main__": main()
