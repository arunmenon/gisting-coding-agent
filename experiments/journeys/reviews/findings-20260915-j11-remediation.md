# Remediation work order: J11 result and the corrections it forces

- issued: 2026-09-15
- to: reviewer agent (Codex), acting as editor on the five write-ups
- from: program coordinator
- source of truth for this order: `experiments/journeys/j11-conn/log.md` and the eight raw run files under `experiments/journeys/j11-conn/results/`
- prior review being remediated: `experiments/journeys/reviews/review-20260915T073918Z-codex.md`, finding F-4-1
- repository state when this was written: commit `dc5063d`

## 0. What you are being asked to do

Apply the corrections in sections 3 to 9 to the program's write-ups. This is an editing
task with a factual basis, not a fresh review. Do not soften a correction because it is
unflattering, and do not extend a correction beyond what section 2 establishes.

Three standing constraints on every edit:

- **No em dashes anywhere.** House rule, absolute.
- **A number that is measured and a number that is inferred must be distinguishable in the
  sentence that carries them.**
- **Do not repair a claim by weakening its wording while keeping its structure.** Where this
  order says withdraw, the sentence comes out, and what replaces it says what was actually
  measured.

Where an edit changes a source file, the built artifact must be rebuilt from it. Build
commands are in section 10.

## 1. Background in one paragraph

Finding F-4-1 of the 2026-09-15 review held that the load generator used
`aiohttp.ClientSession()` with library defaults, which cap simultaneous connections at 100,
and that this, not the hardware, produced the J10 B5 observation of exactly 100 resident
sequences in both arms on the H200. The paper had built its serving mechanism on that
observation. J11 tested it directly: same card class, same server configuration, same 8:1
checkpoint, both arms, 128 and 256 offered sessions, with the client cap set explicitly to
100 and then to 512. The finding is confirmed.

## 2. What J11 establishes, and the exact numbers you may use

All eight runs completed with zero request errors. One run per cell, no repeats. Full table
in `experiments/journeys/j11-conn/log.md` section 6.

**2.1 Confirmed, decisive.** At client cap 100, maximum resident sequences is exactly 100 in
all four cells, in both arms, at both 128 and 256 offered sessions. At cap 512 it is 123
(full, 128), 126 (full, 256), 128 (gist, 128), 137 (gist, 256). The 100-sequence ceiling is
an artifact of the load generator.

**2.2 Confirmed.** Under the cap, KV cache maxima were 0.822 to 0.955 with zero preemptions,
meaning the engine had spare capacity it was never offered work for. With the cap lifted,
KV maxima are 0.973 to 0.999 and preemptions appear (12, 16, 0, 38). The binding constraint
is KV cache saturation, which depends on prompt length.

**2.3 Observed, single run per cell.** At 256 offered sessions the gist held 137 resident
against the full prompt's 126. Direction is observed; magnitude is not established.

**2.4 Confirmed, and it cuts against us.** Lifting the cap reduced throughput in three of
four cells: full 128 sessions 59.67 to 47.00 rpm (-21%), full 256 sessions 67.33 to 46.33
(-31%), gist 256 sessions 88.33 to 56.67 (-36%). Only gist at 128 sessions rose, 74.00 to
80.67 (+9%). The cap was acting as accidental admission control and was keeping the engine
off the preemption cliff. **Therefore J10's high-concurrency numbers are not uniformly
understated by the cap; in most cells the cap flattered throughput.** Any sentence implying
the corrected numbers are simply better than reported is wrong.

**2.5 Confirmed.** The arm ratio moves with the cap. Gist over full is 1.24 and 1.31 at cap
100, and 1.72 and 1.22 at cap 512. A high-concurrency ratio measured under the cap is not a
conservative version of the uncapped one.

**2.6 Newly surfaced, uncontrolled in both J10 and J11.** Prefix cache hit rate is
persistently asymmetric between arms across all eight runs: full 0.791 to 0.840, gist 0.580
to 0.626. The full prompt shares substantially more cached prefix than the gist does. This
favours the full arm, was not controlled for in any journey, and complicates every
arm-to-arm throughput comparison in the program. It must be disclosed, not resolved by
argument.

