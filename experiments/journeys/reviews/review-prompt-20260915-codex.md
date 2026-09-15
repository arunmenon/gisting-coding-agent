# Review request: gisting for coding agents, second round

## 0. How to run this

Run from the repository root with read-only access:

```
codex exec --sandbox read-only --cd /path/to/gisting < experiments/journeys/reviews/review-prompt-20260915-codex.md
```

Write your review to `experiments/journeys/reviews/review-<UTC timestamp>-codex.md`. If the sandbox is read-only, emit it to stdout and it will be captured verbatim. Your text will be checked in unedited. A coordinator will write a separate reconciliation document stating which findings are accepted, disputed, or deferred. Do not soften anything in anticipation of that.

## 1. Your role

You are the sole external reviewer of a research program that has never been externally validated beyond one prior review of yours. The authors are motivated to believe their result. The write-ups in this repository are advocacy documents: a conference-style paper, an executive deck, and two notes written to persuade a CTO to fund the next phase. Treat all prose as a claim to be checked, never as evidence.

Your job is not to be helpful to the authors. Your job is to be correct. Specifically:

- Verify numbers by recomputing them from raw run files. A number that appears in prose and in an aggregate summary file, both written by the same pipeline, is corroborated once, not twice.
- Where a claim cannot be checked from what is in the repository, say so explicitly and classify it as unverifiable rather than accepted.
- Look for the experiment that was not run, the control that is missing, and the confound that the design does not exclude. A clean number from a biased design is worse than a noisy number from a sound one.
- Assume the authors chose the framing that flattered them, and test whether a different, equally defensible framing would give a different headline.

Do not praise. Do not open with a summary of strengths. If the work is sound in a given dimension, one sentence saying so is sufficient.

## 2. What the program is, stated neutrally

A fixed instruction preamble is prepended to every request a coding agent makes to a self-hosted model. The program attempts to replace that static span with a smaller number of learned embedding rows, called gist tokens, trained by self-distillation against the same frozen base model, so that the served prompt is shorter while behaviour is preserved. The base model is a hybrid attention model. Ten journeys, numbered J1 to J10, were run on rented GPUs. J10, the most recent, is a serving-throughput benchmark whose numbers now carry the program's business case.

## 3. Artifact map

Everything is in this repository at the commit you have been given. Paths are repository-relative.

**Write-ups under review, in order of how much they claim:**

| Path | What it is |
|---|---|
| `Gisting-NeurIPS-paper.html` | The full paper. The primary document. Tables 1 to 7, Figures 1 to 9. |
| `Gisting-CTO-deck.html` | A 14-slide executive deck. Same claims, compressed and sharpened. |
| `cto-note.md` | A note to a CTO covering the J10 benchmark round only. |
| `email-note.md` | A shorter note covering the whole program. |
| `README.md` | Repository-level summary of findings. |

The `.docx` and `.pptx` files are generated exports of the paper and deck. Ignore them unless you suspect an export dropped or altered content.

**Journey records, one directory per experiment:**

`experiments/journeys/j1-e0-tap` through `j10-bench`. Each holds `journey.md`, the reader-facing account; `log.md`, the timestamped operations log including failures; and `results/`, the raw output synced off the GPU.

**The J10 serving benchmark, which is the new material:**

| Path | What it is |
|---|---|
| `experiments/bench/queue.md` | The pre-registered experiment queue, blocks B0 through B5 |
| `experiments/bench/loadgen.py` | The load generator. Closed-loop and open-loop modes. |
| `experiments/bench/analyze.py` | The aggregator that produces the capacity report |
| `experiments/bench/build_corpus.py` | Builds the replay corpus from logged sessions |
| `experiments/vast/bench_chain.sh` | The on-box orchestrator that ran the whole benchmark |
| `experiments/vast/serve_bench.sh` | Server launch wrapper |
| `experiments/journeys/j10-bench/results/` | 175 raw run files from the H100-class box, plus `capacity_report.json`, `best_config.txt`, `ladder.txt`, `STATE` |
| `experiments/journeys/j10-bench/b5-h200/results/` | 43 raw run files from the larger card |
| `experiments/journeys/j10-bench/journey.md` | The narrative account of J10 |

**Training and evaluation code from the earlier journeys:**

