# Journey 4: How short can the summary get, and can the loop run itself?

*In everyday terms.* Journey 3 showed a one-quarter-length summary of the handbook works. This journey asked how much further it can be cut before the contractor's work suffers, and did so without a person watching: three boxes, three summary lengths, one controller that trained, tested, marked, filed, and switched off each box on its own.

**The uncertainties this retires.** E4, the compression-ratio knee on this prompt, and whether the research loop is robust enough to run unattended on a metered, unreliable provider.

## The questions

1. At 2:1, 8:1, and 16:1, does Claude Code still complete the twelve verifiable tasks, and where does tool-call validity fray?
2. Can one recipe go from a line in a file to a scored result line with no human step?

## What we believed going in

Shopify found their knee at 4:1 for a prose prompt. Ours is 91 percent JSON tool schemas. The 4:1 run in journey 3 had one invented tool name in 84 calls; the expectation was that higher ratios would fray the catalogue's edge first.

## What we ran

- One box per ratio, RTX PRO 6000 96 GB, about $1 to $1.47 per hour. Three of the first four hosts for the 2:1 run were bad (SSH key never accepted; host went offline; host vanished from the account with its logs). Each was detected and replaced.
- Segment maps derived from four logs so the working directory and the served model name are dynamic. Static span 17,539 tokens for all ratios; gist tokens 8,771 / 2,196 / 1,099.
- The journey 3 teacher cache reused unchanged for all runs: teacher and response token sequences are identical across ratios, only the student prefix differs.
- Worker chain on each box: download with three retries, build delta, train against the cache with out-of-memory retry at a shorter cap and warm start from saved rows after a crash, export, relaunch, generation self-test, ready marker.
- Controller on the workstation: poll each box, run the twelve-task evaluation through the gist tap when ready, verify every turn was swapped, apply the gate, sync artifacts, append a results line, destroy the box. Vanished boxes recorded rather than polled forever.

## What the GPU showed us

| Ratio | Gist tokens | Tasks | Tool calls | Malformed | Invented names | Unswapped turns | Input tokens per turn | Held-out KL, init to final |
|---|---|---|---|---|---|---|---|---|
| Teacher | 0 | 12 of 12 | 69 | 0 | 0 | | 24,258 | |
| 2:1 | 8,771 | 12 of 12 | 98 | 0 | 0 | 0 | 16,083 | 0.073 to 0.038 |
| 4:1 (journey 3) | 4,386 | 12 of 12 | 84 | 0 | 1 | 0 | 11,410 | 0.053 to 0.015 |
| 8:1 | 2,196 | 12 of 12 | 101 | 0 | 0 | 0 | 9,395 | 0.096 to 0.030 |
| 16:1 | 1,099 | 12 of 12 | 94 | 0 | 0 | 0 | 8,245 | 0.136 to 0.021 |

No knee on this task set at any ratio tried. The 16:1 gist, 1,099 tokens standing in for 17,539, passed all twelve tasks with perfect tool-name validity.

Caveats. The KL column is not comparable across ratios: each run's held-out set is drawn after its own sequence-length filter, and the 2:1 run's resumed half used a different subset again. Task and tool columns are directly comparable. The twelve tasks exercise five tools on a two-file repository; the catalogue's edge, where 4:1 once slipped, is not stress-tested here.

**The loop.** Two of three runs hit out-of-memory at the 32k cap and healed at 25.6k; the 2:1 run resumed from saved rows for its remaining 0.52 epoch. All three completed with zero human steps between ready and destroyed: 8:1 in nine minutes, 16:1 in seven, 2:1 in eleven. One checker defect surfaced, unittest-style tests not counted, and was fixed with the affected task rescored.

## What we now understand differently

- **The knee is further out than Shopify's, or beyond what this task set can see.** JSON schemas compress more gracefully than prose, or the twelve tasks are too easy to expose the loss. Both readings demand harder evaluation before shipping any ratio.
- **The loop earns its keep on failures, not on successes.** Two OOM recoveries, one crash resume, three bad-host replacements, and three unattended handoffs on one sweep. About $8 of GPU time and four hours of wall clock not lost, against two hours to write the loop once.
- **The provider is the unreliable component.** Four hosts rented for the 2:1 slot, one good. Provision above reliability 0.99 only, and sync logs during training, not after.
- **Cap sequence length below what fits the median.** 32k fit the median example and blew up on the longest. 30k held in journey 3; the retry ladder makes this safe but not free.

## What it cost

Three working boxes for 5.2, 6.5, and 5.2 hours, about $19.40 plus about $2 on three bad hosts. Account credit moved from $81.29 to $63.43 across the journey, including the pre-existing RTX 3060 instance.
