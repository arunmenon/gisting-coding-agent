#!/usr/bin/env python3
"""Serving load generator for the gisting throughput benchmark (B0).

Replays pre-tokenized prompts (token-id lists) against vLLM's /v1/completions,
in closed-loop (fixed concurrency) or open-loop (Poisson arrivals) mode, and
records per-request timing plus engine-counter deltas from /metrics.

Metrics are measured correctly for the reviewer's caveat:
  - TTFT = time to the first streamed chunk that carries actual text (not the
    first SSE event), so keep-alive / empty chunks don't count.
  - TPOT = mean inter-token latency across text chunks.
  - completion tokens from the final usage block when present, else chunk count.
Output length is fixed (ignore_eos + max_tokens) so arms are compared on equal
generation work, as in the paper's replay.

Each line of --requests is JSON: {"prompt": [token ids], "session": ..., "turn": ...}.

Usage:
  loadgen.py --url http://127.0.0.1:8000 --model qwen3.8-27b-gist \
    --requests reqs_full.jsonl --arm full --mode closed --concurrency 8 \
    --repeat 1 --warmup 15 --duration 90 --out run.json
  ... --mode open --rps 6 ...
"""
import argparse, asyncio, json, os, random, time, sys, urllib.request
import aiohttp

METRIC_KEYS=("vllm:prompt_tokens_total","vllm:generation_tokens_total",
  "vllm:prefix_cache_hits_total","vllm:prefix_cache_queries_total",
  "vllm:request_prefill_time_seconds_sum","vllm:request_decode_time_seconds_sum",
  "vllm:e2e_request_latency_seconds_sum","vllm:request_queue_time_seconds_sum",
  "vllm:num_requests_running","vllm:num_requests_waiting",
  "vllm:gpu_cache_usage_perc","vllm:kv_cache_usage_perc","vllm:num_preemptions_total")

def metrics(base):
    try: txt=urllib.request.urlopen(base+"/metrics",timeout=30).read().decode()
    except Exception: return {}
    out={}
    for line in txt.splitlines():
        for k in METRIC_KEYS:
            if line.startswith(k+" ") or line.startswith(k+"{"):
                try: out[k]=float(line.rsplit(" ",1)[1])
                except ValueError: pass
    return out

def load_requests(path):
    reqs=[json.loads(l) for l in open(path) if l.strip()]
    if not reqs: sys.exit("no requests in "+path)
    return reqs

async def one_request(session, url, model, ids, max_tokens):
    payload={"model":model,"prompt":ids,"max_tokens":max_tokens,"stream":True,
             "temperature":0,"ignore_eos":True,"stream_options":{"include_usage":True}}
    rec={"ok":False,"ttft":None,"e2e":None,"tpot":None,"completion_tokens":0,"prompt_tokens":len(ids),"err":None}
    t0=time.perf_counter(); first=None; last=t0; n=0; usage=None
    try:
        async with session.post(url+"/v1/completions", json=payload, timeout=aiohttp.ClientTimeout(total=900)) as resp:
            if resp.status!=200: rec["err"]=f"http{resp.status}"; return rec
            async for raw in resp.content:
                line=raw.decode("utf-8","ignore").strip()
                if not line.startswith("data:"): continue
                data=line[5:].strip()
                if data=="[DONE]": break
                try: chunk=json.loads(data)
                except Exception: continue
                if chunk.get("usage"): usage=chunk["usage"]
                ch=chunk.get("choices") or []
                if ch and ch[0].get("text"):
                    now=time.perf_counter()
                    if first is None: first=now
                    n+=1; last=now
        t_end=time.perf_counter()
        if first is None: rec["err"]="no_text"; return rec
        ct=(usage or {}).get("completion_tokens") or n
        rec.update(ok=True, ttft=first-t0, e2e=t_end-t0, completion_tokens=ct,
                   prompt_tokens=(usage or {}).get("prompt_tokens") or len(ids),
                   tpot=((last-first)/max(1,ct-1)) if ct>1 else None)
        return rec
    except Exception as e:
        rec["err"]=type(e).__name__; return rec

async def sampler(base, every, stop_flag, samples):
    while not stop_flag["stop"]:
        m=metrics(base); m["t"]=time.time(); samples.append(m)
        await asyncio.sleep(every)

async def closed_loop(a, reqs):
    rnd=random.Random(a.seed); results=[]; start=time.perf_counter(); stop=start+a.warmup+a.duration
    idx={"i":0}
    async with aiohttp.ClientSession() as s:
        async def worker():
            while time.perf_counter()<stop:
                # turn-ordered round-robin so prefix caching sees realistic sharing
                r=reqs[idx["i"]%len(reqs)]; idx["i"]+=1
                sent=time.perf_counter(); rec=await one_request(s,a.url,a.model,r["prompt"],a.max_tokens)
                rec["sent_rel"]=sent-start; results.append(rec)
        await asyncio.gather(*[worker() for _ in range(a.concurrency)])
    return results

