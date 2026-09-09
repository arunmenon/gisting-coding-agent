#!/bin/bash
# Runs INSIDE the vast container. Builds the gisted checkpoint dir: full base checkpoint (symlinked
# shards) with the two modified shards, config, and tokenizer from the delta copied over.
set -euo pipefail
BASE=$(python3 -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen3.8-27B'))")
OUT=/root/qwen3.8-27b-gist
mkdir -p "$OUT"
for f in "$BASE"/*; do ln -sf "$(readlink -f "$f")" "$OUT/$(basename "$f")"; done
for f in /root/delta/*; do rm -f "$OUT/$(basename "$f")"; cp "$f" "$OUT/"; done
ls -la "$OUT" | grep -vE "^l" | awk '{print $5, $9}'
python3 - <<'PY'
import json
from safetensors import safe_open
cfg=json.load(open('/root/qwen3.8-27b-gist/config.json')); tc=cfg.get('text_config',cfg)
with safe_open('/root/qwen3.8-27b-gist/model-00003-of-00018.safetensors','pt') as h: e=h.get_slice('model.language_model.embed_tokens.weight').get_shape()
with safe_open('/root/qwen3.8-27b-gist/model-00018-of-00018.safetensors','pt') as h: l=h.get_slice('lm_head.weight').get_shape()
from transformers import AutoTokenizer
t=AutoTokenizer.from_pretrained('/root/qwen3.8-27b-gist')
print('config vocab', tc['vocab_size'], '| embed', e, '| lm_head', l, '| tokenizer len', len(t), '| <gist_0> ->', t.convert_tokens_to_ids('<gist_0>'))
PY
