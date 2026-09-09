#!/bin/bash
# Runs as user cc on the box. One headless Claude Code session per task line, each in a fresh
# copy of a small seed repo, through the tap. Output JSON per session in ~/gisting/logs/sessions/.
set -uo pipefail
export ANTHROPIC_BASE_URL=http://127.0.0.1:8081
export ANTHROPIC_API_KEY=dummy ANTHROPIC_AUTH_TOKEN=dummy
export ANTHROPIC_DEFAULT_OPUS_MODEL=qwen3.8-27b ANTHROPIC_DEFAULT_SONNET_MODEL=qwen3.8-27b ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3.8-27b ANTHROPIC_MODEL=qwen3.8-27b
export CLAUDE_CODE_ATTRIBUTION_HEADER=0 DISABLE_AUTOUPDATER=1 DISABLE_TELEMETRY=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
TASKS="${1:-$HOME/gisting/driver/tasks.txt}"
OUT="$HOME/gisting/logs/sessions"; mkdir -p "$OUT"
SEED="$HOME/gisting/seed_repo"
if [ ! -d "$SEED" ]; then
  mkdir -p "$SEED" && cd "$SEED" && git init -q
  cat > calc.py <<'PY'
def add(a, b):
    return a + b

def divide(a, b):
    return a / b

def mean(values):
    return sum(values) / len(values)
PY
  cat > test_calc.py <<'PY'
from calc import add, divide, mean

def test_add():
    assert add(2, 3) == 5

def test_divide():
    assert divide(6, 3) == 2

def test_mean_empty():
    assert mean([]) == 0
PY
  echo "# Seed repo for gisting E0 sessions" > README.md
  git add -A && git -c user.email=cc@local -c user.name=cc commit -qm "seed"
fi
n=0
while IFS= read -r task; do
  [ -z "$task" ] && continue; case "$task" in \#*) continue;; esac
  n=$((n+1)); work="$HOME/gisting/work/s$n"; rm -rf "$work"; cp -r "$SEED" "$work"; cd "$work"
  echo "=== session $n: $task"
  timeout 900 ~/.local/bin/claude -p "$task" --dangerously-skip-permissions --output-format json --max-turns 25 > "$OUT/s$n.json" 2> "$OUT/s$n.err"
  echo "exit=$? $(python3 -c "import json,sys; d=json.load(open('$OUT/s$n.json')); print('turns', d.get('num_turns'), 'cost_usd', d.get('total_cost_usd'), 'result:', str(d.get('result'))[:120].replace(chr(10),' '))" 2>/dev/null || echo "(no json)")"
done < "$TASKS"