async def open_loop(a, reqs):
    rnd=random.Random(a.seed); results=[]; tasks=[]; start=time.perf_counter(); stop=start+a.warmup+a.duration
    idx={"i":0}
    async with aiohttp.ClientSession() as s:
        async def fire(r):
            sent=time.perf_counter(); rec=await one_request(s,a.url,a.model,r["prompt"],a.max_tokens)
            rec["sent_rel"]=sent-start; results.append(rec)
        while time.perf_counter()<stop:
            r=reqs[idx["i"]%len(reqs)]; idx["i"]+=1
            tasks.append(asyncio.create_task(fire(r)))
            await asyncio.sleep(rnd.expovariate(a.rps))
        if tasks: await asyncio.gather(*tasks)
    return results

def pct(vals,p):
    vals=sorted(v for v in vals if v is not None)
    if not vals: return None
    return vals[min(len(vals)-1,int(round(p/100*(len(vals)-1))))]

def summarize(results, a, m0, m1, samples):
    steady=[r for r in results if r.get("sent_rel",0)>=a.warmup]
    ok=[r for r in steady if r["ok"]]
    dur=a.duration
    d=lambda k: (m1.get(k,0)-m0.get(k,0)) if (k in m0 and k in m1) else None
    eng={"prompt_tokens":d("vllm:prompt_tokens_total"),"gen_tokens":d("vllm:generation_tokens_total"),
         "prefix_hits":d("vllm:prefix_cache_hits_total"),"prefix_queries":d("vllm:prefix_cache_queries_total"),
         "prefill_s":d("vllm:request_prefill_time_seconds_sum"),"decode_s":d("vllm:request_decode_time_seconds_sum"),
         "queue_s":d("vllm:request_queue_time_seconds_sum"),"preemptions":d("vllm:num_preemptions_total")}
    if eng["prefix_queries"]: eng["prefix_hit_rate"]=round(eng["prefix_hits"]/eng["prefix_queries"],3)
    if samples:
        run=[s.get("vllm:num_requests_running") for s in samples if "vllm:num_requests_running" in s]
        kv=[s.get("vllm:kv_cache_usage_perc", s.get("vllm:gpu_cache_usage_perc")) for s in samples]
        kv=[x for x in kv if x is not None]
        eng["max_running_seqs"]=max(run) if run else None
        eng["kv_usage_max"]=max(kv) if kv else None; eng["kv_usage_mean"]=round(sum(kv)/len(kv),3) if kv else None
    return {"arm":a.arm,"tag":a.tag,"repeat":a.repeat,"mode":a.mode,
        "concurrency":a.concurrency if a.mode=="closed" else None,"rps":a.rps if a.mode=="open" else None,
        "max_tokens":a.max_tokens,"warmup_s":a.warmup,"duration_s":dur,"requests_file":os.path.basename(a.requests),"ts":time.time(),
        "requests_total":len(steady),"requests_ok":len(ok),"errors":len(steady)-len(ok),
        "err_kinds":{k:sum(1 for r in steady if r["err"]==k) for k in set(r["err"] for r in steady if r["err"])},
        "throughput_rpm":round(len(ok)/dur*60,2),"out_tokens_per_s":round(sum(r["completion_tokens"] for r in ok)/dur,1),
        "e2e_p50":pct([r["e2e"] for r in ok],50),"e2e_p95":pct([r["e2e"] for r in ok],95),
        "ttft_p50":pct([r["ttft"] for r in ok],50),"ttft_p95":pct([r["ttft"] for r in ok],95),
        "tpot_p50":pct([r["tpot"] for r in ok],50),"prompt_tokens_med":pct([r["prompt_tokens"] for r in ok],50),
        "engine":eng}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",required=True); ap.add_argument("--model",default="qwen3.8-27b-gist")
    ap.add_argument("--requests",required=True); ap.add_argument("--arm",required=True); ap.add_argument("--tag",default="")
    ap.add_argument("--mode",choices=["closed","open"],default="closed")
    ap.add_argument("--concurrency",type=int,default=8); ap.add_argument("--rps",type=float,default=4.0)
    ap.add_argument("--repeat",type=int,default=1)
    ap.add_argument("--warmup",type=float,default=15); ap.add_argument("--duration",type=float,default=90)
    ap.add_argument("--max-tokens",type=int,default=200); ap.add_argument("--seed",type=int,default=0)
    ap.add_argument("--sample-every",type=float,default=5.0); ap.add_argument("--out",required=True)
    a=ap.parse_args()
    reqs=load_requests(a.requests)
    m0=metrics(a.url); samples=[]; flag={"stop":False}
    async def run():
        st=asyncio.create_task(sampler(a.url,a.sample_every,flag,samples))
        res=await (closed_loop(a,reqs) if a.mode=="closed" else open_loop(a,reqs))
        flag["stop"]=True; await asyncio.sleep(0)
        st.cancel()
        return res
    results=asyncio.run(run())
    m1=metrics(a.url)
    summ=summarize(results,a,m0,m1,samples)
    json.dump({"summary":summ,"raw":results,"metric_samples":samples},open(a.out,"w"))
    print(json.dumps({k:v for k,v in summ.items() if k!="engine"}), flush=True)
    print("engine:",json.dumps(summ["engine"]), flush=True)

if __name__=="__main__":
    main()
