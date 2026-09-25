# steno.loop

Wave 1 of the Steno run loop (steno-design.md section 2, build order step 5).
`steno run <spec>` is meant to replace the per-journey shell scripts under
`experiments/vast/` and `experiments/loop/` with one declarative entry point.
This wave implements the spec, the persisted lifecycle, the compute backend
protocol with a fake backend for tests, the runner, the ledger and a small
CLI, all local: no network, no GPU, no vast.ai calls happen anywhere in this
package. Revised after a Codex review (steno-build-wave1) found blocking and
major gaps in the first draft; see "Fixed in this revision" below.

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

## Adding a backend

Implement the `ComputeBackend` protocol in `steno/loop/backend.py`:
`quote`, `provision` (idempotent via the `idempotency_key` argument),
`inspect`, `execute`, `transfer`, `cost`, `destroy`, `confirm_destroyed`.
`VastBackend` in the same file is a documented stub (raises
`NotImplementedError`) describing the intended mapping onto
`experiments/vast/*.sh` and `experiments/vast/rsh.sh` for wave 2. Do not
implement it by copying this wave's `FakeBackend` semantics; `FakeBackend` is
a test double, not a template for a real provider's failure modes.

## Running tests and the dry run

```bash
# from the repository root
experiments/.venv/bin/python -m pytest tests/loop -q

# validate a spec (no execution)
experiments/.venv/bin/python -m steno.loop.cli validate steno/loop/examples/claude-code-qwen38.json

# dry-run against FakeBackend: no network, no GPU, no vast.ai calls
experiments/.venv/bin/python -m steno.loop.cli dry-run steno/loop/examples/claude-code-qwen38.json --run-dir /tmp/steno-dry-run
```

## Known gaps (left for the next wave)

- No real backend: `VastBackend` is a stub. Wave 2 implements it against
  `experiments/vast/bench_provision.sh` and `experiments/vast/rsh.sh`.
- No mapping from stages to the existing chain scripts
  (`experiments/vast/*chain*.sh`, `experiments/loop/controller.py`); this
  wave's `stage_executors` argument is the seam where that mapping plugs in.
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
