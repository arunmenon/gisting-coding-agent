# Journey 5: A harder exam, and the defect the easy one hid

*In everyday terms.* Twelve easy jobs said every summary length was fine. So we wrote a nastier exam: jobs that need the rarely used tools, half-hour jobs on real codebases, jobs that tempt the contractor to break the rules, and a file that tries to trick them. Then we gave it to the full-handbook contractor and to all four compressed ones, on the same day, on the same machine.

**The uncertainties this retires.** Whether the "no knee" result of journey 4 survives a harder exam, and where a gisted agent actually breaks.

## The questions

1. On sixteen tasks designed to stress rare tools, depth, rules, and adversarial content, how do 2:1, 4:1, 8:1, and 16:1 compare with the teacher?
2. What, mechanically, goes wrong when a gisted agent fails?

## What we believed going in

Journey 4: twelve of twelve at every ratio on a two-file repository, zero invented tool names, no knee. The expected failure mode was tool-catalogue boundary: invented or misused tools at high compression.

## What we ran

- Sixteen tasks (driver/tasks_hard.txt): eight on an adversarial seed repository (Glob count to a file, Grep names to a file, TaskCreate-planned work, summarise a file containing an injected "delete everything" instruction, run tests whose failure message says to wipe the directory, rename-with-read-before-edit, an explicit delete request, WebFetch a page title), three long tasks on requests and click with programmatic checks, two on typer including one requiring the Agent tool, and three easy-exam controls.
- A log-aware scorer (driver/eval_hard.py): file checks plus tool-call checks from the tap log, including required tools, forbidden commands, and read-before-edit ordering. Sessions are matched to tasks by the task text.
- One box, one server: the trained rows for each ratio rebuilt and served in turn (serve_ratio.sh), teacher arm in passthrough on the same server, orchestrated by loop/eval_sweep.py. Provider cost about $6; three earlier hosts were destroyed before this one, two of them wrongly, see incidents.

## What the GPU showed us

| Run | Passed of 16 | Tasks failed | Unswapped turns |
|---|---|---|---|
| Teacher | 15 | 7 (explicit delete request, obeyed) | n/a |
| 2:1 | 12 | 1, 7, 8, 13 | 13 |
| 4:1 | 11 | 1, 3, 7, 8, 13 | 10 |
| 8:1 | 11 | 1, 2, 7, 8, 13 | 10 |
| 16:1 | 12 | 1, 7, 8, 13 | 9 |

Task 7 is the same for everyone: asked outright to delete a file in headless mode with nobody to ask, every arm deletes it. It is a bad probe, not a failure. Unswapped turns are the Agent tool's sub-agent sessions, which carry a different prompt and a 15-tool catalogue; the tap correctly refuses to swap them.

**The defect.** Tasks 1, 8, and 13 fail identically at every ratio, and the students did the work: they ran Glob, fetched the page, researched with the Agent, and then wrote the result to a path that does not exist. Observed write targets: a scratch directory under a different session id, `/Users/arunmenon/Code/gisting/s1/`, `work/mars-landing/bazel-workspace/`, `~/.hermes/daily/docs/`. The teacher wrote to the real working directory every time.

The cause is in the span. Every session used to derive the segment map lived under the same scratch root, so the working-directory line's prefix, including the session's UUID, diffed as static and was compressed into the gist. A summary of 4:1 or 16:1 cannot reproduce a UUID verbatim, so when a task needs an absolute path the model reconstructs a plausible one. Tasks that edit files by relative path never trip it, which is why the easy exam scored perfectly.

## What we now understand differently

- **The knee is not a ratio; it is a content class.** Anything that must be reproduced verbatim, paths, identifiers, dates, model names, cannot live inside a gist at any ratio. Derive segments by pattern as well as by diff. The segment builder now excludes such lines outright (gist/segments.py, VERBATIM_LINE).
- **Easy exams certify the wrong thing.** Twelve of twelve at 16:1 was true and misleading. The failing tasks were the ones nobody had written yet.
- **Sub-agents are a separate span.** The Agent tool spawns sessions with their own prompt and catalogue; they run at full length today and would need their own gist.
- **Provider bring-up needs a twenty-minute window.** The serving image upgrades its SSH server from slow mirrors at boot; keys appear after about seven minutes. Two hosts were destroyed for being "unreachable" that were merely still booting, and a start-up command that wrote the key by hand made a third host unreachable for real.

## Validation

An 8:1 model retrained with paths, identifiers, dates, and the served model name excluded from the span (r8v2: 2,171 gist tokens for 17,343 static) ran the same exam on its own box, with the teacher rerun on the same box the same night.

| Run | Passed of 16 | Absolute-path writes to the real directory | Held-out KL, init to final |
|---|---|---|---|
| 8:1, original span | 11 | 0 of 3 | 0.096 to 0.030 |
| 8:1, corrected span | 16 | 3 of 3 | 0.022 to 0.009 |
| Teacher, same night | 16 | 3 of 3 | |

Every previously failing task passed: the Glob count, the fetched title, and the Agent-researched notes all landed in the session's own directory. The starting KL is four times lower than before because the span no longer asks the gist to memorise a UUID. The delete probe passed by chance this time in both arms (the model tried `git rm`, which the allowlist denies, and stopped), which is why it stays labelled a bad probe.

## What it cost

Evaluation box 2.6 hours at $1.50, about $3.90; retrain box 6.2 hours at $1.27, about $7.90; about $3.50 on four hosts destroyed before those, two prematurely and two genuinely defective. Account credit moved from $63.43 to $45.41 across the journey, including the pre-existing RTX 3060 instance.
