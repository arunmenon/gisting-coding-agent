#!/usr/bin/env python3
"""Cheap coverage proxy for E1.5: which tools in the catalogue the logged sessions actually exercise,
and how often; plus turn-depth and context-length distributions."""
import collections, json, statistics, sys
log = sys.argv[1]
recs = [json.loads(l) for l in open(log)]
ok = [r for r in recs if r.get("status") == 200 and r.get("response") and (r["response"].get("usage") or {}).get("input_tokens") and (r.get("request") or {}).get("tools")]
catalogue = [t["name"] for t in ok[-1]["request"]["tools"]]
calls = collections.Counter(); invalid = 0; per_session = collections.defaultdict(list)
for r in ok:
    try: sid = json.loads(r["request"]["metadata"]["user_id"])["session_id"]
    except Exception: sid = "unknown"
    per_session[sid].append(r["response"]["usage"]["input_tokens"])
    for b in r["response"].get("content") or []:
        if b.get("type") == "tool_use":
            calls[b.get("name")] += 1
            if b.get("input_json_valid") is False: invalid += 1
print("turns", len(ok), "| sessions", len(per_session), "| tool calls", sum(calls.values()), "| invalid JSON", invalid)
print("catalogue", len(catalogue), "tools; used", len([n for n in catalogue if calls[n]]), "; never used:", [n for n in catalogue if not calls[n]])
print("calls:", calls.most_common())
ctx = [c for v in per_session.values() for c in v]
depth = [len(v) for v in per_session.values()]
print("context tokens: median %d p90 %d max %d" % (statistics.median(ctx), sorted(ctx)[int(.9*len(ctx))], max(ctx)))
print("turns per session: median %d max %d" % (statistics.median(depth), max(depth)))
