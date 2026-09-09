# Journey 9: Per-segment ratio, and where the harness ran out of road

*In everyday terms.* The plan was clean: compress the rules hard, give the tool catalogue more room, and see whether rarely used tools become reachable again. The training worked. The measuring instrument, run after training, broke in a new way on every attempt, and the journey closes without a trustworthy number.

**The uncertainty this was to retire.** E4 per-segment: does keeping the tool block at 4:1 or 2:1, with rules at 8:1, restore rare-tool reach that a flat 8:1 loses.

## What we ran

Two gists trained cleanly on the merged base-plus-coverage data with the tool block at 4:1 (4,170 gist tokens) and 2:1 (8,168), rules at 8:1. Training loss fell normally on both; the rows are saved (results/r8t4/gist_rows.pt, results/r8t2/gist_rows.pt). Evaluation was to be the coverage exam in gist mode against the teacher's 16 of 16.

## What actually happened

The training is not in question. The evaluation harness failed six distinct ways across four attempts:

1. Tap port collision between the two concurrent runs: the second run's logging proxy could not bind, so its exam ran unlogged and scored null. Fixed: per-run ports derived from instance and run name.
2. Client-path request drops: 84 tap-side 502s while the engine logged only 200s. Four concurrent streaming sessions through one SSH tunnel dropped requests. This also revises journey 8's "server outage" to the same cause. Fixed: evaluation concurrency dropped to 2.
3. Work directories deleted before the file-based hard-exam scorer read them (a KEEP flag), so hard-exam scores read zero. Fixed.
4. Anchor brittleness: the segment map, derived from earlier journeys, had a static system segment carrying repo and git text that differs on a fresh box, so the whole swap fell back to passthrough. Fixed: the tap now swaps the anchors it finds and leaves a drifted one raw, verified offline to gist the full tool block.
5. Slow-booting hosts that never accepted SSH inside the 20-minute window, twice.
6. On the final attempt the local evaluation environment produced an invalid teacher reference (7 of 16; seedadv checks reporting files not intact), so even the gist coverage numbers would have had no valid baseline.

## What we now understand differently

- The method side is fine; the evaluation harness is the fragile part, exactly as the independent review warned. Each fix was correct and verified, and each uncovered the next fault. Six faults on one question is the finding: an evaluation loop assembled incrementally under time pressure is not trustworthy for a result you intend to publish, and needs to be rebuilt and validated end to end before the per-segment question is worth asking again.
- The per-segment ratio question is open. The trained rows exist, so a future clean attempt is evaluation only.

## What it cost

About $30 across the sweep and four re-eval attempts, most of it on failed or contaminated boxes. No trustworthy per-segment score was produced.

## Status: inconclusive. Program closed after this journey.