**2.7 Unaffected by this defect.** The J10 headline peak figures were measured at 16 and 32
concurrent sessions, far below the 100-connection cap, so the cap could not bind there. The
+43.75 percent peak arithmetic, the cache ablation at 4, 8 and 16 sessions, and the
open-loop measurement at 9 to 72 requests per minute are not invalidated by F-4-1. They
remain subject to every other finding in the 2026-09-15 review, which this order does not
address.

**2.8 Scope limit.** J11 measured one hardware class, two concurrencies, one run per cell,
no quality measurement. The J10 H100 residency probe (54 full, 66 gist, KV at 100 percent)
sat below the cap and its residency numbers survive; the interpretation built on it does not.

## 3. Paper: `paper/build_neurips.py`

### 3.1 Withdraw the mechanism paragraph. Blocking.

Line 179, the paragraph beginning `<p><b>Where the capacity comes from.</b>`. The claims
that the H200 "kept exactly 100 resident in both arms", that "the resident-session ceiling
on this hybrid model is therefore set by the recurrent-state cache", and that "the gist
raises throughput mainly by faster turnover per session" are all withdrawn.

Replace the paragraph with one that reports, in this order: that the original H200 residency
probe was invalidated by a client connection limit in our own load generator; that a
dedicated follow-up with the limit removed found residency of 123 to 137 rather than 100,
with the KV cache at 97 to 99.9 percent and preemptions present; that the binding constraint
is therefore KV saturation, which depends on prompt length; that the gist held 137 resident
against the full prompt's 126 in a single run at 256 offered sessions; and that lifting the
limit reduced throughput in three of four cells, so the limit had been acting as admission
control and the earlier high-concurrency figures are not uniformly conservative. State that
the mechanism is now reported as observed rather than explained.

### 3.2 Correct the architecture-consequence paragraph. Blocking.

Line 191, the paragraph beginning `<p><b>Architecture and headroom, not prompt length alone,
set the benefit.</b>`. The sentence asserting that "the resident-session ceiling is set by
the recurrent-state cache, whose cost per sequence is independent of prompt length, so a
shorter prompt does not let many more sessions fit; it lets each session finish sooner" is
contradicted by J11 and must come out.

The layer-mix description itself (16 of 64 layers full attention) is unaffected and stays.
Recast the paragraph so the layer mix is an expectation recorded before measurement that the
benchmark did **not** confirm as a residency mechanism. Keep the observations that survive:
the gain is throughput rather than single-request latency, it is largest where memory is
tight, and it survives removal of prefix caching.

### 3.3 Correct the conclusion. Blocking.

Line 212. Remove the clause "with the resident-session ceiling set by the recurrent-state
cache rather than by prompt length". Do not replace it with a different mechanism claim. The
surrounding sentence about sustained request rate and peak throughput stays, subject to 3.5.

### 3.4 Correct the benchmark run count and add the sixth measurement. Major.

Line 159. "All 201 runs completed without error" is wrong on two counts: the reviewer
recomputed 202 archived J10 runs, and J11 adds 8 more. State the J10 count as verified by
the reviewer, and describe J11 as a separate follow-up with its own count rather than
folding it into the same total. The list of measurements in that paragraph should gain the
connection-limit control as a fifth item, described as a correction to the fourth.

### 3.5 Qualify the key callout. Major.

Line 158, the `div class="key"` block. The 2x and 44 percent figures may stay, per 2.7, but
the callout currently reads as a settled deployment result. Add, inside the callout, that
these are finite-window replay measurements on one hardware class and that the mechanism
behind them is not established. Do not bury this in a later paragraph.

### 3.6 Add the prefix-hit asymmetry to limitations. Major.

Section 7 of the paper. Add the 2.6 disclosure as a limitation in its own right: the two
arms do not receive equal benefit from prefix caching, the asymmetry is persistent and
large, it favours the full-prompt arm, and it was not controlled for in any measurement in
the program.

### 3.7 Add J11 to the compute appendix. Minor.

Table 7 gains a row: J11, 1.15 GPU-hours, H200 NVL, including the aborted first instance.

### 3.8 Figure 9 caption. Major.

Line 160. The caption describes the full prompt collapsing "beyond 32 sessions as its KV
cache fills". The figure's high-concurrency region was measured through the capped client.
Either restrict the plotted range to concurrencies at or below 64, or mark the region above
64 as client-limited in both the figure and the caption. State in the caption which choice
was made.

