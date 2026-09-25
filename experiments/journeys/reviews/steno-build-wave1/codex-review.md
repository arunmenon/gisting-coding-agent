Do not commit this as wave 1 yet: provisioning recovery, cleanup reconciliation, fail-open validation, canonical data loss, and fixture sanitisation need fixes first. Choices 1 and 2 are consistent with the design; choice 3 is acceptable in principle but incorrectly implemented, and choice 4 reproduces on real data. Choice 5 needs persisted, separate work and cleanup outcomes; choice 6 is acceptable only as explicitly restricted scaffolding, with unsupported checks failing closed.

W-1: A provisioning crash can strand a live resource without a recorded provider ID. Severity: blocking. File: `steno/loop/runner.py:120`.

The runner persists `provisioning` before calling the provider, but rejects that state on restart when `backend_resource_id` is absent. A crash after provider creation and before the `ready` save therefore produces `RuntimeError: inconsistent state`, even though the persisted idempotency key could recover the resource. I reproduced this with a live fake resource. Fix: reconcile or repeat idempotent provisioning from this state, then persist the returned ID before cost queries or ledger operations. Test crashes on both sides of the provider call; the existing restart test crashes later, inside a stage.

W-2: Ordinary backend exceptions bypass teardown. Severity: blocking. File: `steno/loop/runner.py:284`.

An exception from execution, transfer, cost lookup, or ledger writing exits before cleanup. The existing crashing-stage test actually demonstrates this, then relies on somebody restarting the runner. Fix: persist typed failure information and enter exception-safe cleanup once ownership is established, preserving unresolved resources for reconciliation. Hard process termination still requires restart recovery; caught operational failures should not require manual intervention.

W-3: An unknown destroy result permanently disables cleanup reconciliation. Severity: blocking. File: `steno/loop/runner.py:327`.

Set `fail_destroy=True` and `fail_destroy_confirmation=True`, run once, clear both flags, and resume. The resource remains alive in `destroy_unknown`; the runner never retries destruction or confirmation. `tests/loop/test_state.py` explicitly requires this broken terminal behavior. Fix: make unknown destruction recoverable, inspect the provider on resume, retry as appropriate, and transition to confirmed only on provider evidence.

W-4: Failed sync destroys artifacts regardless of policy, and the fake backend conceals the loss. Severity: major. File: `steno/loop/runner.py:304`.

`artifacts.emergency_policy` is ignored and destruction always follows failed transfer. With a nonempty output manifest, `fail_sync=True` destroys the resource; clearing the flag and resuming then reports completion because `FakeBackend.transfer()` returns the requested manifest even for destroyed resources. Fix: enforce an explicit emergency policy, persist artifact loss when termination is required, and prevent post-destruction transfer from manufacturing verification. Make the fake backend model resource existence and actual stored artifacts.

W-5: Work failure disappears from the returned outcome after restart. Severity: major. File: `steno/loop/runner.py:246`.

A failed span produces `completed=True` with an abort reason initially; resuming produces `completed=True, abort_reason=None`. Stage failure details remain in state, but the advertised summary loses them. Choice 5 does not itself falsely confirm teardown, but it is unsafe as the sole completion signal. Fix: persist separate work outcome and cleanup status, reconstruct failure reasons on resume, and make success exit codes depend on work success as well as cleanup.

W-6: Run identity permits resource sharing and reuse across incompatible specs. Severity: major. File: `steno/loop/runner.py:201`.

The default run ID comes from the pair filename, so separate runs of the same pair share the provider key `<pair>:compute`. An idempotent backend can return one run’s resource to another. Conversely, an existing run directory accepts changed inputs, gates, pair, or stages and skips previously successful stages without identity verification. Fix: persist a unique run ID and immutable spec/pair/input digests, reject incompatible resumes, and enforce one active owner per run directory.

W-7: Interrupted preflight is treated as completed preflight. Severity: major. File: `steno/loop/runner.py:223`.

Only `pending` preflight executes validation; `running` falls through to provisioning. A restart after saving `running` but before completing validation bypasses all preflight checks. Fix: rerun idempotent preflight from `running`, and allow provisioning only after persisted preflight success.

W-8: Required span and preflight contracts silently become optional. Severity: major. File: `steno/loop/spec.py:89`.

`stages=["train"]` validates, a nonexistent pair path is accepted, and any nonempty inputs dictionary satisfies preflight. Missing credit defaults to sufficient credit. Gates are neither evaluated nor included in the stage plan, and absent executors become successful no-ops under the fake backend. Fix: require span before dependent work, validate pinned pair and required inputs, and reject unsupported gates or missing executors outside an explicit dry-run mode. A Vast stub is a valid B6 deferral; silently passing missing B5 checks is not.

W-9: Restart retries bypass the configured attempt limit. Severity: major. File: `steno/loop/runner.py:275`.

Every restart reruns a `running` stage without persisting an attempt count or applying `max_attempts_per_stage`. A stage that performs work and then crashes can repeat indefinitely, even with a limit of one. Fix: persist an attempt ID and counter before execution, reconcile existing work where possible, and stop when the configured limit is reached. Deferring automatic failure triage does not justify unbounded restart retries.

W-10: Parse failures are excluded from the all-call gate. Severity: major. File: `steno/span/cli.py:35`.

