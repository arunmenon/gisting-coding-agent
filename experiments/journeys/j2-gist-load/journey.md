# Journey 2: Can the model take new words, and what do real sessions look like?

*In everyday terms.* Journey 1 measured the handbook. This journey asked two follow-ups. Can we actually add made-up words to this model's dictionary without it ever blurting them out? And when the contractor does real work on real codebases for half an hour at a time, how much of what they read is still the handbook?

**The uncertainties this retires.** The section 3.3 checkpoint gate (resized embeddings load and serve, gist ids are never sampled), the E1 long-session static share, and whether the E2 training pipeline runs end to end on one GPU.

## The questions

1. Does vLLM load Qwen3.8-27B with 4,387 extra embedding rows and a grown output head, and does it ever emit a gist id?
2. What is the static share integrated over long sessions on real repositories?
3. Does the two-pass self-distillation loop run within one 96 GB GPU, and does the KL move?

## What we believed going in

From J1: static span 21k tokens, share 0.73 on short sessions. From the queue: the checkpoint has 243 spare rows so a resize is unavoidable; the output head must not be able to produce gist ids; the share will fall as context fills with file contents.

## What we ran

- One RTX PRO 6000 Blackwell (96 GB) on Vast.ai at $1.402 per hour, after a first host stalled in "loading" for twelve minutes and was destroyed.
- Built the gisted checkpoint on the box: embedding grown from 248,320 to 252,544 rows, mean-chunk initialised gist rows, zero rows appended to the output head, 4,387 `<gist_N>` special tokens. Loaded in vLLM 0.28.
- Generation test: ten prompts at temperatures 1.0 and 1.5, including "repeat `<gist_0>`", scanned for any output id at or above the first gist id.
- Switched to the base model and collected sessions from the Mac through the tap: 10 long tasks on requests, click, and typer with a 40-turn cap, plus 110 of a planned 300 stratified tasks across those repos and a seed repo, stopped at a three-hour deadline. Tool catalogue trimmed to the 27 built-in tools by excluding MCP servers.
- Built 1,494 distillation examples from the logs, matching vLLM's Anthropic adapter exactly (inline system messages merged into the leading block, tool results as role=tool).
- Training chain on the box: rebuild delta from the J2 segment map, trainer smoke test, short run, export rows, relaunch with a logits mask, generation test again.

## What the GPU showed us

**Checkpoint gate: passed.**

| Check | Result |
|---|---|
| Resized checkpoint loads in vLLM 0.28 | Yes, 526,547-token KV pool |
| Gist ids emitted in 10 generations, unmasked | 0 |
| Student path with 398 gist tokens as system prompt | Accepted, correct arithmetic answer |
| Logits mask processor | Loads once named `module:Class` |

**Long-session share (E1).**

| Session class | Count | Median turns | Median context | Integrated static share |
|---|---|---|---|---|
| Short, up to 8 turns | 64 | 5 | 24k | 0.72 |
| Medium, 9 to 15 turns | 21 | 12 | 40k | 0.48 |
| Long, over 15 turns | 39 | 23 | 41k | 0.44 |
| Turns at 80k to 100k context | 14 | | | 0.18 |

Static span for the trimmed catalogue: 17,540 tokens (15,994 tool schemas, 1,546 instructions in three segments). One long session exhausted the 131k window at turn 23.

**Coverage.** 1,676 tool calls, none malformed. Bash, Read, and Grep are 90 percent. 18 of 27 tools never invoked.

**Prefix caching.** Token hit rate 60 percent over the run, down from 87 percent on short sessions.

**Training (E2 pipeline gate).** 25 optimizer steps, two examples per step, learning rate 2e-3, examples capped at 24k tokens, 142 in the training pool and 6 held out. One example costs 32 seconds for the teacher and student passes together.

| Measure | Value |
|---|---|
| Held-out KL per token at initialisation (mean-chunk rows) | 0.660 |
| Held-out KL per token after 25 steps | 0.473 |
| Trainable parameters | 22.5 million (4,387 rows by 5,120) |
| Gist ids emitted after training, masked server | 0 of 10 generations |
| Parity probe, 12 held-out tool-calling turns | student emitted a call 12 of 12; tool name matched the teacher 10 of 12; exact arguments 2 of 12 |

The teacher itself, run greedily, disagreed with its own logged call on 3 of the 12 turns, so exact-argument agreement is a hard bar even for the teacher against itself. The gist was trained on 50 examples and the probe overlaps the training pool, so read the probe as proof the loop closes, not as a quality number.

## What we now understand differently

- The tool catalogue, not the instructions, is the thing to compress. The instructions are 1.5k tokens; the schemas are 16k, and two thirds of them describe tools these sessions never used.
- The 0.25 gate holds as a session median for every class, but the deepest turns sit below it. Gisting's value on this model is concentrated in the first two thirds of a session.
- The static span depends on machine configuration and on repo state. The git block at the end of the prompt changes per repo and per commit, so it stays as raw tokens.
- The trainer's first two failures were both engineering, not method: a colon in a class name, and gradient checkpointing that only engages in training mode.

## What it cost

4.0 instance-hours at $1.402, about $5.60 plus disk, on the working host. A first host stalled in loading and cost about $0.25. Account credit moved from $65.99 to $57.79 across the journey, which also includes a pre-existing RTX 3060 instance on the account. Roughly: 15 minutes for download, delta, and the first gate; 3 hours of session collection; 25 minutes of training and tests; the rest was three restarts of the server.
