# Note to Srini: Steno as a Lattice pillar

Two versions of the same message: the email, and a shorter Slack cut.

---

## Email

**Subject:** Steno: following up on the Shopify gisting blog, as a new Lattice pillar

Hi Srini,

In our last meeting you pointed us to Shopify's post on gisting. We took the idea and tried it on our own setup, and I'd like to propose it as a new pillar under Lattice. We're calling it **Steno**: learned prompt compression for agent calls.

**What it is, in brief.** A coding agent re-sends the same fixed preamble, mostly tool schemas plus rules, to the model on every call. Steno replaces that preamble with a small set of learned tokens, the technique Shopify calls gisting. The base model stays frozen, only the new token embeddings are trained, and a proxy swaps them in, so neither the agent nor the serving engine's code changes; the served model carries the new token rows.

**What Steno is made of.** Five parts, all built and run in this study:

1. **Span analysis:** measures what the harness re-sends on every call, and separates the fixed part from the per-session values that must stay raw.
2. **Trainer:** adds new token rows to the model and trains them by self-distillation, with the base model frozen.
3. **Proxy:** swaps the fixed span for the Steno tokens, with no change to the agent or the serving engine's code.
4. **Evaluation:** task suites scored against the full prompt, plus a serving benchmark.
5. **Auto loop:** scripts and a controller that provision a GPU, train, serve, evaluate, sync results and tear down, with spend guards.

An independent review of these five parts found them working for the pair we studied but still coupled to it. The gaps are tracked as a TODO list in `steno-capability.md` in the repo, and the P1 items there need closing before the next-pair run.

**What we did.** One pair: Claude Code with Qwen3.8-27B, self-hosted.

- The fixed preamble was 17.5 to 21k tokens per call, over 90% of it tool schemas.
- At 8:1 compression, input per turn fell from 24.3k to 9.4k tokens, and task scores matched the full prompt on our suites.
- In short H100 replays, the Steno setup handled 2x the request rate within each arm's own latency threshold and reached 44% higher peak throughput.
- On a larger H200, the peak difference was near zero (85.3 vs 83.3 req/min), and per rental dollar the H100 with Steno and the H200 without it came out roughly even.

**What isn't proven yet.** This is one harness and model pair on our own task suites. Savings per successful task, quality at production load, and the reason for the throughput gain are still open. An external review caught a measurement defect in our load generator along the way; we corrected it, and the deck notes it.

**How it fits Lattice.** It sits alongside the meta-harness, adaptive routing and model distillation tracks. One synergy we'd propose testing: distil a model first, then apply Steno to the distilled model. We'd also propose the Jetstream inner loop as the first place to trial it.

**The ask.** Run the same experiment suite, starting with the span study, on the next harness and distilled-model pair; validate on held-out work; then a guarded pilot.

- Deck, 12 slides plus appendix: https://claude.ai/artifact/FC9EqhEMaNjchaeDns41Pb (PowerPoint attached)
- White paper: https://claude.ai/code/artifact/ba7fae28-8e2c-4312-b94e-693f112eb963 (Word version attached)
- Code and results: GitHub `arunmenon/gisting-coding-agent`

Happy to walk you through it.

Arun

---

## Slack

Hi Srini, following up on the Shopify gisting post you shared in our last meeting. We tried it on our own stack and I'd like to propose it as a new Lattice pillar, which we're calling Steno: learned prompt compression for agent calls.

In brief: a coding agent re-sends the same fixed preamble (tool schemas and rules) on every call. Steno swaps it for a few learned tokens, with the base model frozen and a proxy in front, so the agent and serving engine's code don't change.

Steno is five parts: span analysis, a trainer, a proxy, an evaluation suite and an auto loop that runs experiments on rented GPUs.

On Claude Code with Qwen3.8-27B at 8:1: input per turn went from 24.3k to 9.4k tokens with task scores matching the full prompt on our suites, and short H100 replays showed 2x the request rate within latency and 44% higher peak throughput. On a larger H200 the peak gain was near zero. One pair only; savings per task and quality at load are still to prove.

Proposal: rerun the same experiment suite on the next harness and distilled-model pair, then a guarded trial in the Jetstream inner loop.

Deck: https://claude.ai/artifact/FC9EqhEMaNjchaeDns41Pb · White paper: https://claude.ai/code/artifact/ba7fae28-8e2c-4312-b94e-693f112eb963
