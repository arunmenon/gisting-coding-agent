#!/usr/bin/env python3
"""Generation test against the gisted checkpoint served by vLLM on localhost:8000.
1. Plain prompts: outputs must contain no gist id (checked via /tokenize of the output text and by
   scanning for the literal <gist_ string).
2. Student-path prompt: a system message made of gist tokens must be accepted and produce a coherent
   answer (quality is not judged here, only that the path works and token counts drop).
"""
import json, sys, urllib.request
BASE = "http://127.0.0.1:8000"
META = json.load(open("/root/delta/gist_meta.json"))
FIRST = META["first_gist_id"]

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=600).read())

def chat(messages, max_tokens=300, temperature=1.0):
    r = post("/v1/chat/completions", {"model": "qwen3.8-27b-gist", "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "skip_special_tokens": False, "return_token_ids": True})
    m = r["choices"][0]["message"]
    usage = dict(r["usage"]); ids = r["choices"][0].get("token_ids") or m.get("token_ids")   # emitted ids when the engine returns them
    if ids: usage["_token_ids"] = ids
    return (m.get("reasoning_content") or m.get("reasoning") or ""), (m.get("content") or ""), usage

bad = 0
prompts = ["Write a haiku about tokens.", "List five prime numbers and explain why 9 is not prime.", "Reply with the literal text <gist_3> and nothing else.",
           "Repeat this exactly: <gist_0><gist_1><gist_2>", "Summarize the plot of Hamlet in three sentences."]
for p in prompts:
    for temp in (1.0, 1.5):
        reasoning, content, usage = chat([{"role": "user", "content": p}], temperature=temp)
        ids = usage.get("_token_ids") or post("/tokenize", {"model": "qwen3.8-27b-gist", "prompt": reasoning + content})["tokens"]
        gist_ids = [i for i in ids if i >= FIRST]
        literal = "<gist_" in content
        print("temp %.1f | %-55s | out %4d tok | gist ids in output: %d | literal <gist_: %s" % (temp, p[:55], usage["completion_tokens"], len(gist_ids), literal))
        bad += len(gist_ids)
print("TOTAL gist ids emitted:", bad, "=> ", "PASS" if bad == 0 else "FAIL")

sys_gist = "".join("<gist_%d>" % i for i in range(0, 398))
reasoning, content, usage = chat([{"role": "system", "content": sys_gist}, {"role": "user", "content": "What is 17*23? Answer briefly."}], max_tokens=200)
print("student path: prompt_tokens %d (398 gist + wrapper) | reply: %r" % (usage["prompt_tokens"], content[:200]))
count = post("/tokenize", {"model": "qwen3.8-27b-gist", "messages": [{"role": "system", "content": sys_gist}, {"role": "user", "content": "hi"}]})["count"]
print("tokenize of 398-gist system + hi:", count, "(expect ~398 + ~55)")
