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
        if TAG and s.get("tag")!=TAG: continue
        runs.append(s)
    return runs

def mean_std(xs):
    xs=[x for x in xs if x is not None]
    if not xs: return (None,None)
    return (round(st.mean(xs),3), round(st.pstdev(xs),3) if len(xs)>1 else 0.0)

TAG="B1"
def main():
    global TAG
    d=sys.argv[1] if len(sys.argv)>1 else "."
    if len(sys.argv)>2: TAG=sys.argv[2]   # experiment tag to analyze (default B1); pass "" for all
    runs=load(d)
    if not runs: sys.exit("no closed-loop run summaries with arm+concurrency in "+d)
    by=defaultdict(lambda: defaultdict(list))  # arm -> conc -> [summary]
    for s in runs: by[s["arm"]][s["concurrency"]].append(s)
    report={}
    for arm in sorted(by):
        concs=sorted(by[arm])
        base=[s["e2e_p50"] for s in by[arm].get(1,[])]  # c=1 median E2E (unloaded)
        base_med=st.mean([x for x in base if x]) if base else None
        rows=[]; plateau=0; plateau_c=None
        for c in concs:
            ss=by[arm][c]
            tp=mean_std([s["throughput_rpm"] for s in ss])
            p95=mean_std([s["e2e_p95"] for s in ss])
            ttft=mean_std([s["ttft_p95"] for s in ss])
            kv=mean_std([(s.get("engine") or {}).get("kv_usage_max") for s in ss])
            rows.append({"concurrency":c,"n":len(ss),"rpm":tp,"e2e_p95":p95,"ttft_p95":ttft,"kv_max":kv})
            if tp[0] and tp[0]>plateau: plateau=tp[0]; plateau_c=c
        # capacity at several latency tolerances: highest c whose mean p95 E2E <= k x (c=1 median)
        caps={}
        for k in (2,3,4,6):
            slo=base_med*k if base_med else None; cap=None; rpm_at=None
            for r in rows:
                if slo and r["e2e_p95"][0] is not None and r["e2e_p95"][0]<=slo: cap=r["concurrency"]; rpm_at=r["rpm"][0]
            caps[f"{k}x"]={"slo_p95_s":round(slo,2) if slo else None,"sessions":cap,"rpm":rpm_at}
        report[arm]={"c1_median_e2e":round(base_med,3) if base_med else None,
                     "capacity_at_slo":caps,
                     "peak_rpm":round(plateau,2),"peak_rpm_at_c":plateau_c,
                     "curve":rows}
    # capacity lift full -> gist
    pair=[(a,b) for a,b in (("full","gist8"),("full16","gist16")) if a in report and b in report]
    for a,b in pair:
        lift={}
        for k,ca in report[a]["capacity_at_slo"].items():
            cb=report[b]["capacity_at_slo"][k]
            if ca["sessions"] and cb["sessions"]: lift[k]=f"{ca['sessions']} -> {cb['sessions']} sessions ({round((cb['sessions']/ca['sessions']-1)*100):+d}%)"
        pa,pb=report[a]["peak_rpm"],report[b]["peak_rpm"]
        ratio={}
        for r in report[a]["curve"]:
            m=[x for x in report[b]["curve"] if x["concurrency"]==r["concurrency"]]
            if m and r["rpm"][0] and m[0]["rpm"][0]: ratio[r["concurrency"]]=round(m[0]["rpm"][0]/r["rpm"][0],2)
        report[f"lift_{b}_vs_{a}"]={"capacity_at_slo":lift,"peak_rpm":f"{pa} -> {pb} ({round((pb/pa-1)*100):+d}%)" if pa else None,"rpm_ratio_by_concurrency":ratio}
    print(json.dumps(report,indent=2))
    json.dump(report,open(os.path.join(d,"capacity_report.json"),"w"),indent=2)

if __name__=="__main__":
    main()
