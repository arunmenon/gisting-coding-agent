# Gisting a Coding Agent

Compressing the fixed preamble a coding agent sends to a model on every turn — the
behavioural rules plus a JSON schema for every tool — by replacing it with a small set
of learned **gist tokens** trained by self-distillation with the base model **frozen**.
Target: Claude Code driving a self-hosted **Qwen3.8-27B** (hybrid attention) served
through vLLM, with **no changes to the client or the inference engine**.

This is a **development study, not a validated benchmark**: every evaluation is a single
run of small, partly reused, author-designed task sets. The whitepaper reports negative
and unscored results plainly and incorporates an independent adversarial review.

## Paper
- `Gisting-NeurIPS-paper.docx` / `Gisting-NeurIPS-paper.html` — the whitepaper (self-contained).
- `Gisting-NeurIPS-review.md` — independent critical review, reconciled into the paper.
- `reviewer-brief.md` — brief used to solicit that review.
- `paper/` — build scripts (`build_neurips.py`, `draw_figs.py`, `build_docx.py`, `build_deck.py`) and figures.
- `Gisting-CTO-deck.html` — executive deck (TCO lens) walking the study from cost problem to capacity payoff to funding ask.

## Findings at a glance (see paper for caveats)
- The static preamble is ~17.5k–21k tokens, over 90% tool schemas, and ~0.72 of a short session's input.
- A one-epoch, embedding-only gist matched the full prompt 12/12 on an easy suite at every ratio 2:1–16:1 (single runs).
- Failure and fix: session-specific values folded into the gist broke path tasks; keeping them raw restored an 8:1 gist from 11/16 to 16/16.
- On this hybrid-attention model the serving benefit is **throughput under load** (~16% more requests/min at 8 concurrent sessions), not faster single replies.

## Source
- `experiments/gist/` — span analysis, checkpoint growth, distillation training.
- `experiments/proxy/` — the logging and span-substitution proxy (the "tap").
- `experiments/driver/` — headless session driver and evaluation suites.
- `experiments/loop/` — the automated experiment loop (provision → train → serve → eval → destroy).
- `experiments/journeys/` — per-experiment logs and results notes.
- `experiments/analysis/` — span and coverage analysis.
- `experiments/ledger.md` — GPU-hour ledger.

## Model & data (Hugging Face, private)
Trained deltas and distillation data are hosted on HF, not in git:
- Model: `ledzepu2/gisting-qwen38-gist` — gist-row deltas, segment maps, serving template. The base model (Qwen3.8-27B) is under its own license and is required to use these.
- Dataset: `ledzepu2/gisting-coding-agent-sessions` — compressed training sets and teacher caches.

## Build
```bash
cd paper
python build_neurips.py   # -> gisting-neurips.html
python draw_figs.py       # regenerate figures into paper_figs/
python build_docx.py      # -> Word document
```
Scripts contain absolute output paths from the authoring environment; adjust before running.

## Not tracked here
Model checkpoints, teacher caches, large `*.jsonl` data, virtualenvs, rented-instance SSH
keys, and credentials are excluded via `.gitignore`; model artifacts and data live on HF.
