#!/usr/bin/env python3
"""Coverage exam scorer: for each task line with '## requires: A,B', PASS if the session called every
required tool at least once (the call may have returned an error; the point is that the model knows the
tool exists and its shape). Reports per-tool coverage across the run. Usage: eval_coverage.py tasks.txt requests.jsonl [--json out]"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_hard as e
tasks=[]; 
for line in open(sys.argv[1]):
    if not line.strip() or line.startswith("#"): continue
    body, _, req = line.rstrip("\n").partition("## requires:")
    repo, turns, text = body.split("|", 2); tasks.append({"repo": repo, "text": text.strip(), "requires": [x.strip() for x in req.split(",") if x.strip()]})
sess=e.session_calls(sys.argv[2]); m=e.match(sess, tasks)
results=[]; used_any=set()
for i,t in enumerate(tasks):
    s=m.get(i)
    if not s: results.append({"task": i+1, "pass": False, "reason": "no session"}); continue
    used={n for n,_ in s["calls"]}; used_any|=used
    missing=[r for r in t["requires"] if r not in used]
    results.append({"task": i+1, "pass": not missing, "required": t["requires"], "missing": missing, "turns": s["turns"], "unswapped": s["unswapped"]})
for r in results: print("task %2d %s required=%s missing=%s" % (r["task"], "PASS" if r["pass"] else "FAIL", r.get("required"), r.get("missing")))
passed=sum(r["pass"] for r in results); print("SUMMARY passed %d/%d | distinct tools used %d: %s" % (passed, len(results), len(used_any), sorted(used_any)))
if "--json" in sys.argv: json.dump({"passed": passed, "total": len(results), "tasks": results, "tools_used": sorted(used_any)}, open(sys.argv[sys.argv.index("--json")+1], "w"), indent=1)
