#!/bin/bash
# Headless Claude Code sessions from this Mac through tap (8081) -> tunnel (8000) -> vLLM on vast.
# Task file lines: "<repo_name>|<max_turns>|<task text>" (repo_name = seed or a dir under $SCRATCH/repos).
# Each session runs in a fresh copy of the repo. Tools allowlisted; MCP servers excluded (--strict-mcp-config)
# so the tool catalogue is the 25 built-in tools. Usage: run_sessions_local.sh <tasks.txt> <label> [concurrency]
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/claude-env.sh"
[ -n "${TAP_URL:-}" ] && export ANTHROPIC_BASE_URL="$TAP_URL"
export DISABLE_TELEMETRY=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
if [ -n "${MODEL_NAME:-}" ]; then export ANTHROPIC_MODEL="$MODEL_NAME" ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL_NAME" ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL_NAME" ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL_NAME"; fi
TASKS="$1"; LABEL="${2:-run}"; CONC="${3:-1}"
SCRATCH="${SCRATCH:-/private/tmp/claude-501/-Users-arunmenon-projects-gisting/82deba89-c9a1-41e0-9e61-ec090b34e902/scratchpad}"
OUT="$HERE/logs/sessions/$LABEL"; mkdir -p "$OUT" "$SCRATCH/work/$LABEL"
export PATH="$SCRATCH/sessionvenv/bin:$PATH"   # python/pytest with the task repos installed
SEED="$SCRATCH/seed_repo"
if [ ! -d "$SEED" ]; then
  mkdir -p "$SEED" && cd "$SEED" && git init -q
  printf 'def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n\ndef mean(values):\n    return sum(values) / len(values)\n' > calc.py
  printf 'from calc import add, divide, mean\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_divide():\n    assert divide(6, 3) == 2\n\ndef test_mean_empty():\n    assert mean([]) == 0\n' > test_calc.py
  echo "# Seed repo for gisting sessions" > README.md
  git add -A && git -c user.email=cc@local -c user.name=cc commit -qm "seed"
fi
ALLOWED='Read,Edit,Write,Glob,Grep,Agent,TaskCreate,TaskUpdate,TaskList,TaskGet,TaskOutput,TaskStop,WebFetch,WebSearch,NotebookEdit,EnterWorktree,ExitWorktree,ListAgents,SendMessage,CronList,CronCreate,CronDelete,Skill,ReportFindings,Bash(git worktree:*),Bash(git checkout:*),Bash(git branch:*),Bash(python -m pytest:*),Bash(python3 -m pytest:*),Bash(pytest:*),Bash(ls:*),Bash(cat:*),Bash(head:*),Bash(wc:*),Bash(git status:*),Bash(git diff:*),Bash(git log:*),Bash(python -c:*),Bash(python3 -c:*),Bash(python -m:*),Bash(python3 -m:*),Bash(find:*),Bash(rg:*),Bash(grep:*)'
run_one() {
  local n="$1" repo="$2" turns="$3" task="$4"
  local src="$SEED"; [ "$repo" != "seed" ] && src="$SCRATCH/repos/$repo"
  local work="$SCRATCH/work/$LABEL/s$n"; rm -rf "$work"; cp -R "$src" "$work"; cd "$work" || return
  export PYTHONPATH="$work/src:$work"   # the working copy shadows the editable install, so tests exercise the session edits
  local start=$(date +%s)
  python3 -c 'import subprocess,sys
try: sys.exit(subprocess.run(sys.argv[1:], timeout=1800).returncode)
except subprocess.TimeoutExpired: print("SESSION_TIMEOUT", file=sys.stderr); sys.exit(124)' claude -p "$task" --output-format json --max-turns "$turns" --permission-mode acceptEdits --strict-mcp-config --allowedTools "$ALLOWED" < /dev/null > "$OUT/s$n.json" 2> "$OUT/s$n.err"
  local code=$?
  echo "s$n repo=$repo exit=$code wall=$(( $(date +%s) - start ))s $(python3 -c "import json; d=json.load(open('$OUT/s$n.json')); print('turns', d.get('num_turns'), '| result:', str(d.get('result'))[:100].replace(chr(10),' '))" 2>/dev/null || echo "(no json) $(tail -c 120 "$OUT/s$n.err" | tr '\n' ' ')")"
  if [ -n "${CHECK:-}" ]; then echo "check s$n: $(python3 "$HERE/driver/eval_checks.py" "$n" "$work" 2>&1 | tail -1)"; fi
  [ -z "${KEEP:-}" ] && rm -rf "$work"
}
n=0
while IFS= read -r line; do
  [ -z "$line" ] && continue; case "$line" in \#*) continue;; esac
  n=$((n+1)); line="${line%%\#\# requires:*}"; repo="${line%%|*}"; rest="${line#*|}"; turns="${rest%%|*}"; task="${rest#*|}"
  run_one "$n" "$repo" "$turns" "$task" &
  while [ "$(jobs -rp | wc -l)" -ge "$CONC" ]; do sleep 2; done
done < "$TASKS"
wait
echo "ALL_SESSIONS_DONE label=$LABEL sessions=$n"
