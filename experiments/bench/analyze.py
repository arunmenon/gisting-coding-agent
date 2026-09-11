#!/usr/bin/env python3
"""Aggregate loadgen run summaries into the CTO capacity answer (B1).

Reads a directory of run JSONs (each produced by loadgen.py, closed-loop, tagged
with arm + concurrency + repeat in the filename or summary), and computes, per arm:
  - throughput and p95 E2E vs concurrency (mean +/- std across repeats)
  - the SLO capacity: the highest concurrency whose mean p95 E2E stays within
    2x the arm's own c=1 median E2E (the agreed SLO)
  - peak sustained throughput (req/min) at or below that capacity

Run files are expected to carry, in their summary, keys: arm, concurrency, repeat
(add them via loadgen meta or encode in filename arm=..._c=..._r=...). This script
reads summary["arm"], summary["concurrency"]; repeats are grouped automatically.
"""
import json, glob, os, sys, math, statistics as st
from collections import defaultdict

def load(d):
    runs=[]
    for p in glob.glob(os.path.join(d,"*.json")):
        try: s=json.load(open(p)).get("summary",{})
        except Exception: continue
        if s.get("mode")!="closed": continue
        if "arm" not in s or s.get("concurrency") is None: continue
        runs.append(s)
    return runs

def mean_std(xs):
    xs=[x for x in xs if x is not None]
    if not xs: return (None,None)
    return (round(st.mean(xs),3), round(st.pstdev(xs),3) if len(xs)>1 else 0.0)

def main():
    d=sys.argv[1] if len(sys.argv)>1 else "."
    runs=load(d)
    if not runs: sys.exit("no closed-loop run summaries with arm+concurrency in "+d)
    by=defaultdict(lambda: defaultdict(list))  # arm -> conc -> [summary]
    for s in runs: by[s["arm"]][s["concurrency"]].append(s)
    report={}
    for arm in sorted(by):
        concs=sorted(by[arm])
        base=[s["e2e_p50"] for s in by[arm].get(1,[])]  # c=1 median E2E (unloaded)
        base_med=st.mean([x for x in base if x]) if base else None
        slo = base_med*2 if base_med else None
        rows=[]; cap=None; peak_rpm=0
        for c in concs:
            ss=by[arm][c]
            tp=mean_std([s["throughput_rpm"] for s in ss])
            p95=mean_std([s["e2e_p95"] for s in ss])
            ttft=mean_std([s["ttft_p95"] for s in ss])
            rows.append({"concurrency":c,"n":len(ss),"rpm":tp,"e2e_p95":p95,"ttft_p95":ttft})
            if slo and p95[0] is not None and p95[0]<=slo:
                cap=c; peak_rpm=max(peak_rpm, tp[0] or 0)
        report[arm]={"c1_median_e2e":round(base_med,3) if base_med else None,
                     "slo_p95_e2e":round(slo,3) if slo else None,
                     "capacity_sessions_at_slo":cap,
                     "peak_rpm_within_slo":round(peak_rpm,2) if peak_rpm else None,
                     "curve":rows}
    # capacity lift full -> gist
    if "full" in report and "gist" in report:
        cf=report["full"]["capacity_sessions_at_slo"]; cg=report["gist"]["capacity_sessions_at_slo"]
        if cf and cg: report["capacity_lift_gist_vs_full"]=f"{cf} -> {cg} sessions ({round((cg/cf-1)*100)}%)"
    print(json.dumps(report,indent=2))
    json.dump(report,open(os.path.join(d,"capacity_report.json"),"w"),indent=2)

if __name__=="__main__":
    main()
