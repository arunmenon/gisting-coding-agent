# Design brief: harness-agnostic span analysis, and a consolidated auto loop

Read-only. Produce a design recommendation, not code changes.

## Context

This repository implements **Steno** (learned prompt compression for agent calls; publicly known as gisting): the fixed preamble a coding agent re-sends to the model on every call is replaced by learned token rows trained by self-distillation with the base model frozen. It was built and run for one pair only: the **Claude Code** harness with **Qwen3.8-27B**, served with vLLM on rented GPUs.

A capability review (`experiments/journeys/reviews/steno-capability-20260925/codex-review.md`, and the summary in `steno-capability.md`) found Steno to be a working single-pair implementation, not yet reusable. Read both first.

Steno is pitched internally as a pillar of Lattice, our AI cost-optimization umbrella. The organisation (PayPal) has **its own custom coding harnesses** in addition to off-the-shelf ones. The next step is to run the experiment suite on another harness and distilled-model pair.

Two parts need a design now. Training is out of scope.

## Question 1: harness-agnostic span analysis

Today span analysis is hard-wired to Claude Code: `experiments/analysis/static_span.py`, `experiments/gist/span.py`, `experiments/gist/segments.py`, `experiments/gist/dataset.py` and `experiments/proxy/tap.py` assume the Anthropic Messages request format, Claude session metadata, top-level `system` blocks plus a `tools` array, Anthropic streaming events, and Qwen tokenizer defaults. Three code paths serialise the system text differently. The raw-value (per-session) rules are a regex that misses some path and ID shapes. Nothing checks that every captured call matches the measured span.

The goal is a **strategy interface with per-harness adapters**, so that onboarding a new harness, including an in-house one, takes little effort: implement an adapter, run the same span analysis, get the same outputs.

Answer:

1. **The adapter contract.** What exactly must a harness adapter provide? Think in terms of: request parsing into a canonical call record; identifying the system prompt, tool catalogue, messages and session identity; streaming/response handling; how the harness is launched for evaluation; how per-session values are declared or detected. Give a concrete interface sketch (method names, inputs, outputs, canonical record fields).
2. **What stays generic.** Which stages become harness-independent once calls are canonical: capture, span discovery across all calls, fixed versus per-session classification, invariance checking, tokenizer-specific counting, segment map and bundle identity (hashes), reporting.
3. **The model side.** Span analysis also depends on the tokenizer and chat template. Should that be a second, model-side adapter? What does it provide?
4. **Onboarding a new harness.** The minimal steps and artefacts to onboard a harness we have never seen (for example an in-house one), including how to validate the adapter before trusting its output: fixtures, golden captures, an invariance report.
5. **Risks.** Where the abstraction will leak, and how to keep adapters thin.

Do not speculate about how any specific harness other than Claude Code behaves; we have no evidence. Design for unknown harnesses.

## Question 2: the auto loop, and what to take from RSI

The auto loop (`experiments/loop/`, `experiments/vast/`) works in pieces but has proliferated: per-journey run scripts (`run_r8v2.sh`, `run_latency.sh`, `run_e5.sh`, `run_coverage.sh`, `run_seg.sh`, `run_j9_reeval.sh`, and more), separate provisioners for training, evaluation and benchmarking, historical instance files, and no single span-first entry point. Its operational lessons (spend guards, liveness checks, sync-before-destroy) are real and worth keeping.

Answer:

1. **Consolidation.** A target shape for one loop: a declarative run spec (pair, stages, budget, gates), a stage pipeline (span study, data, train, serve, evaluate, benchmark), a lifecycle state machine with persisted state, and pluggable compute backends. What replaces the per-journey scripts?
2. **RSI, time-boxed.** "Recursive self-improvement" is a popular term. We do not want to chase it. Pick **at most four** concrete, bounded mechanisms from that line of thinking that would genuinely help this loop, for example: an agent that reads the results ledger and proposes the next recipe within a budget; automatic failure triage that classifies a failed run and retries or stops; a lessons store that turns incidents into checks the loop enforces; gated promotion where a candidate only replaces the incumbent after passing held-out evaluation. For each: what it does, what it needs, what guardrails keep it safe and within budget, and what we would measure to know it helps. Say explicitly what you would **not** adopt and why.

## Output

For each question: a short recommendation, the interface or architecture sketch, and a list of next steps ordered by priority, each small enough to be one piece of work. End with the three next steps you would do first overall.

Be concrete and brief. No em dashes. Do not praise the existing work.
