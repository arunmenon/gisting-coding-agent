# Note to Srini: gisting as a Lattice pillar

Two versions of the same message: the email, and a shorter Slack cut.

---

## Email

**Subject:** Gisting: following up on the Shopify blog, as a new Lattice pillar

Hi Srini,

In our last meeting you pointed us to Shopify's post on gisting. We took the idea and tried it on our own setup, and I'd like to propose it as a new pillar under Lattice.

**What it is, in brief.** A coding agent re-sends the same fixed preamble, mostly tool schemas plus rules, to the model on every call. Gisting replaces that preamble with a small set of learned tokens. The base model stays frozen, only the new token embeddings are trained, and a proxy swaps them in, so neither the agent nor the serving engine changes.

**What we did.** One pair: Claude Code with Qwen3.8-27B, self-hosted.

- The fixed preamble was 17.5 to 21k tokens per call, over 90% of it tool schemas.
- At 8:1 compression, input per turn fell from 24.3k to 9.4k tokens, and task scores matched the full prompt on our suites.
- In short H100 replays, the gisted setup handled 2x the request rate within each arm's own latency threshold and reached 44% higher peak throughput.

**What isn't proven yet.** This is one harness and model pair on our own task suites. Savings per successful task, quality at production load, and the reason for the throughput gain are still open. An external review caught a measurement defect in our load generator along the way; we corrected it, and the deck notes it.

**How it fits Lattice.** It sits alongside the meta-harness, adaptive routing and model distillation tracks. One synergy we'd propose testing: distil a model first, then gist the distilled model. We'd also propose the Jetstream inner loop as the first place to trial it.

**The ask.** Run the same experiment suite, starting with the span study, on the next harness and distilled-model pair; validate on held-out work; then a guarded pilot.

- Deck, 10 slides plus appendix: https://claude.ai/artifact/FC9EqhEMaNjchaeDns41Pb (PowerPoint attached)
- White paper: https://claude.ai/code/artifact/ba7fae28-8e2c-4312-b94e-693f112eb963 (Word version attached)
- Code and results: GitHub `arunmenon/gisting-coding-agent`

Happy to walk you through it.

Arun

---

## Slack

Hi Srini, following up on the Shopify gisting post you shared in our last meeting. We tried it on our own stack and I'd like to propose it as a new Lattice pillar.

In brief: a coding agent re-sends the same fixed preamble (tool schemas and rules) on every call. Gisting swaps it for a few learned tokens, with the base model frozen and a proxy in front, so the agent and serving engine don't change.

On Claude Code with Qwen3.8-27B at 8:1: input per turn went from 24.3k to 9.4k tokens with task scores matching the full prompt on our suites, and short H100 replays showed 2x the request rate within latency and 44% higher peak throughput. One pair only; savings per task and quality at load are still to prove.

Proposal: rerun the same experiment suite on the next harness and distilled-model pair, then a guarded trial in the Jetstream inner loop.

Deck: https://claude.ai/artifact/FC9EqhEMaNjchaeDns41Pb · White paper: https://claude.ai/code/artifact/ba7fae28-8e2c-4312-b94e-693f112eb963
