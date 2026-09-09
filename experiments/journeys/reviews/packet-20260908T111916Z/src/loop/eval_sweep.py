#!/usr/bin/env python3
"""Evaluation-only sweep on ONE box: for each run in order, rebuild + serve that ratio's trained rows
(or reuse the current server in passthrough for the teacher arm), run the exam through the tap, score
with eval_hard.py, append a results line. Usage: eval_sweep.py <box.json> <journey> <tasks.txt> <runs...>
box.json: {"host","port","instance"}; runs: teacher | r2 | r4 | r8 | r16 (each needs loop/ratios/<run>/ locally with
segments.json, tokenizer/, gist_rows.pt already pushed to /root/ratios/<run>/ on the box).
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
box = json.load(open(sys.argv[1])); JOURNEY = sys.argv[2]; TASKS = sys.argv[3]; RUNS = sys.argv[4:]
RESULTS = os.path.join(ROOT, "journeys", JOURNEY, "results"); os.makedirs(RESULTS, exist_ok=True)
PY = os.path.join(ROOT, ".venv", "bin", "python3"); SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20"]
SCRATCH = os.environ.get("SCRATCH", "/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad")
def log(m):
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), m); print(line, flush=True)
    open(os.path.join(ROOT, "journeys", JOURNEY, "log.md"), "a").write("- " + line + "\n")
def ssh(cmd, tries=6, timeout=1800):
    for i in range(tries):
        try:
            r = subprocess.run(["ssh"] + SSH_OPTS + ["-p", str(box["port"]), "root@%s" % box["host"], cmd], capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 or "Permission denied" not in r.stderr: return r.stdout
        except subprocess.TimeoutExpired: pass
        time.sleep(10)
    return None
def tunnel_up(tport):
    subprocess.run("pkill -f 'ssh -N .* -L %d:' " % tport, shell=True)
    p = subprocess.Popen(["ssh", "-N"] + SSH_OPTS + ["-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes", "-p", str(box["port"]), "-L", "%d:127.0.0.1:8000" % tport, "root@%s" % box["host"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(12):
        time.sleep(5)
        if "gist" in subprocess.run(["curl", "-s", "-m", "20", "http://127.0.0.1:%d/v1/models" % tport], capture_output=True, text=True).stdout: return p
    p.terminate(); return None
for run in RUNS:
    tport, pport = 8300, 8301
    if run != "teacher":
        log("%s: building and serving" % run)
        out = ssh("bash /root/serve_ratio.sh %s; tail -1 /root/STATE" % run)
        if not out or "_READY" not in out: log("%s: serve failed: %s" % (run, (out or "")[-200:])); continue
    else:
        out = ssh("curl -s -m 20 localhost:8000/v1/models | grep -c gist")
        if not out or out.strip() == "0": log("teacher: no server up; run a ratio first"); continue
    tun = tunnel_up(tport)
    if tun is None: log("%s: tunnel failed" % run); continue
    reqlog = os.path.join(RESULTS, run, "requests_hard.jsonl"); os.makedirs(os.path.dirname(reqlog), exist_ok=True)
    tap_args = [PY, os.path.join(ROOT, "proxy", "tap.py"), "--listen", "127.0.0.1:%d" % pport, "--upstream", "http://127.0.0.1:%d" % tport, "--log", reqlog]
    if run != "teacher": tap_args += ["--gist", os.path.join(HERE, "ratios", run, "segments.json"), "--normalize", "qwen3.8-27b-gist=qwen3.8-27b"]
    tap = subprocess.Popen(tap_args, stdout=subprocess.DEVNULL, stderr=open(os.path.join(RESULTS, run, "tap_hard.log"), "a")); time.sleep(2)
    label = "hard_" + run; env = dict(os.environ, TAP_URL="http://127.0.0.1:%d" % pport, MODEL_NAME="qwen3.8-27b-gist", KEEP="1")
    log("%s: running exam" % run)
    with open(os.path.join(RESULTS, run, "driver_hard.log"), "w") as o:
        subprocess.run(["bash", os.path.join(ROOT, "driver", "run_sessions_local.sh"), TASKS, label, "4"], env=env, stdout=o, stderr=subprocess.STDOUT, timeout=7200)
    tap.terminate(); tun.terminate()
    scored = os.path.join(RESULTS, run, "hard_scores.json")
    envp = dict(os.environ, PATH=os.path.join(SCRATCH, "sessionvenv", "bin") + ":" + os.environ["PATH"])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "driver", "eval_hard.py"), TASKS, reqlog, os.path.join(SCRATCH, "work", label), "--json", scored], env=envp, capture_output=True, text=True, timeout=1200)
    open(os.path.join(RESULTS, run, "hard_scores.txt"), "w").write(r.stdout + r.stderr)
    try: res = json.load(open(scored))
    except Exception: res = {"passed": None, "total": None}
    line = {"run": run, "exam": os.path.basename(TASKS), "passed": res.get("passed"), "total": res.get("total"), "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    open(os.path.join(RESULTS, "hard_results.jsonl"), "a").write(json.dumps(line) + "\n")
    log("%s: %s" % (run, json.dumps(line)))
log("EVAL_SWEEP_DONE")
