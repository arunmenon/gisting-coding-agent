# steno.loop

The Steno run loop (steno-design.md section 2, build order steps 5-6).
`steno run <spec>` is meant to replace the per-journey shell scripts under
`experiments/vast/` and `experiments/loop/` with one declarative entry point.

Wave 1 implemented the spec, the persisted lifecycle, the compute backend
protocol with a fake backend for tests, the runner, the ledger and a small
CLI, all local: no network, no GPU, no vast.ai calls happened anywhere in
that wave. Revised after a Codex review (steno-build-wave1) found blocking
and major gaps in the first draft; see "Fixed in this revision" below.

Wave 2 (this revision) makes the runner and spec fully provider-neutral (see
"Compute backends" below), adds a backend registry, formalises the
`ComputeBackend` contract, and implements two real backends: `local`
(subprocess-based, still no network) and `vast` (the real vast.ai SDK). The
CLI's `quote` command and the live test file are the only things in this
package that can make a real vast.ai API call, and both are read-only
(`search_offers`, `show_user`); nothing in `steno/loop` ever calls
`create_instance` or `destroy_instance` except `VastBackend.provision()`/
`destroy()` themselves, which only run when a caller explicitly drives a real
run against the `vast` backend.

## What it does

`steno.loop.runner.run(spec, backend, stage_executors, run_dir, clock)` takes
a validated `RunSpec`, provisions one compute resource through `backend`,
runs the spec's declared stages against it in order, syncs artifacts, and
destroys the resource, persisting every state transition to
`runs/<run_id>/state.json` (atomic write) and `runs/<run_id>/events.jsonl`
(append-only) so a crash can resume without double-provisioning or leaking a
rented resource. It writes ledger rows to `runs/<run_id>/ledger.jsonl` on
provision, sync, destroy and artifact loss. `run()` claims a pid-based lock on
`run_dir` for its duration, so only one process can act on a given run at a
time (`steno.loop.state.acquire_run_lock`/`release_run_lock`).

## Spec fields (schema `steno-run/v1`)

| Field | Meaning |
| --- | --- |
| `schema` | Must equal `steno-run/v1`. |
| `pair` | Path to the pinned harness/model pair manifest. Outside `dry_run`, preflight requires this path to exist on disk (checked as given, then relative to the spec file). |
| `inputs` | Must be non-empty and include at least `captures` and `tasks`. |
| `stages` | Ordered subsequence of `preflight, span, data, train, serve, evaluate, benchmark`. `span`, when present, must be the first stage after `preflight`. Any of `train, serve, evaluate, benchmark` requires `span` in the same spec. |
| `budget` | `max_usd`, `max_hours`, `min_credit`, `cleanup_reserve_usd` (all positive numbers, `cleanup_reserve_usd < max_usd`), `max_attempts_per_stage` (positive int, default 1, enforced across restarts). |
| `gates` | Keys restricted to `span`, `evaluate`, `benchmark`; an unrecognised key is rejected. Evaluated against each stage's reported metrics; see "Gate evaluation" below. |
| `compute` | Backend-specific dict (`backend`, `gpu_query`, `image`, `port_base`, ...). `available_credit` is required here outside `dry_run` and compared against `budget.min_credit`. |
| `artifacts` | `store` (required) and `emergency_policy`, required and restricted to `terminate_and_record_loss` (the only policy this wave implements; an unsupported value is rejected rather than silently ignored). |

Parse with `steno.loop.spec.load_spec(path)`, then call `.validate()`, which
raises `SpecValidationError` with a specific message on the first problem
found. `.json` specs parse with the standard library only; `.yaml`/`.yml`
specs use PyYAML if it is installed (a guarded import; its absence only
breaks YAML, never JSON). `RunSpec.identity_digest()` hashes `pair`, `inputs`,
`stages` and `gates`; the runner persists it on a fresh run and refuses to
resume a run directory whose digest no longer matches (see W-6 below).

## dry_run

