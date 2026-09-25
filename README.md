# Gisting a Coding Agent

Compressing the fixed preamble a coding agent sends to a model on every turn by replacing
it with a small set of learned **gist tokens**. The preamble contains behavioural rules
and a JSON schema for every tool. The tokens are trained by self-distillation with the
base model **frozen**.
Target: Claude Code driving a self-hosted **Qwen3.8-27B** (hybrid attention) served
through vLLM, with **no changes to the client or the inference engine**.

Internally the capability is now called **Steno** (learned prompt compression for agent calls).
Its five parts, their status and the open TODO list are tracked in
[`steno-capability.md`](steno-capability.md); the design for harness adapters
and the run loop is in [`steno-design.md`](steno-design.md).

This is a **development study, not a validated benchmark**: every evaluation is a single
run of small, partly reused, author-designed task sets. The whitepaper reports negative
and unscored results plainly and incorporates an independent adversarial review.

## Paper

- `Gisting-NeurIPS-paper.docx` / `Gisting-NeurIPS-paper.html`: the whitepaper (self-contained).
- `Gisting-NeurIPS-review.md`: independent critical review, reconciled into the paper.
- `reviewer-brief.md`: brief used to solicit that review.
- `paper/`: build scripts (`build_neurips.py`, `draw_figs.py`, `build_docx.py`, `build_deck.py`) and figures.
- `Gisting-CTO-deck.html`: executive deck (TCO lens) walking the study from cost problem to capacity payoff to funding ask.

## Findings at a glance (see paper for caveats)

- The static preamble is ~17.5k–21k tokens, over 90% tool schemas, and ~0.72 of a short session's input.
- A one-epoch, embedding-only gist matched the full prompt 12/12 on an easy suite at every ratio 2:1–16:1 (single runs).
- Failure and fix: session-specific values folded into the gist broke path tasks; keeping them raw restored an 8:1 gist from 11/16 to 16/16.
- Serving (J10, H100 NVL): finite-window replay recorded **2x the target request rate passing the chosen latency criterion and +44% observed peak throughput** (43.75% unrounded). The mechanism and deployment capacity are not established. [J11](experiments/journeys/j11-conn/log.md) confirmed that the H200 100-request ceiling came from the load generator. Removing the cap produced sampled residency of 123 to 137 and lowered throughput in three of four comparisons. It does not invalidate the lower-concurrency J10 peak, cache-off or open-loop measurements; the other review findings remain open.
- Corrected quoted-price comparison: H100+gist **23.23**, H200+full **23.38** peak replay requests per minute per ($/h), using $2.64/h and $3.65/h. Cheaper-card substitution is not established. Prefix-cache hit rates also differ persistently (J11 full 0.791 to 0.840, gist 0.580 to 0.626), favouring full in cached fraction; this was uncontrolled. Benchmark code is under `experiments/bench/`, with 202 archived J10 runs and eight separate J11 runs, all with zero recorded request errors and no quality test at benchmark load.

## Source

- `experiments/gist/`: span analysis, checkpoint growth, distillation training.
- `experiments/proxy/`: the logging and span-substitution proxy (the "tap").
- `experiments/driver/`: headless session driver and evaluation suites.
- `experiments/loop/`: the automated experiment loop (provision → train → serve → eval → destroy).
- `experiments/journeys/`: per-experiment logs and results notes.
- `experiments/analysis/`: span and coverage analysis.
- `experiments/ledger.md`: GPU-hour ledger.

## Model & data (Hugging Face, private)

Trained deltas and distillation data are hosted on HF, not in git:

- Model: `ledzepu2/gisting-qwen38-gist`: gist-row deltas, segment maps, serving template. The base model (Qwen3.8-27B) is under its own license and is required to use these.
- Dataset: `ledzepu2/gisting-coding-agent-sessions`: compressed training sets and teacher caches.

## Build

```bash
cd paper
../experiments/.venv/bin/python draw_figs.py --serving-only
../experiments/.venv/bin/python build_neurips.py
../experiments/.venv/bin/python build_deck.py
../experiments/.venv/bin/python build_pptx.py
../experiments/.venv/bin/python build_docx.py
```
Builders resolve inputs and output paths relative to `paper/` and refresh the deliverables in the repository root. This checkout has the required Python packages in `experiments/.venv/`. See [paper/README.md](paper/README.md) for the full build instructions.

## Not tracked here

Model checkpoints, teacher caches, large `*.jsonl` data, virtualenvs, rented-instance SSH
keys, and credentials are excluded via `.gitignore`; model artifacts and data live on HF.
