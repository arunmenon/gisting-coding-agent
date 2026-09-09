#!/bin/bash
# Runs INSIDE the vast container as root. Creates an unprivileged user (Claude Code refuses
# --dangerously-skip-permissions as root), installs pinned Claude Code, the tap, and task repos.
set -euo pipefail
CC_VERSION="${CC_VERSION:-2.1.259}"
id cc >/dev/null 2>&1 || useradd -m -s /bin/bash cc
apt-get install -y -qq git ripgrep >/dev/null 2>&1 || true
su - cc -c "curl -fsSL https://claude.ai/install.sh | bash -s $CC_VERSION" 
su - cc -c '~/.local/bin/claude --version'
mkdir -p /home/cc/gisting/logs /home/cc/gisting/proxy /home/cc/gisting/driver
cp /root/tap.py /home/cc/gisting/proxy/tap.py
cp /root/run_sessions.sh /root/tasks.txt /home/cc/gisting/driver/
chown -R cc:cc /home/cc/gisting
# tap on 8081 -> vllm on 8000, as user cc, in tmux
su - cc -c 'tmux new-session -d -s tap "python3 ~/gisting/proxy/tap.py --listen 127.0.0.1:8081 --upstream http://127.0.0.1:8000 --log ~/gisting/logs/requests.jsonl"'
sleep 1; su - cc -c 'tmux ls'
