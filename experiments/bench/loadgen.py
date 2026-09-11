#!/usr/bin/env python3
"""Serving load generator for the gisting throughput benchmark (B0).

Replays pre-rendered chat-completion request payloads against a vLLM
OpenAI-compatible endpoint, in closed-loop (fixed concurrency) or open-loop
(Poisson arrivals) mode, and records per-request timing.

Metrics are measured correctly for the reviewer's caveat:
  - TTFT is the time to the first streamed chunk that carries actual content
    (not the first SSE event), so keep-alive/role-only chunks don't count.
  - TPOT is mean inter-token latency across content chunks.
  - completion tokens come from the final usage block when present, else a
    content-chunk count fallback.

Usage:
  loadgen.py --url http://127.0.0.1:8000/v1/chat/completions \
    --requests reqs_full.jsonl --mode closed --concurrency 8 \
    --warmup 20 --duration 120 --out run.json
  loadgen.py ... --mode open --rps 6 --duration 120 --out run.json

Each line of --requests is a JSON chat-completions body (messages, model, etc.);
max_tokens/stream are forced by this script so output length is controlled.
"""
import argparse, asyncio, json, os, random, time, sys
import aiohttp

def load_requests(path):
    reqs=[]
    with open(path) as f:
        for line in f:
            line=line.strip()
            if line: reqs.append(json.loads(line))
    if not reqs: sys.exit("no requests in "+path)
    return reqs

async def one_request(session, url, body, max_tokens, sem=None):
    """Send one streaming request; return timing dict."""
    payload=dict(body); payload["stream"]=True; payload["max_tokens"]=max_tokens
    payload["stream_options"]={"include_usage": True}
    rec={"ok":False,"ttft":None,"e2e":None,"tpot":None,"completion_tokens":0,"prompt_tokens":None,"err":None}
    t0=time.perf_counter(); first_content=None; last=t0; n_content=0; usage=None
    try:
        if sem: await sem.acquire()
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            if resp.status!=200:
                rec["err"]=f"http{resp.status}"; return rec
            async for raw in resp.content:
                if not raw: continue
                line=raw.decode("utf-8","ignore").strip()
                if not line.startswith("data:"): continue
                data=line[5:].strip()
                if data=="[DONE]": break
                try: chunk=json.loads(data)
                except Exception: continue
                if chunk.get("usage"): usage=chunk["usage"]
                choices=chunk.get("choices") or []
                if not choices: continue
                delta=choices[0].get("delta") or {}
                content=delta.get("content")
                if content:  # first chunk carrying actual text
                    now=time.perf_counter()
                    if first_content is None: first_content=now
                    n_content+=1; last=now
        t_end=time.perf_counter()
        if first_content is None:
            rec["err"]="no_content"; return rec
        rec["ok"]=True; rec["ttft"]=first_content-t0; rec["e2e"]=t_end-t0
        ct=(usage or {}).get("completion_tokens") or n_content
        rec["prompt_tokens"]=(usage or {}).get("prompt_tokens")
        rec["completion_tokens"]=ct
        rec["tpot"]=((last-first_content)/max(1,ct-1)) if ct>1 else None
        return rec
    except Exception as e:
        rec["err"]=type(e).__name__; return rec
    finally:
        if sem: sem.release()

async def closed_loop(url, reqs, conc, warmup_s, dur_s, max_tokens, seed):
    rnd=random.Random(seed); results=[]; start=time.perf_counter(); stop=start+warmup_s+dur_s
    async with aiohttp.ClientSession() as session:
        async def worker():
            while time.perf_counter()<stop:
                body=rnd.choice(reqs); sent=time.perf_counter()
                r=await one_request(session,url,body,max_tokens)
                r["sent_rel"]=sent-start; results.append(r)
        await asyncio.gather(*[worker() for _ in range(conc)])
    return results, warmup_s

async def open_loop(url, reqs, rps, warmup_s, dur_s, max_tokens, seed):
    rnd=random.Random(seed); results=[]; tasks=[]; start=time.perf_counter(); stop=start+warmup_s+dur_s
    async with aiohttp.ClientSession() as session:
        async def fire(body):
            sent=time.perf_counter(); r=await one_request(session,url,body,max_tokens)
            r["sent_rel"]=sent-start; results.append(r)
        while time.perf_counter()<stop:
            body=rnd.choice(reqs); tasks.append(asyncio.create_task(fire(body)))
            await asyncio.sleep(rnd.expovariate(rps))  # Poisson inter-arrival
        if tasks: await asyncio.gather(*tasks)
    return results, warmup_s

def summarize(results, warmup_s, dur_s, meta):
    steady=[r for r in results if r.get("sent_rel",0)>=warmup_s]
    ok=[r for r in steady if r["ok"]]
    def pct(vals,p):
        vals=sorted(v for v in vals if v is not None)
        if not vals: return None
        k=min(len(vals)-1,int(round((p/100)*(len(vals)-1)))); return vals[k]
    e2e=[r["e2e"] for r in ok]; ttft=[r["ttft"] for r in ok]; tpot=[r["tpot"] for r in ok]
    out_tok=sum(r["completion_tokens"] for r in ok)
    span=dur_s
    return {**meta,
        "requests_total":len(steady),"requests_ok":len(ok),"errors":len(steady)-len(ok),
        "err_kinds":{k:sum(1 for r in steady if r["err"]==k) for k in set(r["err"] for r in steady if r["err"])},
        "throughput_rpm": round(len(ok)/span*60,2) if span else None,
        "out_tokens_per_s": round(out_tok/span,1) if span else None,
        "e2e_p50":pct(e2e,50),"e2e_p95":pct(e2e,95),
        "ttft_p50":pct(ttft,50),"ttft_p95":pct(ttft,95),
        "tpot_p50":pct(tpot,50),
        "prompt_tokens_med":pct([r["prompt_tokens"] for r in ok if r["prompt_tokens"]],50),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",required=True); ap.add_argument("--requests",required=True)
    ap.add_argument("--mode",choices=["closed","open"],default="closed")
    ap.add_argument("--concurrency",type=int,default=8); ap.add_argument("--rps",type=float,default=4.0)
    ap.add_argument("--warmup",type=float,default=15); ap.add_argument("--duration",type=float,default=120)
    ap.add_argument("--max-tokens",type=int,default=200); ap.add_argument("--seed",type=int,default=0)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    reqs=load_requests(a.requests)
    meta={"mode":a.mode,"concurrency":a.concurrency if a.mode=="closed" else None,
          "rps":a.rps if a.mode=="open" else None,"max_tokens":a.max_tokens,
          "warmup_s":a.warmup,"duration_s":a.duration,"seed":a.seed,
          "requests_file":os.path.basename(a.requests),"url":a.url,"ts":time.time()}
    if a.mode=="closed":
        results,w=asyncio.run(closed_loop(a.url,reqs,a.concurrency,a.warmup,a.duration,a.max_tokens,a.seed))
    else:
        results,w=asyncio.run(open_loop(a.url,reqs,a.rps,a.warmup,a.duration,a.max_tokens,a.seed))
    summ=summarize(results,w,a.duration,meta)
    json.dump({"summary":summ,"raw":results},open(a.out,"w"))
    print(json.dumps(summ,indent=1))

if __name__=="__main__":
    main()
