# J11 correction pass: Codex completion report

Date: 2026-09-15. Starting commit: `9d3468e`.

Scope: apply the J11 work order and its separate quoted-price correction to the write-ups and rebuild their exports. This is not a new performance review or a closure of the second review's other findings.

## Outcome in plain language

The previous explanation mistook a limit in our testing tool for a limit in the hardware. That explanation is withdrawn prominently in the paper, both deck formats, the CTO note and README. Removing the testing limit usually reduced completed work, so the old high-load results cannot be described as conservative estimates.

The corrected price comparison also removes the claimed case for replacing the more expensive card with the cheaper card plus gisting. At the quoted prices, their measured output per rental dollar is nearly equal, with the more expensive card running the full prompt slightly ahead. Neither result establishes cost per correctly completed coding task.

The +43.75 percent peak difference and 2x target-rate result remain, with qualifications. J11 did not test or invalidate those lower-load measurements. Fair tuning, measurement duration, common response-time requirements and quality under load remain open issues from the second review.

## Item dispositions

| Work-order item | Status | Result or reason for deviation |
|---|---|---|
| 3.1 Paper mechanism paragraph | Applied with deviation | Withdrew the old explanation and reported all four throughput changes; near-full cache and preemptions are described as evidence consistent with memory pressure, not proof of a uniquely established replacement mechanism. |
| 3.2 Architecture paragraph | Applied | Kept the 16/64 layer description, distinguished the prior expectation from the measurements, and retained the surviving throughput observations. |
| 3.3 Conclusion | Applied | Removed the residency mechanism and made the J11 withdrawal and corrected cost conclusion explicit. |
| 3.4 Run count and follow-up | Applied with deviation | Used 202 archived J10 runs plus eight separate J11 runs; followed the item's body in making the follow-up the fifth measurement, rather than its contradictory heading saying sixth. |
| 3.5 Key callout | Applied | Preserved the two headline figures and added finite-window, fixed-output, hardware and unresolved-mechanism qualifications inside the callout. |
| 3.6 Prefix-cache limitation | Applied with deviation | Disclosed the persistent full/gist hit-rate difference and lack of control; distinguished the higher cached fraction from an unmeasured net effect on the throughput comparison. |
| 3.7 Compute appendix | Applied | Added J11, H200 NVL, 1.15 GPU-hours, including the aborted first instance. |
| 3.8 Figure 9 | Applied | Retained the existing 1-64 range, stated that choice in the caption, and removed the unsupported causal framing from the figure and caption. |
| 4 HTML deck | Applied | Replaced the mechanism slide with a prominent correction and an architecture-only diagram caption; changed the summary and funding framing accordingly. |
| 5 PowerPoint deck | Applied | Used the same correction and exact caption as the HTML deck; rebuilt all 14 slides. |
| 6.1 CTO mechanism correction | Applied with deviation | Made the withdrawal prominent and reported 137 versus 126 as single-run sampled maxima under heavy load, rather than claiming those counts were reached before memory filled. |
| 6.2 CTO experiment list | Applied | Corrected the original probe and added the connection-limit follow-up as item six, grouping the hardware comparison with the related measurement. |
| 6.3 CTO cost section | Applied | Replaced the central argument with consistent quoted-price arithmetic and no established cheaper-card substitution; propagated the same correction to the other write-ups to avoid contradictions. |
| 7 Email note | Applied | Corrected the throughput and cost bullets, including the direction of the cap effect, changing ratios and unresolved deployment value. |
| 8 README | Applied | Withdrew the mechanism, linked J11, corrected the price comparison, and preserved the qualified lower-load figures. |

No item was left unapplied. All changes are in the working tree; no commit or external communication was made.

## Arithmetic checked against the run files

J11 request throughput uses successful requests whose start falls in the measurement window, divided by its three-minute duration. It is not a count restricted to requests finishing inside that window.

| Prompt and offered concurrency | Cap 100 | Cap 512 | Change |
|---|---:|---:|---:|
| Full, 128 | 179 / 3 = 59.67 | 141 / 3 = 47.00 | -21.23% |
| Full, 256 | 202 / 3 = 67.33 | 139 / 3 = 46.33 | -31.19% |
| Gist, 128 | 222 / 3 = 74.00 | 242 / 3 = 80.67 | +9.01% |
| Gist, 256 | 265 / 3 = 88.33 | 170 / 3 = 56.67 | -35.85% |