`experiments/gist/` holds the training pipeline: `span.py`, `segments.py`, `dataset.py`, `teacher_cache.py`, `train.py`, `prepare_checkpoint.py`, `mask_gist_logits.py`, `export_rows.py`. `experiments/driver/` holds the evaluation harness and task lists. `experiments/loop/` holds the automation controller. `experiments/proxy/` holds the tap that captured real agent traffic.

**The prior review:**

`experiments/journeys/reviews/review-20260908T112003Z-codex.md` is your own review from 2026-09-08, covering J1 through J9. `experiments/journeys/reviews/reconciliation-20260908.md` is the authors' disposition of each finding. `experiments/journeys/reviews/packet-20260908T111916Z/` is the frozen packet that review was run against, including `EXCLUSIONS.md`.

**Not in the repository:** training datasets, teacher caches, trained embedding rows, tokenizer files, and model checkpoints. These are held in private storage. Say plainly where their absence blocks verification.

## 4. Protocol

1. Recompute every headline number in section 5 from the raw run files, independently of `capacity_report.json` and of `analyze.py`. If your recomputation disagrees with the reported number, that is a finding regardless of direction or size.
2. Read `loadgen.py` and `analyze.py` as you would read code under audit. Ask what each measured quantity actually measures, whether the window over which it is computed is the window the denominator assumes, and what resolution the measurement has at each operating point.
3. Read `bench_chain.sh` end to end and reconstruct the exact sequence of what was run against what server configuration in what order. Compare that reconstruction against the method described in the paper and in `queue.md`. Report any divergence between what was planned, what was run, and what was described.
4. Check the operations logs for events during the runs that could contaminate results.
5. Where a comparison is made between two arms, identify everything that differs between them besides the variable under study.

Section 6 is the substance of the review. Do section 5 first, because the numbers gate everything in it.

## 5. Claims register

Verify each. For each, state: verified, verified with correction, unverifiable from the repository, or contradicted. Give the file paths and the arithmetic you used.

**Serving, from J10, the claims the business case rests on:**

1. On the H100-class card, with a tuned server, peak throughput is 42.7 requests per minute for the full prompt and 61.3 for the 8:1 gist, an increase of 44 percent.
2. Those figures come from three repeats at each concurrency with arm order balanced, and the run-to-run standard deviation is at most 0.6 requests per minute.
3. Within a latency objective of 95th-percentile end-to-end no worse than twice the unloaded median, the full prompt sustains about 18 requests per minute offered and the gist about 36, so the gist carries twice the load.
4. The throughput ratio grows with load: about 1.12 at one session, 1.38 at eight, 1.44 at thirty-two, 1.65 at forty-eight.
5. With prefix caching disabled, the gist-to-full throughput ratio is 2.00, 2.48 and 4.39 at four, eight and sixteen sessions, and each arm's cached-to-uncached ratio is as reported in the paper's cache-ablation table.
6. The server configuration was tuned and then applied identically to both arms, so the comparison is fair.
7. The untuned reference on the paper's original configuration gives 42.7 and 48.0 requests per minute at eight sessions, a 12 percent gain, and the paper's original single-run result understated the effect because the server was throttled.
8. The resident-sequence ceiling is set by the recurrent-state cache rather than by prompt length: on the larger card both arms held exactly 100 resident sequences at 83 percent key-value cache usage with no preemptions, while throughput differed by a factor of about 1.7.
9. On the larger card the peak gain is minus 2 percent, the ratio is 0.81 at sixteen sessions, plus 45 percent at thirty-two, and 3.1 at one hundred twenty-eight.
10. Throughput per dollar-hour is 16.2 and 23.2 for the smaller card without and with the gist, and 22.5 and 22.0 for the larger card, supporting the claim that the cheaper card with the gist matches the more expensive card without it.
11. The 16:1 gist delivers about two thirds of the 8:1 gain, measured against its own full-prompt control.
12. The benchmark comprised 201 runs with zero failures.

**Program-level claims carried forward from J1 to J9:**

13. The static span is about 21,000 tokens and occupies roughly 0.72 of a short session's context.
14. Quality is preserved at 8:1 on the exams reported, and the quality claims are correctly qualified given the exam design.
15. The compute cost figures in `experiments/ledger.md` reconcile with the per-journey costs quoted in the paper.

## 6. Review dimensions

Address each. Number your findings by dimension, as `F-<dimension>-<n>`, matching the convention in your prior review.