One ordinary request plus a selected request containing `messages:[null]` yields `skipped=1` and report `pass=True`; the CLI exits successfully. The JSON report does not record the skipped request. Fix: account for every selected capture with provenance and an explicit parse/unsupported outcome, and fail the all-call gate on unexplained exclusions.

W-11: Adjacent protected lines falsely fail invariance. Severity: major. File: `steno/span/analysis.py:106`.

Two calls containing `working directory /a\nDate: 2026-01-01` and `working directory /b\nDate: 2026-01-02` fail with one unresolved range, although both lines match the declared rule. Contiguous differences are merged, then rule matching is disabled for ranges longer than one line. Those ranges also use `None` for session classification, hiding within-session variation. Fix: retain aligned per-call ranges and evaluate every constituent line before aggregating classifications.

W-12: Declared protected values become compressible when constant in the sample. Severity: major. File: `steno/span/analysis.py:140`.

Two identical `working directory /a` preambles pass with one fixed line and zero protected ranges. Rules are applied only to observed differences, contradicting their contract that these values must remain raw. Fix: classify declared protected values before fixed-span discovery, even in singleton or identical captures, and exclude them from fixed/compressible counts.

W-13: Discovery is presented as validation without checking a proposed segment map. Severity: major. File: `steno/span/analysis.py:222`.

`build_report()` derives its baseline from the calls being checked and has no proposed-map input. Running it on a fresh singleton with arbitrary changed instructions always passes; it cannot establish compatibility with an earlier discovered bundle, ordering, or rewritten raw-value preservation. Fix: separate discovery from validation against a frozen, identified segment map; report insufficient evidence separately from validated compatibility.

The reported real-data result itself is reproducible: 43 calls, six cohorts, 15 unresolved ranges, overall failure. The unresolved excerpts are changing `<total_tokens>` values in inline system messages, with successive cohorts contributing one through five ranges. That supports choice 4; it does not validate the checker’s other cases.

W-14: The canonical record silently loses nested request semantics. Severity: major. File: `steno/span/adapters/claude_code.py:291`.

Whole containers are marked known while only selected children are retained. For example, tool `strict:true` and `output_config.format` disappear from the canonical record and `unsupported`; tool behavior can change without changing `catalogue_hash()`. Other losses include metadata beyond session identity and unhandled system content. Fix: preserve unconsumed nested fields with source locations, include tool semantics in catalogue identity, and explicitly mark unsupported rendering cases.

The unchanged-preamble rewrite is broader than the fixture: it copies the original request and replaces extracted text in place, and a constructed request with image content, empty system blocks, and extra fields round-tripped structurally. This proves semantic request equality, not lossless canonicalisation or byte-for-byte wire reproduction; original JSON bytes are not retained.

W-15: Streaming decoding drops errors and signed thinking data. Severity: major. File: `steno/span/adapters/claude_code.py:217`.

A stream containing `signature_delta` followed by an `error` event returns an ordinary partial reply with neither the signature nor the error. `parse_request()` also only handles dictionary responses instead of routing supported response representations through its decoder. Fix: preserve signature and unknown events, expose typed incomplete/error outcomes, and add streaming, truncation, and error fixtures. Porting existing loss does not satisfy the new fragments-and-errors contract.

W-16: The manifest does not implement mandatory B3 bundle identity. Severity: major. File: `steno/span/manifest.py:25`.

Tokenizer and template hashes are optional, model identity is merely a hash of a name, and no proxy or dataset enforcement exists. Meanwhile, valid empty tool catalogues and empty rule sets are rejected as missing. Fix: distinguish incomplete discovery metadata from a deployable bundle, require pinned rendering identities for deployable validation, and distinguish absent collections from explicitly empty ones. Either implement B3 enforcement or explicitly remove B3 from this wave’s completion claim.

W-17: The sanitised fixture retains original identifying metadata. Severity: blocking. File: `tests/span/fixtures/claude_code_captures.jsonl:1`.

The fixture’s device ID and all three session IDs exactly match the source capture; UUID-bearing local paths also remain. I found no email addresses or the checked credential markers, but the personal-identifier sanitisation claim is false. Fix: consistently replace device, session, request, tool-use, and path identifiers with synthetic values while preserving relationships, then update expected assertions.

W-18: Fixture messages violate the no-em-dash requirement. Severity: minor. File: `tests/span/fixtures/claude_code_captures.jsonl:1`.

The fixture contains 159 U+2014 characters. Fix: replace them in the synthetic fixture and add a scan covering fixture contents as well as Python and Markdown files.

Verification was read-only: 42 span/spec tests passed, with the file-writing spec test deselected. Full lifecycle persistence tests were not rerun under the read-only filesystem; lifecycle reproductions used in-memory persistence mocks. Existing tests miss the provisioning crash window and encode incorrect terminal cleanup behavior; the invariance path test also contains an assertion whose injected-text alternative is always true.

Wave 2 should pick up:

- Qwen rendering/token parity and a fresh, independently validated onboarding capture.
- Local and Vast backends with operation deadlines, independent spend enforcement, incremental durable sync, and restore verification.
- Journey integration, real stage gates, required artifact contracts, and bounded typed failure retries.
- Remaining B3 enforcement if this wave is explicitly rescoped to defer it.
