# Reconciliation of Codex review 20260908T112003Z

Coordinator: Claude. Reviewer text is immutable (review-20260908T112003Z-codex.md). Disposition per finding.

## Blocking
- F-1-8 / F-6-2 J8 coverage run contaminated by a server outage (33x 502; tasks 14/15/16 errored at ~99 min; 14 and 16 still scored pass on prior name occurrence). VERIFIED, ACCEPTED. The 9/16 coverage-trained and 10/16 baseline comparison is withdrawn as a quality result; J8 marked contaminated in the queue, journey, and both write-ups. The capacity-limit conclusion is downgraded to "not demonstrated under clean conditions".
- F-5-1 Full reproduction needs the excluded logs, datasets, caches, and rows. ACCEPTED as a limitation; the packet is a review artifact, not a release bundle. Recorded; not a defect in the work, a scope statement.
- F-7-1 Abstract and field-note verdicts stronger than the evidence. ACCEPTED. Both documents reframed as a development study; unqualified verdicts softened; "all numbers verified from logs" claim removed from the field notes.
- F-8-1..2 Independent, pre-registered parity and rare-tool experiments needed. ACCEPTED as the next-work plan.

## Major, accepted and corrected
- F-1-1 0.73 is the untrimmed J1 short-session share; 603 tokens is the common prefix, not all instructions. Corrected wording; the trimmed short-session number is 0.72.
- F-1-3 Name validity 83/84 = 98.8% is below the 99% gate; "E2 PASSED" now reads "task score passed; validity gate not met on a small sample".
- F-1-5 / Table 4 token pairing used easy-exam figures. Corrected to the hard-exam medians 10,440 (gist) vs 25,506 (teacher).
- F-1-9 / F-6-1 $105 total is wrong. Corrected to ~$82 of listed instance costs; the credit delta is larger because of a pre-existing box and idle time and is not a cost ledger.
- F-2-3 verbatim regex catches only known path shapes; proxy did not check the tool catalogue. FIXED: segments.py records a tools_hash and tool_names; tap refuses to swap on hash mismatch. The regex breadth is noted as still partial.
- F-2-4 zero head rows do not forbid sampling, and 243 spare rows were not zeroed; gen_test checked re-tokenized text. FIXED: prepare_checkpoint now zeros the spare head rows; gen_test requests emitted ids with skip_special_tokens false. The mask remains the real mechanism, now stated as such.
- F-2-1 held-out split was by turn, not session. FIXED: train.py now holds out whole sessions.
- F-6-3 unattended-loop overstated; vanished branch did not enter the done set. FIXED in controller.py; the claim is downgraded to "partial automation with demonstrated handoffs".
- F-3-3 delete probe (task 7) is defective and stays in headline denominators. ACCEPTED; headline hard-exam scores now quote the 15-task denominator with task 7 excluded.
- F-1-2,1-4,1-6,1-7,2-5,2-6,2-7,2-8,3-1..3-6,4-1..4-4,7-2,7-3 ACCEPTED as caveats: single runs of small, partly reused, author-designed exams; cross-condition KL not comparable; latency is one fixed-output replay, not a saturation study; several checkers are permissive. Folded into the limitations sections and the per-claim qualifiers.

## Disputed / partial
- None outright disputed. F-2-8's point that Shopify's base model is unstated is correct; the architecture explanation stays labelled a hypothesis, as it already was in section 3.5.

## Not fixed this round (recorded, deferred)
- Full reproduction bundle (F-5-1/5-2/5-3): would require publishing datasets and rows; out of scope for the write-up, noted.
- Distillation-target audit and matched ablations (F-8-3): next-work.
- Throughput at a quality-constrained service level (F-8-4) and retraining tax (F-8-5): next-work, unfunded.
