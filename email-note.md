Subject: Gisting a coding agent: artifacts, journey, and what we learned

Hi,

Sharing the outcome of a short research program on "gisting" for coding agents: compressing the large fixed preamble (behavioural rules + tool schemas) that a coding agent re-sends to the model on every step, by replacing it with a handful of learned "gist" tokens trained with the base model frozen.

This follows Shopify's engineering report on gisting (shopify.engineering/gisting), which applied the technique to their production coding agent and reported substantial serving savings. We set out to test whether it **transfers** to a different setup (a preamble that's overwhelmingly tool schemas, on a model we host ourselves), and what holds up under scrutiny.

Two parts below: where everything is, and what we found.

## 1. The artifacts

Start with the two primary reads: the deck for the overview, the whitepaper for the full detail.

- **Whitepaper** (`Gisting-NeurIPS-paper.docx`): the full account, with method, results, honest limitations, and an independent adversarial review reconciled in.
- **Executive deck** (TCO lens, ~10 min read): `Gisting-CTO-deck.pptx` (editable) and a web version. Bottom line is on slide 2.
- **Code + everything above**: GitHub: `arunmenon/gisting-coding-agent`.
- **Trained weights + data** (Hugging Face, private, access on request): model `ledzepu2/gisting-qwen38-gist`, dataset `ledzepu2/gisting-coding-agent-sessions`.

## 2. The journey and the insights

We ran it in phases: measure the fixed preamble from real logged sessions; grow the model's vocabulary and train the gist by self-distillation; push the compression to find where it breaks; measure what it buys at serving time; and report what we couldn't score. The whole thing ran through an automated, cost-guarded loop (provision GPU → train → serve → evaluate → destroy).

What we learned. This is a development study, so single runs on small, partly reused task sets, not a validated benchmark:

- **The preamble is a real, recurring tax**: ~17.5–21k tokens per turn, over 90% tool schemas, ~0.72 of a short session's input.
- **A gist can match the full prompt** on our suite at every ratio from 2:1 to 16:1, cutting tokens read per turn by roughly half to two-thirds.
- **The one failure that mattered**: session-specific values (a path with a session id) got baked into the gist and reproduced wrong; keeping them raw fixed it. Every deployment will hit this.
- **J10 measured a replay advantage.** On H100, finite-window tests with 200-token outputs recorded **2x the target request rate passing the chosen latency criterion** (18 versus 36 req/min) and **+44% observed peak throughput** (42.7 versus 61.3 req/min; 43.75% unrounded). The mechanism and deployment capacity are not established. J11 confirmed a client connection-limit defect in the high-concurrency tests; removing the cap reduced throughput in three of four comparisons and changed the gist/full ratios. Those historical points are not uniformly conservative. The lower-concurrency peak, cache-off and open-loop figures are not invalidated by that defect; their other review qualifications remain open.
- **The cost comparison is corrected.** The observed H200 peak difference was -2%, using H100-selected settings; its historical 3.1x ratio at 128 requests was client-capped. On consistent quoted rental prices ($2.64/h H100, $3.65/h H200), H100+gist gives **23.23** requests per minute per ($/h), slightly below H200+full at **23.38**. The previous 22.5 H200 figure used an effective price. These replay measurements do not establish cheaper-card substitution or savings per successful coding task.
- **Recommended operating point: 8:1.** It's the ratio we actually hardened and validated, and it sits at the knee of diminishing returns.

The reviewer verified 202 archived J10 runs with zero recorded request errors; J11 adds eight separate runs with zero request errors, one per condition and no quality measurement. J11 measured 137 gist versus 126 full requests resident at 256 offered, with nearly full cache and preemptions. These are sampled observations, not precise hardware ceilings. Prefix-cache hit rates remain unequal (full 0.791 to 0.840, gist 0.580 to 0.626), favouring full in cached fraction; the effect on the comparison was not controlled. Generalisation, fair tuning, sustained performance and deployment economics remain to be validated.

Happy to walk through any of it.

Arun
