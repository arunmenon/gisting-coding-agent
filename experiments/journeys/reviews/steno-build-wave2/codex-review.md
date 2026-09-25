Wave 2 is not ready to commit: provisioning, artifact preservation, and bundle enforcement violate required guarantees. Read-only, offline probes reproduced several failures; I did not rerun the filesystem-writing pytest suite or access the real API key. `backend_options` remains opaque to the neutral layer, but flat compute fields leak provider vocabulary and lose constraints. The standalone J11 replay performs no remote work, the lock implementation is unchanged, and no em dashes were found in the reviewed wave-2 files.

X-1: Provisioning can rent twice after an ambiguous create response. Severity: blocking. File: steno/loop/backends/vast.py:183.
The label lookup occurs only before `create_instance`. The installed SDK defaults to three attempts and retries creation PUTs after timeouts, connection errors, and gateway errors without another label lookup. A retry after restart also assumes immediate label visibility. Fix: disable automatic creation retries, persist an uncertain-creation state, and reconcile before permitting another rental; require provider idempotency or stop for unresolved ambiguity. Test “creation accepted, response lost” and delayed visibility.

X-2: Transfer success does not prove artifacts were retrieved or preserved. Severity: blocking. File: steno/loop/backends/vast.py:284.
Both VastBackend and LocalBackend skip copying when `_destination` is absent but return success. The runner supplies only the hash manifest at `runner.py:589`, so it can mark sync verified and destroy the sole artifact copy. Even with a destination, neither backend verifies the copied bytes. The conformance test checks hashes returned by the backend, not destination files. Fix: make the artifact destination explicit, require retrieval, and hash the destination before success; test that artifacts survive teardown.

X-3: Remote commands and artifact paths undergo shell interpretation. Severity: blocking. File: steno/loop/backends/vast.py:272.
An offline probe with path `artifact; echo injected` produced `sha256sum artifact; echo injected 2>/dev/null`. Passing an argv list to local `ssh` also does not preserve remote argument boundaries at line 247. Destination joins additionally permit absolute paths or `..` to escape the artifact directory. Fix: use a structured remote execution/transfer mechanism, or correctly encode remote arguments, and validate destination containment. Test metacharacters, spaces, absolute paths, and traversal.

X-4: A valid bundle does not authenticate the artifacts actually used for compression. Severity: blocking. File: experiments/proxy/tap.py:330.
`--gist` and `--bundle` load independently; `load_gist` discards bundle identity. The dataset builder likewise uses global `SEGMENTS` and `TOKENIZER_DIR` without binding them to the supplied bundle. A matching request can therefore pass enforcement while an unrelated or hashless map supplies gist tokens. Fix: require the actual segment map and rendering artifacts to match the loaded bundle, including adapter identity, and reject legacy maps when enforcement is enabled. Add end-to-end tap and dataset mismatch tests.

X-5: Deleting an unhashed field disables instruction-structure enforcement. Severity: major. File: steno/span/enforce.py:87.
`instruction_structure` is outside `bundle_sha`; omission becomes `[]`, which skips the comparison at line 109. An offline probe changed a rejected request into an accepted request by deleting that field without changing the recorded hash. Fix: include structure in the authenticated identity, require its presence, and compare explicitly even when the expected structure is empty.

X-6: Real backends silently skip the runner’s registered executors. Severity: major. File: steno/loop/backends/vast.py:239.
The runner supplies `{"executor": ..., "inputs": ..., "outputs": {}}`, while VastBackend and LocalBackend only examine `command`. Both returned success without invoking an executor in offline probes. Ungated stages can be marked complete without running; gated stages fail for missing metrics. Fix: define one explicit stage-plan/executor contract shared by runner and backends, reject missing work, and test through `run()` rather than only calling backend methods directly.

X-7: Raw SDK exceptions can carry the API credential beyond the backend. Severity: blocking. File: steno/loop/backends/vast.py:130.
SDK exceptions propagate without sanitization. Using only a synthetic credential, an offline probe confirmed that an SDK `HTTPError` retains it in `error.request.headers["Authorization"]`. Other paths interpolate exception text into results or CLI output. The current key test injects a credential-free double and checks only top-level attribute names. Fix: translate SDK failures into sanitized exceptions/results without retaining original exception objects or chains; test constructor, quote, provision, inspect, and execution failures with a synthetic secret.

X-8: Unknown provider responses can become confirmed destruction. Severity: blocking. File: steno/loop/backends/vast.py:324.
`instances or []` turns `None` into authoritative absence; the offline probe returned `True` for a null lookup. The same normalization in label lookup can permit another rental. `destroy()` also ignores the response body and reports acceptance for any non-throwing response. Fix: validate successful response shapes and completeness before interpreting absence, preserve unknown outcomes, and validate destroy acknowledgements. Test null, malformed, and rejected responses, not only raised exceptions.

