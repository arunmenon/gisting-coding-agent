#!/usr/bin/env python3
"""Sweep controller (runs on the Mac, detached). For each box in boxes.json:
  poll /root/STATE over ssh with retries;
  on READY_FOR_EVAL: open a tunnel, start the gist tap with this run's segment map, run the
    12-task eval, score, verify every turn was swapped, sync artifacts, append a results line,
    destroy the box;
  on a *_FAILED marker or the global deadline: sync logs, append a failure line, destroy the box.
Everything is idempotent per box via state files under journeys/<journey>/results/<run>/.
"""
import json, os, re, subprocess, sys, time, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BOXES = json.load(open(sys.argv[1])); JOURNEY = sys.argv[2]; DEADLINE_H = float(sys.argv[3]) if len(sys.argv) > 3 else 12
RESULTS = os.path.join(ROOT, "journeys", JOURNEY, "results"); LEDGER = os.path.join(RESULTS, "sweep_results.jsonl")
GATE = json.load(open(os.path.join(HERE, "gate.json")))
VAST = os.path.join(ROOT, ".venv", "bin", "vastai"); PY = os.path.join(ROOT, ".venv", "bin", "python3")
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20"]
started = time.time()

def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg)
    print(line, flush=True)
    with open(os.path.join(ROOT, "journeys", JOURNEY, "log.md"), "a") as f: f.write("- " + line + "\n")

