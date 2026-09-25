# Note to Srini (Slack)

Ready to paste. Deck and white paper go as attachments.

---

Hi Srini, following up on the Shopify gisting blog you shared a few weeks back.

We set out to reproduce it on our own stack: Claude Code as the harness, a self-hosted Qwen3.8-27B as the model. The idea: a coding agent re-sends the same ~20k-token preamble, mostly tool schemas, on every call. Gisting teaches the model a short learned stand-in for it, with the base model frozen.

What we saw on that pair:
• Input per turn down from 24.3k to 9.4k tokens at 8:1, with task scores matching the full prompt on our suites
• H100: 2x the request rate within the latency target, and 44% higher peak throughput
• H200: level at peak, and 1.2 to 1.7x ahead under heavy load

While reproducing it, we built what we needed to scale the self-distillation flow beyond one pair, with a few RSI tenets baked in. We're calling this capability *Steno*, under Lattice:
• *Span analysis:* one adapter per harness feeds a shared analysis of what the agent re-sends on every call
• *Trainer:* learns the Steno tokens by self-distillation, base model frozen
• *Proxy:* swaps them in at serving time, with no change to the agent or the serving engine
• *Benchmark pack:* task suites scored against the full prompt, plus a serving benchmark
• *Auto loop:* runs the other four from one spec, with budget and pass gates. The RSI tenets sit here, kept bounded: failure triage, lessons turned into checks, gated promotion, and a next-recipe proposer that a person approves

It also stacks with the distillation track: distil a model, then Steno it, for a smaller model reading a shorter prompt.

So far this is one harness and model pair, and cost per completed task is still to prove. Next, we'd like to try it on a Jetstream harness: write its adapter, run the suite on that harness with a distilled model, and if it holds, a guarded trial in the inner loop.

Deck and white paper attached. Happy to walk you through it.
