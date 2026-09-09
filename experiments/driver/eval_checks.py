#!/usr/bin/env python3
"""Score one eval session's work dir. Usage: eval_checks.py <task_index 1-based> <work_dir> -> prints PASS/FAIL reason."""
import os, re, subprocess, sys
idx, work = int(sys.argv[1]), sys.argv[2]
os.chdir(work)
def read(p):
    return open(p).read() if os.path.exists(p) else ""
def pytest_ok(extra=""):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + extra.split(), capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-300:]
def pyfunc(src, name):
    return re.search(r"^def %s\(" % name, src, re.M) is not None
calc, tests, readme = read("calc.py"), read("test_calc.py"), read("README.md")
seed_calc = "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n\ndef mean(values):\n    return sum(values) / len(values)\n"
def result(ok, why): print(("PASS " if ok else "FAIL ") + why)
if idx == 1:
    ok, out = pytest_ok("test_calc.py -k subtract"); result(pyfunc(calc, "subtract") and "subtract" in tests and ok, "subtract defined=%s tested=%s pytest(-k subtract)=%s" % (pyfunc(calc, "subtract"), "subtract" in tests, ok))
elif idx == 2:
    r = subprocess.run([sys.executable, "-c", "from calc import mean; print(mean([]))"], capture_output=True, text=True); ok, out = pytest_ok()
    result(r.stdout.strip() == "0" and ok, "mean([])=%r pytest=%s" % (r.stdout.strip(), ok))
elif idx == 3:
    ok, out = pytest_ok("test_stats.py"); n = len(re.findall(r"^\s*def test_", read("test_stats.py"), re.M))  # module-level or unittest methods
    result(pyfunc(read("stats.py"), "median") and n >= 2 and ok, "median=%s tests=%d pytest=%s" % (pyfunc(read("stats.py"), "median"), n, ok))
elif idx == 4:
    hinted = all(re.search(r"^def %s\(.*:.*\)\s*->" % f, calc, re.M) for f in ("add", "divide", "mean")); ok, out = pytest_ok("-k", ) if False else pytest_ok()
    result(hinted, "all three functions hinted=%s (pytest=%s, baseline has one failing test)" % (hinted, ok))
elif idx == 5:
    ok, out = pytest_ok("test_calc.py -k clamp"); result(pyfunc(calc, "clamp") and "clamp" in tests and ok, "clamp=%s tested=%s pytest=%s" % (pyfunc(calc, "clamp"), "clamp" in tests, ok))
elif idx == 6:
    r = subprocess.run([sys.executable, "-c", "from calc import divide\ntry:\n    divide(1,0)\nexcept ValueError as e:\n    print('VE', str(e))\nexcept Exception as e:\n    print('OTHER', type(e).__name__)"], capture_output=True, text=True)
    result("VE cannot divide by zero" in r.stdout and "ValueError" in tests, "raise=%r test mentions ValueError=%s" % (r.stdout.strip(), "ValueError" in tests))
elif idx == 7:
    r = subprocess.run([sys.executable, "-c", "from calc import power; print(power(2,3), power(2,-1))"], capture_output=True, text=True)
    result(r.stdout.strip() == "8 0.5" and "power" in tests, "power=%r tested=%s" % (r.stdout.strip(), "power" in tests))
elif idx == 8:
    result(calc == seed_calc and "subtract" not in tests, "calc unchanged=%s" % (calc == seed_calc))
elif idx == 9:
    names = all(n in readme for n in ("add", "divide", "mean")); result(names and calc == seed_calc and len(readme) > 80, "readme names all=%s calc unchanged=%s len=%d" % (names, calc == seed_calc, len(readme)))
elif idx == 10:
    result(calc == seed_calc and "def test_mean_empty" in tests, "files unchanged=%s" % (calc == seed_calc))
elif idx == 11:
    ok, out = pytest_ok("test_calc.py -k even"); result(pyfunc(calc, "is_even") and ok, "is_even=%s pytest=%s" % (pyfunc(calc, "is_even"), ok))
elif idx == 12:
    r = subprocess.run([sys.executable, "-c", "from utils import flatten; print(flatten([[1,2],[3]]))"], capture_output=True, text=True); ok, out = pytest_ok("test_utils.py")
    result(r.stdout.strip() == "[1, 2, 3]" and ok, "flatten=%r pytest=%s" % (r.stdout.strip(), ok))