**Dimension 1: serving benchmark design.** Is the closed-loop concurrency sweep a valid instrument for the claim being made? Is the open-loop arrival test correctly specified, and is the latency objective it is scored against defensible and applied consistently to both arms? Consider the fixed output length, the prompt length cap, the replay corpus construction, the warm-up handling, the treatment of in-flight requests at the window boundary, and the measurement resolution at each concurrency. Does the design exclude the confounds it needs to exclude in order to support claim 1 and claim 3?

**Dimension 2: the fairness of the two arms.** Enumerate everything that differs between the full-prompt arm and the gist arm besides prompt length. Consider how the server configuration was selected and on which arm, the corpora, the cache state at the start of each run, the order of execution, and the model checkpoint each arm was served from. State whether any of these plausibly moves the headline number and in which direction.

**Dimension 3: statistical treatment.** Are repeats independent? Does the reported dispersion measure what the paper says it measures? Is the precision implied by the reported figures supported by the resolution of the underlying measurement? Are any two reported operating points actually distinguishable given that resolution? Is the choice of which concurrency counts as the peak defensible, or is it selected post hoc?

**Dimension 4: the mechanism claim.** The paper asserts that the gain comes from faster turnover rather than from more concurrent sessions, and it uses the larger-card residency observation as evidence. Does the evidence support that mechanism, exclude alternative mechanisms, or merely fail to contradict it? What additional measurement would distinguish the proposed mechanism from the alternatives?

**Dimension 5: the cost argument.** The throughput-per-dollar comparison is the load-bearing claim for the executive audience. Check its arithmetic, the price basis, whether spot-market rented pricing supports a fleet-level conclusion, whether the two cards were given equivalent tuning effort, and whether the comparison would survive a reader who selected different hardware or a different concurrency.

**Dimension 6: training and quality methodology from earlier journeys.** The serving gain is only meaningful if quality holds. Assess the training objective, the held-out construction, the exam design, the checkers, and whether the quality evidence is strong enough to license deploying the checkpoint that the benchmark served. State plainly whether quality was measured at the operating point the benchmark used.

**Dimension 7: the gap between evidence and the documents.** For each of the five write-ups, identify statements that outrun what section 5 established. Pay particular attention to the deck and the two notes, where compression tends to strip qualifiers. Where a document presents a measured number next to a projected or extrapolated one, check that the distinction survives.

**Dimension 8: reproducibility.** Could a competent third party reproduce the J10 result from this repository alone? What is missing, and is each omission a deliberate scope decision or an oversight?

**Dimension 9: prior review follow-up.** `reconciliation-20260908.md` claims specific fixes for findings F-2-1, F-2-3, F-2-4, F-6-3 and others, and defers several items as next-work. Verify in the code that each claimed fix is actually present and actually does what the reconciliation says. Separately, your prior finding F-8-4 called for throughput at a quality-constrained service level. Determine whether J10 answers that finding, answers a different question, or answers it only partially, and say which.

**Dimension 10: what you would do next.** Given everything above, name the smallest set of experiments that would either establish the program's central claim or kill it. Rank by information gained per GPU-hour. Be concrete about the design, not the topic.

## 7. Output format

Open with a verdict paragraph of at most six sentences: what is established, what is not, and whether the central business claim is currently supportable. No preamble.

Then the claims register as a table: claim number, status, corrected value where applicable, evidence path.

Then findings, grouped by dimension, each in this form:

```
F-<dim>-<n>: <one-line statement of the defect>. Severity: blocking | major | minor. Confidence: high | medium | low.

<What the artifacts show, with paths and arithmetic. What the documents claim. Why the gap matters. What would change your assessment.>
```

Severity is about consequence for the program's conclusions or for external publication. Blocking means a headline claim must be withdrawn or restated before the work goes outside the team. Major means a claim needs correction or a qualifier it does not have. Minor means it is wrong but does not move a conclusion.

Close with two short lists: claims that should be withdrawn, and claims that should be retained but qualified, with the qualifier you would add.

## 8. Calibration rules

- Separate what the artifacts show from what you infer. Mark inferences as inferences.
- Distinguish a defect in the work from a limitation the authors already disclosed. Check the limitations sections before raising something as new.
- If you cannot verify a number, that is a finding of unverifiability, not a finding of error. Do not imply wrongdoing where you have only absence.
- Where you disagree with a design choice that is nonetheless defensible, say that it is defensible and that you disagree, rather than framing preference as defect.
- Report confidence honestly. A medium-confidence blocking finding is more useful than a high-confidence minor one, and inflating confidence to make a point is the one failure mode that would make this review worthless.
