#!/usr/bin/env python3
"""Teacher-vs-student parity probe on the gisted server (weights for real tokens are unchanged, so
the teacher prompt run on this server IS the teacher). For held-out examples whose logged response
contained a tool call, run both prompts through /v1/completions greedily and compare the first tool
call's name and arguments. Usage: parity_probe.py /root/data/train.jsonl <n> [seed]"""
import json, random, re, sys, urllib.request
from transformers import AutoTokenizer
BASE = "http://127.0.0.1:8000"
tok = AutoTokenizer.from_pretrained("/root/qwen3.8-27b-gist")

def complete(prompt_text, max_tokens=600):
    body = {"model": "qwen3.8-27b-gist", "prompt": prompt_text, "max_tokens": max_tokens, "temperature": 0, "skip_special_tokens": False}
    req = urllib.request.Request(BASE + "/v1/completions", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=900).read())["choices"][0]["text"]

def first_tool_call(text):
    m = re.search(r"<tool_call>(.*?)</tool_call>", text, re.S)
    if not m: return None, None
    block = m.group(1)
    name = re.search(r"<function=([^>]+)>", block) or re.search(r'"name"\s*:\s*"([^"]+)"', block)
    params = dict(re.findall(r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", block, re.S))
    return (name.group(1) if name else None), params

path, n = sys.argv[1], int(sys.argv[2]); random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
examples = [json.loads(l) for l in open(path)]
with_tool = [e for e in examples if "<tool_call>" in tok.decode(e["response_ids"]) and len(e["teacher_ids"]) <= 30000]
random.shuffle(with_tool)
rows = []
for e in with_tool[:n]:
    logged_name, logged_params = first_tool_call(tok.decode(e["response_ids"]))
    t_out = complete(tok.decode(e["teacher_ids"], skip_special_tokens=False))
    s_out = complete(tok.decode(e["student_ids"], skip_special_tokens=False))
    t_name, t_params = first_tool_call(t_out); s_name, s_params = first_tool_call(s_out)
    rows.append({"logged": logged_name, "teacher": t_name, "student": s_name, "name_match": t_name == s_name, "args_match": t_name == s_name and t_params == s_params,
                 "student_has_call": s_name is not None, "teacher_has_call": t_name is not None, "student_out_head": s_out[:160].replace("\n", " ")})
    print(json.dumps(rows[-1]), flush=True)
k = len(rows)
print("SUMMARY n=%d | teacher emitted call %d | student emitted call %d | name match %d | args exact match %d" % (
    k, sum(r["teacher_has_call"] for r in rows), sum(r["student_has_call"] for r in rows), sum(r["name_match"] for r in rows), sum(r["args_match"] for r in rows)))