X-9: LocalBackend loses resource identity across restart and confirms deletion without evidence. Severity: major. File: steno/loop/backends/local.py:51.
Both resource and idempotency registries exist only in memory. Reconstructing the backend over the same root cannot recover an existing resource, can create another directory for the same key, and reports unknown resources destroyed. `rmtree(ignore_errors=True)` also marks deletion successful when files remain. Fix: persist resource/key metadata, reconcile directories on restart, and confirm actual removal. Add fresh-backend restart and deletion-failure tests.

X-10: J11 substitutes checkpoint composition for the span gate’s evidence. Severity: major. File: steno/loop/executors/j11.py:101.
The reported `share=0.9852297903766404` measures segment-map composition, not measured static-span share or invariance. It passed a `share_min=0.9` gate in an offline probe, despite the program’s stated measured share being 0.72. The current 0.5 threshold does not make these metrics interchangeable. Fix: expose checkpoint composition under a separate metric and require a provenance-bearing span report for `share`; fail closed when that evidence is unavailable.

X-11: The shipped flat J11 compute form silently drops its GPU constraints. Severity: major. File: steno/loop/examples/j11-conn.json:29.
`gpu_query` embeds Vast vocabulary outside the provider module, but VastBackend constructs its request only from `compute.request` and never consumes `gpu_query`. J11’s H200, GPU-count, reliability, and disk requirements therefore disappear during quoting/provisioning. Fix: migrate this spec to neutral request fields and opaque provider options; reject or explicitly translate supported legacy fields rather than silently ignoring them.

X-12: Quotes do not honor all resource and price constraints. Severity: major. File: steno/loop/backends/vast.py:92.
`cpu_ram_gb_min` is never translated; a 512-GB request produced only `rentable=true verified=true`. Search also omits the SDK’s storage-pricing argument, whose installed default is 5 GiB, while provisioning may allocate 40 GiB or more. Consequently the hourly-price filter can approve an understated price. Fix: translate all supported constraints, reject unsupported ones, and quote the actual requested storage. Add explicit memory-unit and allocated-disk pricing tests.

X-13: Stage deadlines exclude endpoint resolution and other blocking work. Severity: major. File: steno/loop/backends/vast.py:244.
Endpoint lookup runs before the subprocess timeout begins. The installed SDK can spend multiple 120-second request attempts there, even for a one-second stage deadline. FakeBackend also invokes arbitrary executors without enforcing a timeout; its conformance test merely supplies an executor that returns a timeout-shaped result. Fix: enforce an overall deadline across lookup and execution, propagate remaining time, and test actual blocking operations.

X-14: Credit lookup failure falls back to potentially stale asserted credit. Severity: major. File: steno/loop/runner.py:162.
A backend advertising credit lookup can fail, after which `compute.available_credit` authorizes provisioning anyway. Non-finite returned values such as NaN also evade the less-than comparison. Fix: require finite, valid live credit when the backend supports lookup; reserve explicit credit assertions for backends without that capability. Test lookup failure and non-finite values before any provision call.

X-15: Marker replay accepts incomplete or out-of-order success evidence. Severity: major. File: steno/loop/executors/j11.py:187.
Offline probes accepted `server_up` before `ckpt_built`, and a benchmark containing just one combination with `BENCH_DONE` before its result. Benchmark completion does not require `B6_done`, all eight unique combinations, or one coherent chain invocation. Fix: validate invocation boundaries, marker order, expected combinations, duplicates, and completion markers before returning success.

X-16: The J11 dry run does not evaluate gates or propagate replay failures. Severity: major. File: steno/loop/executors/dryrun.py:92.
When a STATE file exists, the command returns zero regardless of missing required inputs or failed stage results. Gates are printed but never evaluated, so even an impossible benchmark threshold produces no gate failure. Fix: evaluate replay results through the shared gate logic and return nonzero for missing inputs, failed stages, or failed gates. Keep all execution mocked or replay-only.

X-17: The fake backend cannot be constructed through the advertised registry interface. Severity: minor. File: steno/loop/backends/__init__.py:81.
`create_backend("fake")` raises `TypeError` because `FakeBackend` requires a clock, while the registry and quote CLI supply none. The conformance suite constructs it directly and misses this. Fix: register a factory with a default clock while preserving clock injection, and test registry construction plus `quote` for every built-in backend.

Commit wave 2: no, because cloud creation, credential isolation, verified artifact recovery, bundle enforcement, and gate semantics remain unsafe or incomplete.
