#!/usr/bin/env python3
"""E8 latency benchmark, run ON the box against localhost:8000 (no tunnel in the numbers).
Replays logged sessions turn by turn (so prefix caching sees realistic sharing) in two arms:
  teacher: teacher_ids (full prompt)      student: student_ids (gist prefix, same conversation)
Each request generates exactly MAX_TOKENS at temperature 0. Reports per arm and concurrency:
client TTFT and latency percentiles, throughput, and engine counter deltas (prefill s, decode s,
prompt tokens, generation tokens, prefix-cache hits). Usage: bench_latency.py data.jsonl out.json
"""
import json, sys, time, threading, urllib.request, statistics, collections
BASE="http://127.0.0.1:8000"; MODEL="qwen3.8-27b-gist"; MAX_TOKENS=200; N_SESSIONS=12; TURNS_PER=6
data=[json.loads(l) for l in open(sys.argv[1])]
# group by session, keep sessions with >= TURNS_PER turns, take the first N_SESSIONS
by=collections.defaultdict(list)
for e in data: by[e.get("session","?")].append(e)
sessions=[sorted(v, key=lambda e: e.get("turn_index",0))[:TURNS_PER] for v in by.values() if len(v)>=TURNS_PER][:N_SESSIONS]
print("sessions", len(sessions), "turns each", TURNS_PER, flush=True)

def metrics():
    txt=urllib.request.urlopen(BASE+"/metrics", timeout=60).read().decode()
    out={}
    for line in txt.splitlines():
        for key in ("vllm:request_prefill_time_seconds_sum","vllm:request_decode_time_seconds_sum","vllm:prompt_tokens_total","vllm:generation_tokens_total","vllm:prefix_cache_hits_total","vllm:prefix_cache_queries_total","vllm:e2e_request_latency_seconds_sum","vllm:request_queue_time_seconds_sum"):
            if line.startswith(key+" ") or line.startswith(key+"{"): out[key]=float(line.rsplit(" ",1)[1])
    return out

def one(ids):
    body={"model":MODEL,"prompt":ids,"max_tokens":MAX_TOKENS,"temperature":0,"stream":True,"ignore_eos":True}
    req=urllib.request.Request(BASE+"/v1/completions", data=json.dumps(body).encode(), headers={"content-type":"application/json"})
    t0=time.time(); first=None; n=0
    with urllib.request.urlopen(req, timeout=900) as r:
        for line in r:
            if line.startswith(b"data:") and b"[DONE]" not in line:
                if first is None: first=time.time()
                n+=1
    return (first-t0) if first else None, time.time()-t0, n

def run_arm(arm, conc):
    key="teacher_ids" if arm=="teacher" else "student_ids"
    # each worker replays whole sessions in turn order; sessions are distributed across workers
    lanes=[sessions[i::conc] for i in range(conc)]
    results=[]; lock=threading.Lock()
    def worker(lane):
        for sess in lane:
            for e in sess:
                ttft, lat, n = one(e[key])
                with lock: results.append({"ttft":ttft,"lat":lat,"prompt_len":len(e[key]),"gen":n})
    m0=metrics(); t0=time.time()
    ths=[threading.Thread(target=worker,args=(l,)) for l in lanes]; [t.start() for t in ths]; [t.join() for t in ths]
    wall=time.time()-t0; m1=metrics()
    d={k: m1.get(k,0)-m0.get(k,0) for k in m0}
    tt=[r["ttft"] for r in results if r["ttft"]]; la=[r["lat"] for r in results]
    q=lambda xs,p: sorted(xs)[min(len(xs)-1,int(p*len(xs)))]
    summary={"arm":arm,"concurrency":conc,"requests":len(results),"wall_s":round(wall,1),
             "prompt_tokens_median":statistics.median(r["prompt_len"] for r in results),
             "ttft_median_s":round(statistics.median(tt),3),"ttft_p90_s":round(q(tt,.9),3),
             "latency_median_s":round(statistics.median(la),2),"latency_p90_s":round(q(la,.9),2),
             "requests_per_min":round(len(results)/wall*60,2),"gen_tokens_per_s":round(sum(r["gen"] for r in results)/wall,1),
             "engine_prefill_s_per_req":round(d.get("vllm:request_prefill_time_seconds_sum",0)/max(len(results),1),3),
             "engine_decode_s_per_req":round(d.get("vllm:request_decode_time_seconds_sum",0)/max(len(results),1),3),
             "engine_prefix_hit_rate":round(d.get("vllm:prefix_cache_hits_total",0)/max(d.get("vllm:prefix_cache_queries_total",1),1),3),
             "engine_prompt_tokens":d.get("vllm:prompt_tokens_total",0)}
    print(json.dumps(summary), flush=True); return summary

out=[]
# warm-up: touch both arms once so compile caches and the first-call cost are excluded
for arm in ("teacher","student"): one(sessions[0][0]["teacher_ids" if arm=="teacher" else "student_ids"])
for conc in (1,4,8):
    for arm in ("teacher","student"):
        out.append(run_arm(arm, conc))
json.dump(out, open(sys.argv[2],"w"), indent=1); print("BENCH_DONE", flush=True)
