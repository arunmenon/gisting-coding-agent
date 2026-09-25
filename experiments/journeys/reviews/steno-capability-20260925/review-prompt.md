# Review request: is Steno a reusable capability, or a one-off study?

Run read-only from the repository root. Emit your review to stdout.

## 1. Context

This repository holds a research program that compressed a coding agent's fixed prompt preamble into learned tokens. The technique is known publicly as gisting; internally we now call the capability **Steno**. It was built and run for exactly one pairing: the **Claude Code** harness with the **Qwen3.8-27B** model, self-hosted on rented GPUs with vLLM.

We are pitching Steno to our CTO as a new pillar under Lattice, our AI cost-optimization umbrella. The pitch says the next step is to rerun the whole experiment suite, span study first, on the **next harness and distilled-model pair**. For that to be credible, the five parts below need to exist as working, reusable pieces, not just as scripts that happened to work once.

The deck describes Steno as five parts:

1. **Span analysis:** measures what the harness re-sends on every call, and separates the fixed part from the per-session values that must stay raw.
2. **Trainer:** adds new token rows to the model and trains them by self-distillation, with the base model frozen.
3. **Proxy:** swaps the fixed span for the Steno tokens, so the agent and serving engine stay unchanged.
4. **Evaluation:** task suites scored against the full prompt, plus a serving benchmark.
5. **Auto loop:** provisions a GPU, trains, serves, evaluates, syncs results and tears down, with spend guards.

## 2. Where the code is

| Part | Likely locations |
|---|---|
| Span analysis | `experiments/analysis/static_span.py`, `experiments/gist/span.py`, `experiments/gist/segments.py`, `experiments/proxy/tap.py` (capture) |
| Trainer | `experiments/gist/train.py`, `dataset.py`, `teacher_cache.py`, `prepare_checkpoint.py`, `export_rows.py`, `mask_gist_logits.py`, `memprobe.py` |
| Proxy | `experiments/proxy/tap.py`, `stub.py`, `smoke.sh`; `experiments/vast/serve_gist.sh`, `apply_gist_delta.sh`, `experiments/gist/out/chat_template_gist.jinja` |
| Evaluation | `experiments/driver/` (task lists, `eval_hard.py`, `eval_checks.py`, `eval_coverage.py`, `run_sessions.sh`), `experiments/bench/` (serving benchmark) |
| Auto loop | `experiments/loop/` (`controller.py`, `provision.sh`, `eval_sweep.py`, run scripts), `experiments/vast/` (provisioning, supervision, watchdog, `bench_provision.sh`, `rsh.sh`) |

Also read for context: `Gisting-NeurIPS-paper.html` (the white paper), the journey records under `experiments/journeys/`, and the two earlier reviews under `experiments/journeys/reviews/` (`review-20260908T112003Z-codex.md`, `review-20260915T073918Z-codex.md`) with the reconciliation of the first.

## 3. What to do

For each of the five parts:

**A. Verify the description.** Does the code actually do what the one-line description says, for the pair that was studied? Quote the file and function that does it. Flag any part of the description the code does not support.

**B. Find the coupling.** List every place where the part is hard-wired to Claude Code, to Qwen3.8-27B or its tokenizer or chat template, to vLLM, to vast.ai, to a specific GPU, to specific paths, or to one-off experiment names. For each, say what would have to change for a different harness or a different model. State facts about the code only. Do **not** speculate about how other harnesses behave; we have no evidence about them.

**C. Find the gaps.** What is missing for this part to be run by someone else on a new pair: configuration instead of constants, a single entry point, documentation, tests, validation checks, error handling, reproducibility (pinned versions, seeds, hashes), data the repo does not contain. Include anything the earlier reviews found that is still open for this part.

**D. Distilled-model readiness.** The next pair uses a distilled model. Flag anything in the trainer, proxy or serving path that assumes a particular model size, architecture (for example the hybrid attention of Qwen3.8), vocabulary size, or embedding layout.

## 4. Output format

Open with a verdict of at most five sentences: how close Steno is to being a reusable capability, and the single biggest blocker.

Then one section per part, in the order above, each with:

- **Verified:** yes, partly or no, with one sentence and a file reference.
- **Coupling:** bullet list, each with file and line or function.
- **Gaps:** bullet list.

Then a consolidated TODO list, in this exact form, one item per line, ordered by priority:

```
- [ ] P<1|2|3> · <part> · <concrete action> · <file(s)>
```

P1 means it blocks running the suite on a second pair. P2 means the run would work but be fragile or unrepeatable. P3 means polish.

Do not praise. Be concrete. No em dashes.