`run(..., dry_run=True)` (what the CLI's `dry-run` command passes) relaxes
exactly three infra-dependent preflight checks so lifecycle mechanics can be
exercised against `FakeBackend` without any real pair file, credit balance or
stage executor: the credit floor, the pair path's existence, and a registered
executor for every non-preflight stage. Spec validity and required inputs are
always enforced, `dry_run` or not. Outside `dry_run`, all three are fail
closed: missing credit, a missing pair file, or a stage with no executor all
fail preflight rather than silently proceeding.

## Lifecycle

Two independent state machines, persisted after every transition:

```
Stage:     pending -> running -> succeeded
                              -> failed
           pending -> cancelled

Resource:  requested -> provisioning -> ready -> active -> syncing -> sync_verified
                                                     |          |
                                                     v          v
                                              destroy_requested (from ready/active/syncing/sync_verified)
                                                     |
                                       +-------------+-------------+
                                       v                           v
                              destroy_confirmed             destroy_unknown
                          (confirm_destroyed==True,     (an API error on confirm;
                           terminal)                     retried on every later
                                                          run() call, reachable
                                                          from destroy_requested
                                                          again, until provider
                                                          evidence confirms it)
```

`RunOutcome.completed` reflects resource cleanup only: `sync_verified` AND
`destroy_confirmed`. It is never a success signal by itself. `work_status`
(`succeeded`, `failed`, or `preflight_failed`) and `work_reason` are
recomputed from persisted stage state on every call, including a resume, so a
failure recorded in one call is never lost by a later one. `RunOutcome.success`
is `completed and work_status == "succeeded"`; that is the one flag a caller
should treat as "this run actually succeeded." The CLI's exit code follows
`success`, not `completed`.

Spend (`budget.max_usd` minus `cleanup_reserve_usd`) and wall-clock
(`budget.max_hours`) limits are checked before every stage and while waiting
for an unreachable host to come back, never only when a stage is actively
running, using the backend's `cost()` and the caller-injected `clock()`
independently of each other. A `cost()` exception is treated as budget
exceeded (fail safe) rather than ignored.

Once the run owns a resource (after `_ensure_provisioned` returns), ordinary
exceptions from `execute`, `transfer`, `cost` or ledger calls are caught,
recorded as a typed stage failure or transfer failure, and the run still
proceeds through sync and destroy in the same call. Only a genuine process
kill, which cannot be caught, requires a restart to recover; that path is
covered by idempotent provisioning (below) and idempotent preflight/stage
retry under `max_attempts_per_stage`. This includes `backend.inspect()`: a
raised exception during the reachability wait or during provisioning
reconciliation is caught and treated as "cannot confirm right now," never as
an uncaught crash.

## Gate evaluation

A gate is declared per stage (`span`, `evaluate` or `benchmark`) as a mapping
of field name to a numeric threshold. A stage executor reports its own
`metrics: dict[str, float]` on its `ExecuteResult`; after a stage otherwise
succeeds, every field in its gate is checked against those metrics:

- a field named `<metric>_min` requires `metrics[<metric>] >= threshold`;
- a field named `<metric>_max` requires `metrics[<metric>] <= threshold`;
- a missing metric, or a threshold not met, is a `gate_failure`, which is
  handled exactly like any other stage failure: the stage is marked `failed`
  and every stage after it is cancelled.

This wave's example (`examples/claude-code-qwen38.json`) declares
`gates.span.share_min`, meaning a span stage executor must report a `share`
metric (the compressible input share) of at least `0.25`. A field that is not
numeric, or whose name does not end in `_min`/`_max` (`invariance`,
`teacher_reference`, `task_pass_min_delta_points`, all present in the
example's `evaluate` gate, copied from `experiments/loop/gate.json`), is
carried through the spec but not evaluated in this minimal wave; translating
`gate.json`'s full field set into metrics and comparisons is left for a later
wave. Because gate checking is real, the CLI's `dry-run` (whose default
no-op stage executor reports no metrics at all) now correctly fails the
example spec's span gate, since nothing reports a `share` metric; pass a
stage executor that reports one to see a passing dry run.

## Fixed in this revision (Codex review findings W-1 through W-9, plus the recheck)

- **W-1** (provisioning crash): a crash between calling `backend.provision()`
  and persisting the returned id used to raise `RuntimeError` on resume.
  `_ensure_provisioned` now treats `provisioning` with no persisted id as
  recoverable: it repeats the (idempotent) provision call rather than
  orphaning a live resource. Covered by two tests crashing on each side of
  the provider call.
- **W-2** (uncaught exceptions after ownership): `execute`, `transfer`,
  `cost` and ledger calls are now individually wrapped; an ordinary exception
  becomes a typed failure and cleanup still runs in the same call, with no
  restart required.
- **W-3** (`destroy_unknown` was a dead end): the state machine now allows
  `destroy_unknown -> destroy_requested`, and the runner inspects the
  provider and retries destroy/confirm on every call until provider evidence
  (`confirm_destroyed() == True`, or `inspect().exists == False`) is seen.
- **W-4** (fake verification after failed sync): `FakeBackend` now models
  per-resource stored artifacts; `transfer()` after destruction (or before
  the relevant `execute()` ever ran) fails instead of echoing back whatever
  manifest was asked for. A failed sync now checks `artifacts.emergency_policy`
  explicitly and persists the loss (`state.extra["artifact_loss"]`, plus a
  ledger row) before destroying under `terminate_and_record_loss`.
- **W-5** (failure disappearing after resume): `work_status`/`work_reason`
  are persisted and recomputed from stage state on every call, not only the
  call that first observed the failure.
- **W-6** (resource/run identity): the run id is a fresh uuid, never derived
  from the pair filename, so two runs of the same pair never share an
  idempotency key. A run directory persists `identity_digest()` on creation
  and `IncompatibleResumeError` is raised if a resume's spec digest differs.
  `acquire_run_lock`/`release_run_lock` enforce one active owner per run
  directory (a stale lock from a dead pid is reclaimed automatically).
  Recheck: `identity_digest()` initially hashed the `pair` *path string* and
  the raw `inputs` values, so editing the pinned pair file or an input file
  in place (same path, new contents) went undetected. It now hashes file
  contents for `pair` and for any input value that is itself an existing
  local file path, alongside the path (so a rename is still visible too).
- **W-7** (preflight skipped on restart): preflight now reruns from `running`,
  not only `pending`; provisioning still only happens after preflight is
  persisted as `succeeded`.
- **W-8** (fail-open validation): `spec.validate()` now requires `span`
  before any of `train/serve/evaluate/benchmark`, requires `inputs.captures`
  and `inputs.tasks`, and rejects unsupported `gates` keys and
  `artifacts.emergency_policy` values. Preflight (outside `dry_run`) requires
  a real pair path, sufficient `compute.available_credit`, and a registered
  executor per stage. Recheck: gates were validated for shape but never
  evaluated. See "Gate evaluation" above for the minimal fail-closed
  evaluator now wired into the stage loop.
- **W-9** (unbounded restart retries): `state.extra["stage_attempts"]` is
  incremented and persisted before every execution attempt; once a stage
  reaches `budget.max_attempts_per_stage`, it fails permanently instead of
  retrying again on the next resume.
- **W-2, recheck** (an `inspect()` exception still escaped): the reachability
  wait and the provisioning-reconciliation path both called `backend.inspect()`
  unguarded. Both now catch exceptions: the wait treats it as "not reachable
  this poll" (the caps still apply), and reconciliation leaves the resource
  at `provisioning` (a persisted, reconcilable state) rather than raising;
  `run()` recognises that state and routes straight to a best-effort cleanup
  attempt instead of running stages against an unconfirmed resource.
- **N-2** (racy lock): `acquire_run_lock` used an exists-check followed by a
  separate (truncating) write, a classic TOCTOU race. It now creates the lock
  file with a single `os.open(..., O_CREAT | O_EXCL)` call; a stale lock (dead
  pid, or unreadable contents) is reclaimed by removing it and retrying the
  same atomic create, bounded so two processes racing a reclaim cannot loop
  forever.

## Compute backends (wave 2)

The runner and `RunSpec` are provider-neutral: neither one knows what a
provider's query language, offer shape, or SSH endpoint fields look like.
Only a backend, under `steno/loop/backends/<provider>.py`, knows its
provider; no provider import happens anywhere else in `steno/loop`.

A spec's `compute` block is now `{backend: "<name>", request: {...}, backend_options:
{...}}`:

| Field | Meaning |
| --- | --- |
| `backend` | The registry name the runner/CLI resolve (`fake`, `local`, `vast`, or a new one you register). |
| `request` | A `steno.loop.compute.ComputeRequest`: `gpu_count`, `gpu_memory_gb_min`, `gpu_families` (neutral names like `"h100"`, `"h200"`, `"a100"`), `cpu_ram_gb_min`, `disk_gb_min`, `network_down_mbps_min`, `image`, `max_hourly_usd`, `reliability_min`, `requires_direct_ssh`. Validated generically by `spec.validate()` when present; every field is optional. |
| `backend_options` | Opaque, provider-specific extras (a label prefix, a disk override, a raw query fragment). Never inspected outside the named backend module. |

This is fully backward compatible with wave 1: a flat `compute` dict with no
`request`/`backend_options` split (for example `{"backend": "fake"}`, or the
example spec's `gpu_query`/`image`/`port_base` keys) is still valid, and
`FakeBackend`/`LocalBackend` read the whole mapping themselves. Only a
backend that needs `ComputeRequest` fields (currently `VastBackend`) reads
`compute["request"]`.

### The contract

`steno.loop.backend.ComputeBackend` (an ABC) is the contract every backend
must satisfy: `quote(request)`, `provision(compute, idempotency_key)`
(idempotent: two calls with the same key never provision twice), `inspect`,
`execute` (a timeout is a typed `infra_failure`, never an uncaught
exception), `transfer` (verifies a checksum manifest; a mismatch is
`ok=False`, never silently accepted), `cost`, `destroy` (idempotent),
`confirm_destroyed` (`True`/`False`/`None`; `None` means "API error, unknown"
and must never be treated as "destroyed" by any caller). Each method's
docstring in `backend.py` spells out its idempotency and exception semantics
in full; read them before implementing a new backend.

### Adding a backend for a new provider

For example, an internal PayPal GPU cluster:

1. Write `steno/loop/backends/paypal_cluster.py` implementing `ComputeBackend`.
   All PayPal-specific imports (an internal SDK, an auth client) live only in
   this file.
2. At the bottom of that file, call
   `register_backend("paypal_cluster", PayPalClusterBackend)`.
3. Import the module once from `steno/loop/backends/__init__.py` (guard the
   import if the SDK might be missing, as `vast.py` does, so one missing
   optional dependency never breaks the registry for the others).
4. Reference it from a spec: `compute: {backend: "paypal_cluster", request:
   {...}, backend_options: {...}}`.
5. Add it to the conformance suite's `HARNESS_NAMES` in
   `tests/loop/test_backend_contract.py` with a `BackendHarness` (see
   `make_local_harness` for the simplest real example).

### Built-in backends

- **`fake`** (`backends/fake.py`): the wave 1 test double, moved here
  unchanged in behavior; `steno.loop.backend` re-exports `FakeBackend` so
  `from steno.loop.backend import FakeBackend` still works.
- **`local`** (`backends/local.py`): "provisions" a local working directory
  and runs stage commands (`stage_plan["command"]`, an argv list, never a
  shell string) as subprocesses with a timeout; `transfer()` copies files out
  and verifies a sha256 manifest; `destroy()` removes the directory; `cost()`
  is always zero. Exists to prove the contract is not vast-shaped, and is
  useful on its own for developing stage plans without renting anything.
- **`vast`** (`backends/vast.py`): the real vast.ai backend, using the
  `vastai` SDK and the call shapes already proven in
  `experiments/vast/bench_provision.sh` and `experiments/vast/rsh.sh`.
  - `quote()` maps neutral `gpu_families` to vast's `gpu_name` values through
    one table in this file (`NEUTRAL_GPU_FAMILY_TO_VAST_GPU_NAME`), builds a
    vast query string, and orders by `dph_total`. Note: vast's search query
    field `gpu_ram` is denominated in **GB**, unlike the returned offer
    dict's own `gpu_ram` field, which is in MB (confirmed empirically while
    building this backend); the query builder accounts for this.
  - `provision()` uses the idempotency key as the instance **label** and
    searches `show_instances()` for that label before ever calling
    `create_instance`, so a retried/resumed run cannot double-rent.
  - `inspect()` maps `actual_status`/`cur_state` to the neutral
    exists/reachable fields.
  - `execute()`/`transfer()` resolve the direct-port endpoint
    (`public_ipaddr` + `ports['22/tcp'][0]['HostPort']`) first, falling back
    to the proxy (`ssh_host`/`ssh_port`) only if no direct port exists; both
    run `ssh`/`scp` via `subprocess` with an argv list (no shell string) and
    a timeout. `transfer()` verifies each path with a remote `sha256sum`
    before copying it down.
  - `cost()` is `dph_total * elapsed hours`; `destroy()` calls
    `destroy_instance`; `confirm_destroyed()` returns `True` only when the id
    is absent from `show_instances()`, `False` when still present, and
    `None` (never "destroyed") on an API error.
  - `get_available_credit()` (from `show_user()['credit']`) backs the
    runner's preflight credit check (`capabilities = {"credit_lookup":
    True}`); `runner._backend_available_credit` calls it when the backend
    offers the capability, falling back to `compute.available_credit` from
    the spec otherwise.
  - The vast.ai API key is read from a key file (default `~/.vast_api_key`,
    overridable via the `key_file` constructor argument) exactly once,
    directly into the SDK client constructor; it is never assigned to an
    attribute of `VastBackend`, so it cannot appear in a `repr()` of the
    backend. Do not print `backend._client` (the SDK object) directly.

### Conformance suite

`tests/loop/test_backend_contract.py` runs one parametrised suite
(`TestBackendContract`) against `fake`, `local`, and `vast` (wired to
`RecordedVastSDK`, a small in-file test double with the same method names as
`vastai.VastAI`, so the vast translation logic is tested with no network and
no real vast.ai calls). It checks: idempotent provision, inspect's
exists/not-exists states, execute's ok and typed-timeout outcomes, transfer's
checksum verification (and rejection of a mismatch, and that a destination is
required and the artifact survives destroy()), destroy-then-confirm, that
confirm never reports `True` before destroy, and (for backends with an
external API to fail against) that an API error surfaces as `None`
("unknown"), never `False`/`True`. `LocalBackend` has no such failure mode by
construction and is exempted from that one check
(`supports_unknown_confirm=False`).

A second round of review (steno-build-wave2's Codex review, findings X-1
through X-17) found gaps an offline probe could reach even though the shared
suite passed; the fixes and their dedicated tests, all in this same file plus
`test_runner.py`, are:

- **X-1** (double-rental risk on an ambiguous create): the SDK's own
  automatic retry is disabled (`CLIENT_RETRY_ATTEMPTS = 1`); an ambiguous
  create_instance() outcome (raised, or a response with no `new_contract`)
  triggers a bounded label-reconciliation poll (`_reconcile_or_raise`,
  `RECONCILE_ATTEMPTS`/`RECONCILE_DELAY_SECONDS`) instead of ever calling
  create_instance() again; if reconciliation cannot resolve it,
  `AmbiguousProvisionError` stops the run rather than risking a duplicate.
  `AmbiguousCreateSDK` in the test file models both "response lost, instance
  already created" and "label visible only after N polls".
- **X-7** (a raw SDK exception can carry the API credential): every SDK call
  goes through `_call`/`_call_with_deadline`, which raise a sanitised
  `BackendError` via `_raise_sanitized`. An offline probe found
  `raise ... from None` alone insufficient -- Python still populates
  `__context__` with the original exception, just hides it from a printed
  traceback -- so `_raise_sanitized` explicitly clears `__context__` after
  raising. `SecretLeakingSDK` (a double whose every method raises an
  HTTPError-shaped exception carrying a synthetic secret) proves no path
  (constructor, quote, provision, inspect, execute, destroy, confirm) lets it
  escape, in `str()`, `__cause__`, or `__context__`.
- **X-8** (unknown treated as absence): `_show_instances_validated` rejects a
  `None`/non-list response as `BackendError` rather than `instances or []`;
  `confirm_destroyed()`/`destroy()` never coerce that into `True`.
  `destroy()` validates the response's `success` field instead of "did not
  raise". `MalformedResponseSDK` exercises null and malformed responses.
- **X-3** (shell interpretation): `execute()` builds one already-quoted
  remote command string (`shlex.join`) passed as a single ssh argv element;
  `transfer()` no longer runs any remote command at all (see X-2) and quotes
  scp's remote path segment (`shlex.quote`). Every manifest/output path is
  validated by `compute.validate_relative_artifact_path` (absolute paths and
  `..` rejected) in both `local.py` and `vast.py`.
- **X-2** (transfer success without proof): `transfer()` on both real
  backends now requires an explicit `manifest["_destination"]` and hashes the
  copied file at the destination (not the source, not a remote `sha256sum`)
  before reporting success. `test_artifacts_survive_teardown` transfers,
  destroys the resource, then reads the destination file directly off disk.
- **X-6** (a real backend silently no-oping a plan with no work): the shared
  `backend.stage_plan_has_work()` check is enforced by `LocalBackend.execute`
  and `VastBackend.execute`; `test_runner.py`'s
  `test_run_with_a_non_fake_backend_fails_a_stage_that_has_no_executor_or_command`
  drives this through `run()` (LocalBackend, dry_run=True, no executors)
  rather than only calling `backend.execute()` directly.
- **X-9** (LocalBackend loses state across restart): resource/key metadata
  is persisted to a `_steno_local_registry.json` file under `root_dir`
  (atomic write); `destroy()` verifies the directory is actually gone before
  recording it destroyed. `test_local_backend_recovers_resource_across_restart`
  and `test_local_backend_destroy_reports_failure_when_removal_is_incomplete`
  cover both.
- **X-12** (quote ignores constraints / wrong storage pricing): `cpu_ram_gb_min`
  is now translated (**not** network-verified this round -- the units
  assumption follows `gpu_ram`'s confirmed GB convention but should be
  spot-checked with one real `search_offers` call before relying on it); a
  field this backend cannot translate raises `BackendError`
  (`_TRANSLATED_REQUEST_FIELDS`); `quote()` passes the *actually requested*
  disk size as `search_offers`'s `storage` argument so `dph_total` (and any
  `max_hourly_usd` filter) reflects real pricing.
- **X-13** (deadline excludes endpoint lookup): `execute()`/`transfer()`
  compute one deadline up front and pass it through `_call_with_deadline`
  (a small shared `ThreadPoolExecutor`, `_get_deadline_pool()`) covering
  the SDK lookup, with the remaining budget then bounding the subprocess.
  `test_vast_execute_deadline_covers_slow_endpoint_resolution` uses a double
  with an artificially slow `show_instance` to prove the overall deadline is
  enforced, not just the subprocess's own timeout.
- **X-14** (credit lookup failure falls back to a stale assertion):
  `runner._backend_available_credit` now returns a distinct
  `CREDIT_LOOKUP_FAILED` sentinel (not `None`) when a backend that
  advertises `credit_lookup` fails or returns a non-finite value; preflight
  fails closed on that sentinel instead of falling back to
  `compute.available_credit`. `test_runner.py` covers a raising lookup, a
  NaN lookup, and a successful live lookup overriding a too-low asserted
  value.
- **X-17** (`create_backend("fake")` raised `TypeError`): the registry now
  wraps `FakeBackend` in a factory supplying a default `clock` (`time.time`)
  while still accepting an injected one.

### Live vast.ai test

`tests/loop/test_backend_contract_live.py` has two `@pytest.mark.live`
tests (read-only: `quote()`/`get_available_credit()` only, never
provision/destroy) skipped unless `STENO_LIVE_VAST=1` is set. A bare
`pytest tests/loop` never runs them and never touches vast.ai.

## Running tests and the dry run

```bash
# from the repository root
experiments/.venv/bin/python -m pytest tests/loop -q

