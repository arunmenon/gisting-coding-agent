# Journey 1: How much of what Claude Code sends is the same every time?

*In everyday terms.* Imagine a contractor who, before every single sentence of a conversation, re-reads the entire employee handbook and the full catalogue of tools in the van. If the handbook and catalogue are most of what they read each time, teaching them a compressed version pays off. If they are a footnote next to the actual job, it does not. This journey measured the handbook.

**The uncertainty this retires.** Whether the fixed part of Claude Code's prompt is a large enough share of what the model reads, integrated over real sessions, for a 4:1 compression of it to matter. This is gate E0 in the experiment queue.

## The question

Of the tokens Qwen3.8-27B reads per turn while driving Claude Code 2.1.259, what fraction is byte-identical across sessions?

## What we believed going in

Shopify's engineering post on gisting compressed a 6,000-token system prompt to 1,500 learned tokens and reported 38 percent lower end-to-end latency. The queue's decision rule said gisting alone underdelivers if the static share is below about 25 percent. The architecture note in the queue (section 3.5) warned that Qwen3.8-27B is a hybrid model where only 16 of 64 layers keep a per-token cache over the prefix, so the latency win has a lower ceiling than Shopify's.

## What we ran

- Rented one RTX PRO 6000 Blackwell (96 GB) on Vast.ai at $1.388 per hour.
- Served `Qwen/Qwen3.8-27B` in bf16 with vLLM 0.28.0, text only, prefix caching on, 131k context, reasoning parser and tool parser per the vLLM recipe. vLLM speaks the Anthropic Messages API directly, so no translation proxy was needed.
- Put a 230-line logging proxy (the tap) between Claude Code and vLLM. It records every request and reassembled response with timing, and remaps Claude Code's reasoning effort "high" to "medium" because Qwen3.8 only accepts xhigh, medium, or low.
- Ran 8 headless `claude -p` sessions from the workstation through the tap, each in a fresh copy of a two-file Python repo: explain, fix failing tests, add a function, refactor, write a README, add type hints, add error handling, create a new module with tests. Tools were allowlisted, not skip-permissions.
- Counted the static span exactly by sending the system text and tool schemas through vLLM's own tokenize endpoint, so the number reflects the chat template as the model sees it.

## What the GPU showed us

| Measure | Value |
|---|---|
| Sessions / turns / tool calls | 8 / 43 / 50 (0 invalid tool JSON) |
| Static span as rendered | 21,109 tokens |
| of which system instructions | 603 |
| of which 51 tool schemas | 20,506 |
| of which 24 Playwright MCP tools | 4,512 |
| Context per turn (median / max) | 29,046 / 33,950 tokens |
| Integrated static share (median across sessions) | 0.73 |
| E0 gate (0.25) | PASS |
| Prefix cache token hit rate (vLLM counter) | 87.3 percent |
| Time to first token, median / p90 | 5.7 s / 7.0 s (includes hidden thinking) |
| Decode speed | about 26 tokens per second |
| Turn latency, median / max | 12.5 s / 45.6 s |

The static span is almost entirely tool schemas, not prose. The system instructions are 603 tokens; the tool catalogue is 34 times larger. Across the 8 sessions the system text differed in exactly two characters, the session directory digit in the working-directory path, at two positions. So the gistable layout is three static segments with two tiny dynamic injections, plus the tool block.

Turn one also carries a second, role=system message of about 5,800 tokens listing agent types and skills. Its content varied across turns (36 distinct versions in 43 turns), so it is not part of the byte-identical span as measured, but its stable prefix is a candidate for a per-machine segment.

## What we now understand differently

- **The share is far above the gate, but the sessions were short.** Median context was 29k tokens and the longest turn was 34k. At 100k context the same span is 21 percent. The gate is passed for short and medium sessions; long sessions need their own measurement in E1.
- **Prefix caching works on the hybrid architecture.** vLLM 0.28 runs the state-space layers in "align" cache mode and reported an 87 percent token hit rate. This is the E1 control arm, and it is already on.
- **The cheapest win is not gisting.** Removing the 24 Playwright MCP tools that failed to connect anyway would cut 4,512 tokens with zero training. Any gist plan should start from a trimmed tool catalogue.
- **The time-to-first-token number is not a prefill measure.** Claude Code asks for thinking with display omitted, so the first visible delta arrives after the model finishes thinking. vLLM's own prefill counter puts mean prefill at 2.3 s per request over the whole run, including the cold first call.

## What it cost

1.07 instance-hours at $1.388, about $1.60 plus disk. Account credit moved from $68.64 to $66.22 during the journey; part of that is a pre-existing RTX 3060 instance on the account that this program did not create or touch. Roughly 15 minutes of the hour was model download and compile, 20 minutes was sessions, and the rest was three launch attempts (a concurrency limit, a zombie engine, and a self-matching kill command), all recorded in log.md.