## 4. Deck: `paper/build_deck.py`

Line 224, the mechanism slide caption asserting "at the resident-session ceiling both arms
hold the same number of sessions; the gist just turns them over faster (H200: 85 vs 50
req/min at 100 resident)". Withdraw it. The slide's layer diagram may stay if its caption is
recast as architecture description without the residency claim.

If the deck retains a mechanism slide at all, it must say that the mechanism is not
established and that the measured effect is a throughput difference whose cause is under
investigation. A deck slide that quietly drops the claim while keeping the confident visual
framing does not satisfy this order.

## 5. Deck export: `paper/build_pptx.py`

Line 175 carries the same caption as section 4. Apply the same correction. The HTML deck and
the PowerPoint must not diverge.

## 6. CTO note: `cto-note.md`

### 6.1 Withdraw the turnover bullet. Blocking.

Line 34, the bullet beginning "**The mechanism is turnover, not headcount.**" Every clause
of it is now contradicted, including the closing claim that it "is a better story for us
than the one we had". Replace it with an honest statement: we reported a mechanism, an
external review identified a measurement defect in our own load generator, we tested it, and
the mechanism claim did not survive. Say what the corrected picture is: the gist holds more
sessions before the memory fills, and the advantage depends on how close to full the memory
is.

This note is addressed to a CTO who was asked to fund work on the strength of that bullet.
The correction should be findable by that reader, not folded into a caveat.

### 6.2 Correct the experiment list. Major.

Line 17, item 5, "Where the ceiling actually is", claims we instrumented residency "to
explain the mechanism instead of asserting it". The instrumentation was defective. Correct
the item and add a sixth item describing the follow-up.

### 6.3 The cost table is separately wrong. Blocking, and not a J11 finding.

The per-dollar table uses a quoted rate for one card and an effective rate for the other.
Review finding F-5-2 and its claim-10 entry give the correct figures on a consistent quoted
basis: 16.16, 23.23, 23.38, 22.83 requests per minute per dollar-hour. On that basis the
more expensive card running the full prompt slightly exceeds the cheaper card running the
gist, which inverts the note's central argument. The section headed "Why this is a cost
lever" must be rewritten to match the arithmetic or removed. Do not present the cheaper-card
substitution as established.

## 7. Email note: `email-note.md`

No residency claim appears in this file, but its throughput bullet inherits the
qualifications in 2.4, 2.5 and 3.5, and its cost bullet inherits 6.3. Apply both.

## 8. README: `README.md`

Line 24 states "the resident-session ceiling is the recurrent-state cache, so the gist wins
by turnover, not by fitting more sessions". Withdraw that clause. Replace with the corrected
mechanism status and a pointer to `experiments/journeys/j11-conn/`.

## 9. What must not change

Do not alter the J10 raw run files, `capacity_report.json`, any journey log, or the checked
in review text. Corrections belong in the write-ups and in new journey records. The
historical record of what we believed and when is itself evidence.

Do not remove the +43.75 percent or 2x figures on the strength of this order alone. F-4-1
does not reach them. They carry their own qualifications from the 2026-09-15 review, which
remain open and are outside this work order.

## 10. Build and verification

```
cd paper
python3 build_neurips.py          # writes gisting-neurips.html
python3 build_deck.py             # writes gisting-cto-deck.html
python3 build_pptx.py             # writes Gisting-CTO-deck.pptx
python3 build_docx.py             # writes Gisting-NeurIPS-paper.docx from the HTML
```

Then verify, and report the result of each check:

1. Zero em dashes in every generated file.
2. No occurrence of "turnover", "recurrent-state cache" as a ceiling mechanism, or "100
   resident" as a hardware property, in any of the five write-ups.
3. The paper's table and figure numbering is still contiguous after edits, and every
   in-text reference resolves.
4. The HTML deck and the PowerPoint carry the same corrected caption.
5. The docx rebuild reports the same image and table counts as the HTML.

## 11. Output expected from you

A short report stating, per item in sections 3 to 8: applied, applied with deviation, or not
applied, with the reason in one sentence for anything other than applied. Then the results of
the five verification checks. Then, separately, anything you found while editing that this
order got wrong.
