W-1: closed. In-memory reproductions recover crashes before and after provisioning without duplicate resources (`steno/loop/runner.py:217`).
W-2: partly closed. Execution exceptions trigger cleanup, but a reproduced inspection exception still escapes and leaves a live resource (`steno/loop/runner.py:258`).
W-3: closed. Reproducing both destroy failures, clearing them, and resuming now confirms destruction (`steno/loop/runner.py:529`).
W-4: closed. Failed sync records artifact loss, and resuming after destruction cannot manufacture successful verification (`steno/loop/runner.py:518`, `steno/loop/backend.py:206`).
W-5: closed. The failed-span reproduction retains its failure reason after resume, and CLI success requires successful work (`steno/loop/runner.py:576`, `steno/loop/cli.py:68`).
W-6: partly closed. Unique IDs and changed-input rejection work, but identity hashes the pair path rather than its contents, and ownership remains racy (`steno/loop/spec.py:92`, `steno/loop/state.py:96`).
W-7: closed. Reproducing interrupted preflight now reruns validation and rejects missing credit before provisioning (`steno/loop/runner.py:363`).
W-8: partly closed. Missing prerequisites are rejected, but recognized gates remain accepted without evaluation or inclusion in stage plans (`steno/loop/spec.py:136`, `steno/loop/runner.py:456`).
W-9: closed. The restart reproduction respects the persisted attempt limit and does not execute another attempt (`steno/loop/runner.py:432`).
W-10: closed. The ordinary-request-plus-`messages:[null]` reproduction records the parse failure and returns CLI exit code 1 (`steno/span/cli.py:68`).
W-11: closed. The adjacent protected-line reproduction now passes with zero unresolved ranges (`steno/span/analysis.py:182`).
W-12: closed. Identical protected preambles now produce zero fixed lines and retain protected classification (`steno/span/analysis.py:178`).
W-13: partly closed. Frozen-map validation rejects changed fixed instructions, but accepts arbitrary text where discovery left unresolved lines, as reproduced in N-1 (`steno/span/analysis.py:263`).
W-14: partly closed. Strict tool semantics and output format survive the original reproduction, but unconsumed message-level fields still disappear (`steno/span/adapters/claude_code.py:175`).
W-15: partly closed. Signature and error events now survive reproduction, but a truncated stream still reports `incomplete=False` (`steno/span/adapters/claude_code.py:252`).
W-16: partly closed. Separate manifests require rendering hashes and accept empty collections, while proxy/dataset enforcement is explicitly deferred (`steno/span/manifest.py:176`, `steno/span/README.md:46`).
W-17: partly closed. Session/path sanitization improved, but comparison against the source still finds an original device identifier (`tests/span/fixtures/claude_code_captures.jsonl:1`).
W-18: closed. The fixture scan now finds zero em dashes, with fixture and source hygiene checks passing (`tests/span/test_fixture_hygiene.py:97`).

N-1: Frozen-map validation ignores unresolved classifications, so a failed discovery map validates fresh arbitrary instructions successfully. Severity: major. File: `steno/span/analysis.py:263`.
N-2: The new lock uses non-atomic existence checking followed by truncating creation; an in-memory concurrent reproduction accepted both owners, permitting competing lifecycle operations. Severity: major. File: `steno/loop/state.py:96`.

Commit wave 1: no, because resource leakage, ignored gates, canonical data loss, identifier leakage, and new validation/locking defects remain.
