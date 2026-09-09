Subject: Gisting a coding agent — artifacts, journey, and what we learned

Hi,

Sharing the outcome of a short research program on "gisting" for coding agents: compressing the large fixed preamble (behavioural rules + tool schemas) that a coding agent re-sends to the model on every step, by replacing it with a handful of learned "gist" tokens trained with the base model frozen.

This follows Shopify's engineering report on gisting (shopify.engineering/gisting), which applied the technique to their production coding agent and reported substantial serving savings. We set out to test whether it **transfers** to a different setup — a preamble that's overwhelmingly tool schemas, on a model we host ourselves — and what holds up under scrutiny.

Two parts below — where everything is, and what we found.

## 1. The artifacts

- **Whitepaper** (full account): `Gisting-NeurIPS-paper.docx` — method, results, honest limitations, and an independent adversarial review reconciled in.
- **Executive deck** (TCO lens, ~10 min read): `Gisting-CTO-deck.pptx` (editable) and a web version. Bottom line is on slide 2.
- **Code + everything above**: GitHub — `arunmenon/gisting-coding-agent`.
- **Trained weights + data** (Hugging Face, private, access on request): model `ledzepu2/gisting-qwen38-gist`, dataset `ledzepu2/gisting-coding-agent-sessions`.

## 2. The journey and the insights

We ran it in phases: measure the fixed preamble from real logged sessions; grow the model's vocabulary and train the gist by self-distillation; push the compression to find where it breaks; measure what it buys at serving time; and report what we couldn't score. The whole thing ran through an automated, cost-guarded loop (provision GPU → train → serve → evaluate → destroy).

What we learned — a development study, so single runs on small, partly reused task sets, not a validated benchmark:

- **The preamble is a real, recurring tax**: ~17.5–21k tokens per turn, over 90% tool schemas, ~0.72 of a short session's input.
- **A gist can match the full prompt** on our suite at every ratio from 2:1 to 16:1, cutting tokens read per turn by roughly half to two-thirds.
- **The one failure that mattered**: session-specific values (a path with a session id) got baked into the gist and reproduced wrong; keeping them raw fixed it. Every deployment will hit this.
- **On this architecture the payoff is throughput, not latency** — ~16% more requests/minute at 8 concurrent sessions. In plain terms: more sessions per GPU under load, not a faster single reply.
- **Recommended operating point: 8:1** — it's the ratio we actually hardened and validated, and it sits at the knee of diminishing returns.

What's not yet proven: generalisation on unseen work, and a hard dollar-per-session number (needs a saturation test). That validation is days of work, not months — the tooling already exists.

Happy to walk through any of it.

Arun