# validate a spec (no execution)
experiments/.venv/bin/python -m steno.loop.cli validate steno/loop/examples/claude-code-qwen38.json

# dry-run against FakeBackend: no network, no GPU, no vast.ai calls
experiments/.venv/bin/python -m steno.loop.cli dry-run steno/loop/examples/claude-code-qwen38.json --run-dir /tmp/steno-dry-run

# read-only: print the spec's backend's offers (no provisioning). For a spec
# whose compute.backend is "vast" this makes real (but read-only) vast.ai
# API calls: search_offers and, indirectly through get_available_credit(),
# show_user. It never creates, starts or destroys anything.
experiments/.venv/bin/python -m steno.loop.cli quote steno/loop/examples/claude-code-qwen38.json
```

## Known gaps (left for the next wave)

- No mapping from stages to the existing chain scripts
  (`experiments/vast/*chain*.sh`, `experiments/loop/controller.py`); this
  wave's `stage_executors` argument is the seam where that mapping plugs in.
  `VastBackend.execute()` can now run an arbitrary remote command over SSH,
  but nothing yet translates a stage name into the right chain script.
- No gate evaluation: `spec.gates` is validated for shape and carried through
  but never checked against a stage's result. `gate.json`-style thresholds
  (as in `experiments/loop/gate.json`) still need a generic evaluator.
- No failure-triage/retry classification beyond the flat `max_attempts_per_stage`
  counter; a failed stage still stops the run rather than being retried
  selectively (build order step 8).
- Only one compute resource per run is modeled; multi-resource runs (for
  instance separate train/serve boxes) are out of scope for this wave.
- The run-directory lock is a local pid file; it does not protect against two
  different machines racing on a shared filesystem.
- `VastBackend.quote()` queries one GPU family at a time (vast's query
  language has no clean OR); a spec wanting a fallback family needs two
  `quote()` calls or a future `backend_options` extension.
- No `steno run` (live) CLI command yet, only `validate`/`dry-run`/`quote`;
  wiring a real backend into a live run through the CLI, plus the
  stage-to-chain-script mapping above, is wave 3 work.
- The conformance suite's vast case exercises translation logic through a
  recorded SDK double, not the real API's actual latency/error shapes; the
  `@pytest.mark.live` file is the (opt-in, unrun-by-default) bridge to that.