def ssh(box, cmd, tries=5, timeout=120):
    for i in range(tries):
        try:
            r = subprocess.run(["ssh"] + SSH_OPTS + ["-p", str(box["port"]), "root@%s" % box["host"], cmd], capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 or "Permission denied" not in r.stderr: return r.stdout
        except subprocess.TimeoutExpired: pass
        time.sleep(10)
    return None

def scp_down(box, remote_files, dest, tries=5):
    os.makedirs(dest, exist_ok=True)
    for i in range(tries):
        r = subprocess.run(["scp"] + SSH_OPTS + ["-P", str(box["port"])] + ["root@%s:%s" % (box["host"], f) for f in remote_files] + [dest], capture_output=True, text=True)
        if r.returncode == 0: return True
        time.sleep(10)
    return False

def destroy(box):
    for i in range(5):
        r = subprocess.run("echo y | %s destroy instance %s" % (VAST, box["instance"]), shell=True, capture_output=True, text=True)
        if "destroying" in r.stdout: log("%s: destroyed instance %s" % (box["run"], box["instance"])); return True
        time.sleep(10)
    log("%s: DESTROY FAILED for %s, needs manual action" % (box["run"], box["instance"])); return False

def free_port(base, idx): return base + idx

def run_eval(box, idx):
    run = box["run"]; tport = free_port(8100, idx); pport = free_port(8200, idx)
    subprocess.run("pkill -f 'ssh -N .* -p %s ' " % box["port"], shell=True)
    tunnel = subprocess.Popen(["ssh", "-N"] + SSH_OPTS + ["-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes", "-p", str(box["port"]), "-L", "%d:127.0.0.1:8000" % tport, "root@%s" % box["host"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)
    ok = False
    for i in range(6):
        r = subprocess.run(["curl", "-s", "-m", "20", "http://127.0.0.1:%d/v1/models" % tport], capture_output=True, text=True)
        if "qwen3.8-27b-gist" in r.stdout: ok = True; break
        time.sleep(10)
    if not ok: log("%s: tunnel/health failed" % run); tunnel.terminate(); return None
    reqlog = os.path.join(RESULTS, run, "requests_eval.jsonl"); os.makedirs(os.path.dirname(reqlog), exist_ok=True)
    tap = subprocess.Popen([PY, os.path.join(ROOT, "proxy", "tap.py"), "--listen", "127.0.0.1:%d" % pport, "--upstream", "http://127.0.0.1:%d" % tport, "--log", reqlog, "--gist", os.path.join(ROOT, box["segments"]), "--normalize", "qwen3.8-27b-gist=qwen3.8-27b"], stdout=subprocess.DEVNULL, stderr=open(os.path.join(RESULTS, run, "tap.log"), "a"))
    time.sleep(2)
    env = dict(os.environ, TAP_URL="http://127.0.0.1:%d" % pport, MODEL_NAME="qwen3.8-27b-gist", CHECK="1", KEEP="1")
    with open(os.path.join(RESULTS, run, "driver_eval.log"), "w") as out:
        subprocess.run(["bash", os.path.join(ROOT, "driver", "run_sessions_local.sh"), os.path.join(ROOT, "driver", "tasks_eval.txt"), "eval_" + run, "4"], env=env, stdout=out, stderr=subprocess.STDOUT, timeout=5400)
    tap.terminate(); tunnel.terminate()
    return score(box, reqlog, os.path.join(RESULTS, run, "driver_eval.log"))

def score(box, reqlog, driverlog):
    text = open(driverlog).read()
    passed = len(re.findall(r"^check s\d+: PASS", text, re.M)); total = len(re.findall(r"^check s\d+:", text, re.M))
    recs = [json.loads(l) for l in open(reqlog)] if os.path.exists(reqlog) else []
    ok = [r for r in recs if r.get("status") == 200 and r.get("response") and (r["response"].get("usage") or {}).get("input_tokens") and (r.get("request") or {}).get("tools")]
    unswapped = sum(1 for r in ok if not r.get("gist_applied"))
    catalogue = set(t["name"] for t in ok[-1]["request"]["tools"]) if ok else set()
    calls = 0; malformed = 0; bad_name = 0; names = collections.Counter()
    for r in ok:
        for b in r["response"].get("content") or []:
            if b.get("type") == "tool_use":
                calls += 1; names[b.get("name")] += 1
                if b.get("input_json_valid") is False: malformed += 1
                if b.get("name") not in catalogue: bad_name += 1
    ctx = [r["response"]["usage"]["input_tokens"] for r in ok]
    ttft = [r["ttft_s"] for r in ok if r.get("ttft_s")]
    return {"tasks_passed": passed, "tasks_total": total, "turns": len(ok), "unswapped_turns": unswapped, "tool_calls": calls, "malformed_json": malformed,
            "nonexistent_tool_calls": bad_name, "tool_name_validity": (1 - bad_name / calls) if calls else None, "input_tokens_median": statistics.median(ctx) if ctx else None,
            "ttft_median_s": round(statistics.median(ttft), 2) if ttft else None, "tools_used": dict(names)}

def gate(result):
    ref = GATE["teacher_reference"]; reasons = []
    if result["tasks_passed"] - ref["tasks_passed"] < GATE["task_pass_min_delta_points"] * ref["tasks_total"] / 100.0: reasons.append("task pass")
    if (result["tool_name_validity"] or 0) < GATE["tool_name_validity_min"]: reasons.append("tool-name validity")
    if result["malformed_json"] > GATE["malformed_json_max"]: reasons.append("malformed json")
    if result["unswapped_turns"] > GATE["unswapped_turns_max"]: reasons.append("unswapped turns")
    return ("PASS" if not reasons else "FAIL"), reasons

def finish(box, status, result, state_text):
    run = box["run"]; dest = os.path.join(RESULTS, run)
    scp_down(box, ["/root/train.log", "/root/export.log", "/root/gen_test_trained.log", "/root/STATE", "/root/gist_rows.pt", "/root/prepare.log", "/root/apply.log", "/root/vllm_gist.log", "/root/supervise_gist.log"], dest)
    kl = re.findall(r"eval KL/token ([0-9.]+)", open(os.path.join(dest, "train.log")).read()) if os.path.exists(os.path.join(dest, "train.log")) else []
    line = {"run": run, "ratio": box["ratio"], "instance": box["instance"], "status": status, "kl_init": float(kl[0]) if kl else None, "kl_final": float(kl[-1]) if kl else None,
            "gen_test": "PASS" if "PASS" in state_text and "gen_test_trained" in state_text else None, "result": result, "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if result: line["gate"], line["gate_reasons"] = gate(result)
    with open(LEDGER, "a") as f: f.write(json.dumps(line) + "\n")
    log("%s: recorded %s" % (run, json.dumps({k: line[k] for k in ("status", "kl_init", "kl_final", "gate") if k in line})))
    destroy(box); box["done"] = True

def main():
    done = set()
    while True:
        try:
            boxes = json.load(open(sys.argv[1]))   # reloaded each round so boxes can be added or replaced while running
        except Exception as error:
            log("boxes file unreadable: %s" % error); time.sleep(60); continue
        pending = [b for b in boxes if b["run"] not in done and b.get("active", True)]
        if not pending:
            if os.path.exists(os.path.join(HERE, "STOP_CONTROLLER")) or all(b["run"] in done for b in boxes): break
        for box in pending:
            idx = box.get("port_index", boxes.index(box)); box["done"] = False
            state = ssh(box, "cat /root/STATE 2>/dev/null; echo; tail -1 /root/watchdog.log 2>/dev/null")
            if not state or not state.strip():
                # unreachable: distinguish a flaky SSH hop from a box that no longer exists
                api = subprocess.run([VAST, "show", "instance", str(box["instance"]), "--raw"], capture_output=True, text=True).stdout
                try: status = json.loads(api).get("actual_status")
                except Exception: status = None
                if status is None:
                    log("%s: instance %s no longer exists (vanished); recording and moving on" % (box["run"], box["instance"]))
                    with open(LEDGER, "a") as f: f.write(json.dumps({"run": box["run"], "ratio": box["ratio"], "instance": box["instance"], "status": "vanished", "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
                    box["done"] = True; done.add(box["run"])
                else:
                    log("%s: unreachable this round (api status %s)" % (box["run"], status))
                continue
            last = [l for l in state.splitlines() if l.strip()]
            if "READY_FOR_EVAL" in state:
                log("%s: ready, running eval" % box["run"]); result = run_eval(box, idx)
                finish(box, "ok" if result else "eval_failed", result, state)
            elif any("_FAILED" in l or "FAILED_TO_START" in l for l in last):
                log("%s: terminal failure marker: %s" % (box["run"], [l for l in last if "FAIL" in l][-1][:160])); finish(box, "chain_failed", None, state)
            elif (time.time() - started) / 3600 > DEADLINE_H:
                log("%s: global deadline reached" % box["run"]); finish(box, "deadline", None, state)
            if box.get("done"): done.add(box["run"])
        time.sleep(120)
    log("all boxes done; ledger at %s" % LEDGER)

if __name__ == "__main__":
    main()
