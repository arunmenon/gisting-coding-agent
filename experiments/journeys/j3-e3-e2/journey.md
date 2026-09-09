# Journey 3: Does the compressed handbook still get the job done?

*In everyday terms.* Journeys 1 and 2 measured the handbook, proved the contractor can be handed made-up words, and showed the training loop closes. This journey trained the made-up words properly, over every logged session, and then gave the contractor twelve real jobs twice: once with the full handbook, once with the compressed one. Same jobs, same checker, same server.

**The uncertainties this retires.** E3 (can the teacher pass be precomputed so the loop is affordable), E2 (does a fully trained gist hold task quality), and the serving question (can Claude Code actually drive the gisted model with no changes to Claude Code).

## The question

With 4,386 learned gist tokens standing in for a 17,540-token static span, does Claude Code complete the same verifiable tasks it completes with the full prompt?

## What we believed going in

From J2: the pipeline closes, a 50-example run cut held-out KL by 28 percent, and the student emits well-formed tool calls. From the queue: E2 passes if tool validity is at least 99 percent and task success is within ten points of the teacher. From section 3.5: the latency win on this hybrid model is capped well below Shopify's.

## What we ran

- One RTX PRO 6000 Blackwell Server Edition (96 GB) at $1.268 per hour, 11.3 hours.
- Segment map rebuilt from J1, J2, and a probe session so the working-directory path is fully dynamic. Three instruction segments (601, 524, 419 tokens) and the 15,994-token tool block; 4,386 gist tokens at 4:1.
- A conditional chat template served with the gisted checkpoint: when the system message contains gist tokens, the tool block is not rendered, while the request still carries the tools array so the engine's tool-call parser works. Verified on the live server: 301 tokens with tools, 60 with gist tokens plus tools.
- Teacher cache (E3): vLLM's prompt log-probs at top-32 for all 1,457 usable examples, at 11 to 13 seconds per example, 4 hours 20 minutes. Top-32 mass 0.999 on average and at the tenth percentile. The engine had to run at 80 percent memory utilization with 4k-token prefill chunks; at 92 percent the full-vocabulary log-prob tensor for one chunk needs 8 GB and killed it.
- Training against the cache: one epoch over 1,171 examples with student length at most 30k tokens, 146 steps of 8 examples, learning rate 1e-3, batch-level KL reduction, 98 seconds per step, 4 hours.
- Evaluation: 12 seed-repo tasks with programmatic checkers (add a function and test, refactor, error handling, README, explain without editing), teacher arm through the tap in passthrough, student arm through the tap in gist mode, both on the same server, four concurrent sessions.

## What the GPU showed us

| Measure | Teacher (full prompt) | Student (gist) |
|---|---|---|
| Tasks passed | 12 of 12 | 12 of 12 |
| Turns / sessions | 64 / 12 | 72 / 12 |
| Input tokens per turn, median | 24,258 | 11,410 |
| Tool calls / malformed JSON | 69 / 0 | 84 / 0 |
| Calls to a non-existent tool | 0 | 1 |
| Time to first token, median | 23.8 s | 2.2 s |
| Turn latency, median | 35.3 s | 11.8 s |

| Training | Value |
|---|---|
| Held-out KL per token, mean-chunk init | 0.0534 |
| after 40 / 80 / 120 steps | 0.0436 / 0.0276 / 0.0243 |
| after 146 steps (one epoch) | 0.0152 |
| Gist ids emitted after training, masked, 10 generations | 0 |

The KL scale differs from J2 because this is KL over the teacher's renormalised top-32, not the full vocabulary; the relative drop is 72 percent in one epoch and had not flattened.

Two caveats on the table. The latency comparison is confounded: the teacher arm ran while the teacher-cache job was saturating the same server's CPU, so its 23.8 s first-token time is not a clean measurement. And the one bad tool call, an empty-argument call to `mcp__gisting__session_state`, a name that does not exist, puts student tool-name validity at 98.8 percent on 84 calls, a hair under the 99 percent gate on a sample too small to settle it. Claude Code rejected the call and the task still passed.

## What we now understand differently

- **The gist holds on this task set.** Twelve for twelve in both arms, with the student reading 13,000 fewer tokens per turn. That is the E2 gate, passed on a small verifiable set.
- **The one failure mode seen is catalogue boundary, not format.** The student never produced malformed JSON, but once invented a tool name. A gist compresses the list of what exists; making the boundary crisp is a data question for E6 and E7, and the fix is probably negative examples.
- **Every serving surprise was a string in the prompt.** The served model name appears inside the system prompt, so a server named differently from the training run broke anchoring until the tap normalised it. The date and git state are dynamic too. The anchoring rule for production is: derive segments from sessions that vary every such field, and refuse to swap when an anchor is missing.
- **E3 works but the bottleneck moved to CPU.** The cache made training a pure student-side job, and top-32 loses nothing measurable. But vLLM builds one Python dict per prompt position for log-probs, so caching a 33k-token example costs 12 seconds of CPU. A batched log-prob export would cut that tenfold.
- **The loop is now one script away from unattended.** Rows to score is fully mechanised; what remains is a wrapper that iterates recipes and appends a results line.

## What it cost

11.3 instance-hours at $1.268, about $14.30 plus disk. Account credit moved from $57.79 to $42.67, including the pre-existing RTX 3060 instance. Time split: 15 minutes to serve, 4 hours 20 minutes of teacher caching, 4 hours of training, 1 hour of evaluation in two arms, and roughly 90 minutes lost to restarts (an out-of-memory engine, a script edit that broke the serve line, an idle wait before the student arm started).
