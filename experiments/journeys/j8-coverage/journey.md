# Journey 8: Can more data teach the summary the rare tools?

*In everyday terms.* The one-page summary of the handbook covers the tools the contractor uses every day. Does adding a week of practice with the rarely used tools make them reach for those tools when asked? We tried, and they still reach for them only about half the time.

**The uncertainty this retires.** E6, whether targeted coverage data closes the rare-tool gap at 8:1.

## What we ran

- Sixteen coverage tasks (driver/tasks_coverage.txt), each requiring named rarely used tools: notebook editing, task tracking and background task output, agent listing, worktrees, cron listing, web search, sub-agents, skills, findings, messaging. A scorer (driver/eval_coverage.py) passes a task when every required tool was called at least once, regardless of outcome.
- 48 sessions collected through the full-prompt teacher (three passes), which reached every required tool on 16 of 16 tasks and used 21 distinct tools. 299 training examples resulted; 29 sub-agent turns were correctly refused by the builder.
- Teacher log-probabilities cached for the new examples (top-32 mass 0.999), merged with the 1,494 base examples, and the corrected 8:1 rows retrained from mean-chunk init for one epoch (held-out KL 0.0188 to 0.0084).
- Hard exam plus teacher rerun on the same box; coverage exam in gist mode; then, on a second box, the same coverage exam on the pre-coverage 8:1 model as the baseline.

## What the GPU showed us

| Model | Hard exam | Coverage exam | Distinct tools used on the coverage exam |
|---|---|---|---|
| Teacher | 15 of 16 | 16 of 16 | 21 |
| 8:1 corrected, base data | 16 of 16 (journey 5) | 10 of 16 | 21 |
| 8:1 corrected, base plus coverage data | 14 of 16 | 9 of 16 | 17 |

Both gisted models miss the same tasks: worktrees (both tasks), web search, and messaging; the coverage-trained one also missed agent listing and one Agent task, and the baseline missed cron listing and one task-tracking task. On the hard exam the coverage-trained model kept all three absolute-path tasks correct but wrote an easy control task's files to an invented directory once, with the working-directory line present verbatim and every turn swapped.

## What we now understand differently

- **Rare-tool reachability is a capacity limit of the gist at this ratio, not a data shortage.** Three hundred targeted examples and a lower final KL changed the coverage score by minus one. The compressed catalogue keeps the common tools reachable and makes the rare ones a coin flip.
- **Path fidelity has a residual stochastic failure.** The verbatim rule removed the systematic failure, three of three to zero, but one in sixteen sessions still invented a directory. Any deployment needs the tap to validate write paths against the session's directory, or the client to reject them.
- **The two exams measure different things and both are needed.** The hard exam saw the coverage model as nearly the teacher's equal; the coverage exam saw a 60 percent model.
- **Provider losses continued.** Two hosts failed their SSH window and were destroyed, about $1.

## What it cost

Coverage box 10.2 hours at $1.268, about $12.90; baseline box 0.4 hours, about $0.50; two failed hosts about $1. Account credit moved from $40.28 to $15.83 across journeys 6 to 8, including the pre-existing RTX 3060 instance.