Gist/full ratios are `222/179 = 1.240`, `265/202 = 1.312`, `242/141 = 1.716`, and `170/139 = 1.223`, respectively by cap then concurrency. Engine samples support maximum running counts of 100 in every capped run and 123, 126, 128 and 137 in the uncapped full-128, full-256, gist-128 and gist-256 runs. These are sampled maxima, not exact sustainable ceilings.

Consistent quoted-price arithmetic, using unrounded peak replay rates:

- H100 full: `42.6667 / 2.64 = 16.16`.
- H100 gist: `61.3333 / 2.64 = 23.23`.
- H200 full: `85.3333 / 3.65 = 23.38`.
- H200 gist: `83.3333 / 3.65 = 22.83`.

These units are requests per minute divided by dollars per hour. The ranking reverses the earlier mixed-price comparison; the small difference does not establish a practical hardware winner.

## Five required verification checks

1. **Pass: zero em dashes.** Checked decoded HTML, notes, READMEs and every XML part of the generated DOCX and PPTX. The rebuilt serving figure was also inspected.
2. **Pass: withdrawn mechanism absent.** No `turnover` or `100 resident` wording remains in the write-ups or export text. The paper retains a historical account of a recurrent-state-cache allocation failure at startup in Section 4.1; it is not used to explain the J10 residency ceiling.
3. **Pass: numbering and references.** Figures 1-9 and Tables 1-7 are contiguous. All figure, table, section and numbered bibliography references resolve. The paper has one additional unnumbered overview table. Fixed a pre-existing DOCX list-continuation defect so bibliography numbering restarts at 1.
4. **Pass: identical corrected caption.** The HTML deck caption exactly matches a text node in the PowerPoint export.
5. **Pass: image and table counts.** The DOCX builder reports nine images and eight tables, matching the HTML; assertions enforce both counts.

Additional checks: all modified Python builders parse; `git diff --check` passes; the editable PowerPoint retains 14 slides. Historical raw runs, capacity reports, journey logs and checked-in review text are unchanged.

### Export and visual checks

Rebuilt both root HTML files, the editable PowerPoint, the Word document, the serving PNG and its embedded figure data. Removed stale scratch-directory assumptions from the builders and documented the correct build order. Only the serving PNG changed among the existing figure images.

Inspected all 14 slides through a Keynote PDF render and all 20 paper pages through a Pages PDF render. The corrected deck slide and cost slide have no clipping or overlap. The paper inspection found bibliography numbering continuing from an earlier list and a split table without a repeated header. Both were fixed in the DOCX builder; the final DOCX was rebuilt and its independent reference numbers and eight repeated-header markers were checked directly.

**Visual-check limitation:** the final paper render after those two formatting fixes could not be exported reliably because native Pages automation returned window/frame errors and a closed-pipe error. Thus the paper's substantive content was visually checked, while those last formatting fixes have structural verification only. The deck render used Keynote, which reported missing fonts; it is not verification in native PowerPoint. The canonical document renderer was unavailable because its `pdf2image` dependency was missing. Temporary previews are under `/private/tmp/gisting-j11-qa/` and are not published artifacts.

## What the work order or its supporting log gets wrong

1. **The replacement explanation is too certain.** Sections 2.2 and 3.1 call cache saturation the established binding mechanism. The samples show almost-full cache and preemptions, and conclusively disprove the old 100-request ceiling. They do not isolate allocation policy, establish a precise replacement ceiling, or explain all throughput differences. The edits preserve that distinction.
2. **The CTO replacement sentence overstates the measurement.** Section 6.1 says the gist holds more sessions before memory fills. The 137/126 comparison is a pair of sampled maxima from overloaded runs, with almost-full cache and preemptions in both. It is not a measurement of how many sessions can be sustained before memory fills.
3. **A higher cache-hit fraction is not a measured throughput correction.** Full prompt has the higher fraction; prompt lengths and completed request populations also differ. The asymmetry needs disclosure, but its net effect cannot be calculated from hit fractions alone.
4. **The paper measurement count is internally inconsistent in the order.** Section 3.4's heading says sixth and its body says fifth. The existing paper listed four measurements, so the corrected paper lists five. The CTO list is organized separately into six items.
5. **Figure 9 already stops at 64.** No plotted high-load points needed removal. Its causal framing and disclosure still needed correction.
6. **The supporting log reverses the run-order argument.** It says running all cap-100 conditions before cap-512 conditions prevents a time trend from favouring one cap. That ordering can confound cap with time and cache history; the paper now discloses the order as a limitation.

The work order and original log remain unchanged as historical records. The other findings from the second review remain open; this report does not certify the full paper or deck as publication-ready.
