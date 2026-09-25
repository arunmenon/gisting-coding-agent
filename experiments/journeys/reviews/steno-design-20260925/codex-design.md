**1. Harness-agnostic span analysis**

Use two versioned adapters: a **harness adapter** for request semantics and evaluation launch, and a **model rendering adapter** for the exact serving representation. Bind them through a pinned pair manifest.

This addresses the divergent serialization in [static_span.py](/Users/arunmenon/projects/gisting/experiments/analysis/static_span.py:35), [span.py](/Users/arunmenon/projects/gisting/experiments/gist/span.py:16) and [dataset.py](/Users/arunmenon/projects/gisting/experiments/gist/dataset.py:31). All three consumers should eventually use the same canonical records and renderer.

**Adapter contract**

A sketch, with protocol decoding and launching implemented as separate components behind one harness registration:

```python
class HarnessAdapter:
    identity() -> AdapterIdentity  # name, version, supported capabilities
    capture_plan(config) -> CapturePlan
    parse_request(raw_request, context) -> CanonicalCall
    response_decoder(call) -> ResponseDecoder
    raw_value_rules(config) -> list[RawValueRule]
    launch(task, endpoint, workspace, run_context) -> LaunchPlan
    collect_result(process_result, artifacts) -> HarnessResult

class ResponseDecoder:
    feed(chunk: bytes, timestamp) -> list[CanonicalEvent]
    finish(status, transport_error) -> CanonicalResponse
```

`CapturePlan` specifies the interception or import mechanism. `LaunchPlan` contains executable, arguments, environment references, working directory, timeout and result locations. The generic executor owns processes, deadlines and cleanup.

The canonical record should preserve structure rather than flatten everything into system text:

| Field | Required content |
|---|---|
| Identity | Schema version, call ID, run/task/attempt IDs, harness and adapter versions |
| Session | Session ID, parent session if known, sequence, identity source and confidence |
| Instructions | Ordered blocks, roles, original placement, exact text, source references |
| Tools | Ordered catalogue with complete schemas and extension fields |
| Messages | Ordered roles and typed blocks, including tool-call/result IDs and opaque content |
| Request controls | Requested model, stream flag, reasoning/template-affecting options, extensions |
| Provenance | Raw capture reference/hash, timestamps, received and forwarded request identities, transformation log |
| Outcome | HTTP/transport status, completion/truncation state, response blocks, usage with source, timing |
| Validation | Unsupported fields, parse errors, missing identity and preservation annotations |

Unknown content is retained and marked unsupported for analysis when necessary. Missing session identity must remain explicit. A launcher can supply trustworthy correlation; first-user-text guessing must not.

`RawValueRule` identifies a field or text range, its scope such as session or call, reason, and evidence source. Prefer harness declarations and launch-context values. Use configurable detectors and observed differences as additional protection. A value that happens to remain unchanged in the sample can still require verbatim preservation.

Streaming decoders handle fragmented events, tool arguments, usage, errors and incomplete responses. Capture forwards original bytes independently of decoding. Protocol translation, if required for serving, is an explicit pair component with its own tests.

**What becomes generic**

1. **Capture accounting:** store raw evidence and canonical records; account for every observed request, including failures and unsupported calls. Transport hooks and decoding remain pluggable.
2. **Discovery:** examine every call, including changes within a session. Partition into declared compatibility cohorts using catalogue, instruction structure and rendering options. Report all cohorts and their coverage.
3. **Classification:** label spans as observed fixed, session-varying, call-varying, protected raw or unresolved. Only unprotected, validated fixed spans become candidates.
4. **Invariance:** validate the proposed map against every call in its cohort. Check complete matching, ordering, ambiguous anchors, insertions/deletions and exact raw-value preservation. Unmatched calls remain visible and ineligible.
5. **Counting:** delegate full-context rendering/tokenization, then aggregate per-call and per-session counts. Do not add independently tokenized segment lengths and call that exact.
6. **Artifacts:** emit canonical calls, cohort inventory, segment maps, invariance report and a hashed analysis manifest. Include capture, adapter, policy, catalogue, model revision, tokenizer, template, renderer and segment-map identities.
7. **Reporting:** report eligibility, exclusions, variation, token distributions and measurement provenance. “Invariant” means within the recorded evidence, not guaranteed for future requests.

Segment locations need structural selectors, occurrence identity and verified rendered ranges. Literal substring matching alone is insufficient. At runtime, an unfamiliar or partially matching call should use the full prompt and record the reason.

Keep an **analysis manifest** distinct from a deployable compression bundle. A later bundle additionally binds learned rows, added-token IDs and serving configuration. Analysis should not invent embedding metadata.

**Model-side contract**

Yes, introduce a second adapter, specifically a rendering profile:

```python
class ModelRenderer:
    identity() -> RenderingIdentity
    validate(call, pair_config) -> CompatibilityReport
    render(call, pair_config) -> RenderedPrompt
    verify_server(call, endpoint) -> TokenParityReport
```

`RenderingIdentity` pins tokenizer files, model revision, chat template, serving frontend conversion/version, special-token policy and rendering options.

`RenderedPrompt` contains exact token IDs, rendered text where available, source-to-rendered mappings and supported compression boundaries. Boundaries can be noncontiguous. If safe attribution cannot be established, reject that region.

Server verification compares actual prompt token IDs when available. Matching counts alone is weaker evidence and must be labelled accordingly. This adapter owns the serving serialization, including merging or moving instruction blocks. The harness adapter only preserves their original meaning and placement. Pair configuration owns policies such as effort remapping.

**Onboarding and risks**

For an unknown harness, first establish its actual capture surface and observable behavior. Do not assume an HTTP Messages API, a tools array or a leading system prompt.

The principal leaks are lossy protocol conversion, multimodal content, server-side normalization, history-dependent templates and unstable session identities. Preserve opaque data, expose capabilities explicitly and reject unsupported analysis. Share protocol codecs between adapters where possible; keep discovery, budgets, hashing and reporting out of harness implementations.

Priority work:

1. Define canonical schema, pair manifest and adapter conformance assertions.
2. Implement the Claude Code adapter and its pinned serving renderer as the reference pair.
3. Build sanitized fixtures preserving block boundaries and variation: multiple sessions and turns, catalogue changes, repeated anchors, Unicode, missing identity, interrupted streams, and path/ID shapes missed today.
4. Add all-call discovery and invariance checking, including adversarial insertion/deletion fixtures and exact preservation checks.
5. For the new harness, supply an adapter, launch recipe, declared raw-value rules and golden captures with independently checked expected records.
6. Produce its onboarding packet: fixture results, server parity evidence, capture-diversity coverage, exclusions and invariance report. Require a separate validation capture after discovery before trusting the map.

**2. Consolidated auto loop**

Build one deterministic runner with declarative recipes, typed stage results and persisted resource ownership. Add bounded adaptive behavior only after recovery and accounting work.

The immediate lifecycle defects are concrete: [controller.py](/Users/arunmenon/projects/gisting/experiments/loop/controller.py:108) ignores synchronization failure and marks work done after attempting destruction.

**Architecture sketch**

Illustrative run specification:

```yaml
schema: steno-run/v1
pair: pairs/<harness-model>.yaml  # pinned identities and compatibility
inputs:
  captures: <artifact digest>
  tasks: <suite digest>
  recipe: <recipe digest>
stages: [span, data, train, serve, evaluate, benchmark]
compute:
  default: <backend profile>
  overrides: {span: local}
budget:
  total_usd: <cap>
  wall_seconds: <cap>
  max_instances: 1
  max_attempts_per_stage: 2
  cleanup_reserve_usd: <reserve>
gates:
  span: <versioned policy>
  data: <coverage and split policy>
  serve: <compatibility and readiness policy>
  evaluate: <held-out quality policy>
  benchmark: <common SLO policy>
artifacts:
  store: <durable destination>
  emergency_cleanup: <explicit policy>
```

The pipeline is:

```text
preflight → span study → data → train → serve → evaluate → benchmark
```

Each stage declares required inputs, hashed outputs, resource requirements, deadline and a machine-readable result. Training remains an opaque stage contract here; this recommendation does not redesign it.

A shortened pipeline may reuse prior outputs only after identity and gate verification. Span failure stops expensive downstream work. Evaluation must distinguish infrastructure failure from task failure; neither may silently become a passing result.

Use separate persisted states for work and resources:

```text
Stage:
PENDING → RUNNING → SUCCEEDED | FAILED | CANCELLED

Resource:
REQUESTED → PROVISIONING → READY → ACTIVE
          → QUIESCING → SYNCING → SYNC_VERIFIED
          → DESTROY_REQUESTED → DESTROY_CONFIRMED
```

Persist transitions, attempts, deadlines, instance IDs, artifact acknowledgements and spend estimates before proceeding. On restart, reconcile provider state and stage evidence. API errors mean “unknown,” not “destroyed.” Use a controller lease and idempotency keys to prevent duplicate launches.

A compute backend provides:

```python
quote(resources)
provision(spec, idempotency_key)
inspect(resource_id)
execute(resource_id, stage_plan)
transfer(resource_id, artifact_manifest)
cost(resource_id)
destroy(resource_id)
confirm_destroyed(resource_id)
```

Implement local and Vast backends first. Keep provider-specific SSH, endpoints and billing behind them. Allocate ports once and pass the resulting endpoint object through every stage.

Successful closure requires verified required artifacts and confirmed destruction. Failed cleanup remains pending and visible. Enforce wall and spend limits independently of GPU utilization, including unreachable hosts and provisioning.

There is an unavoidable conflict if artifact recovery fails while rental charges continue. Reserve cleanup budget, sync incrementally, and declare an emergency policy in advance. At its deadline, that policy can terminate resources and record explicit artifact loss. Such a run cannot be marked successfully completed. Hard cost guarantees also depend on provider termination capabilities.

Replace journey scripts with versioned recipe files and named parameter matrices. Historical scripts remain archival evidence. Generate human-readable ledgers from authoritative run events and reconciled billing.

**Bounded mechanisms to take from RSI**

Use at most these four. Start with a pilot limited to one recipe family, four completed runs and a fixed total spend cap.

| Mechanism | What it does and needs | Guardrails | Measure |
|---|---|---|---|
| Failure triage | Classifies typed stage failures using logs and provider status; selects retry, stop or escalation | Deterministic retry policy; capped attempts; unknown failures stop; changed experimental settings require a new run identity | Recovery rate, incorrect retries, wasted spend, intervention time |
| Incident-to-check workflow | Proposes a regression fixture or preflight check from a recorded incident | Reviewed changes with a reproducer; no automatic edits to runner or gates | Repeat-incident rate, failures caught before rental, false positives |
| Gated promotion | Updates an incumbent artifact pointer after candidate verification | Frozen held-out suite, paired repeats, predeclared quality margin, full substitution and serving checks, common benchmark SLO, rollback | Successful-task cost, quality uncertainty, promotion regressions |
| Next-recipe proposer | Reads development results and suggests one change from an allowed search space | Proposal only initially; fixed candidate quota and spend; no hidden-test access; no gate, code or budget edits | Improvement per experiment dollar and recommendation acceptance rate |

Held-out evaluation must have a limited promotion cadence. Repeatedly selecting against the same held-out results eventually turns them into development feedback.

Do **not** adopt recursive agent spawning, unrestricted self-modification, autonomous gate relaxation or open-ended experiment search. These expand cost and invalidate comparisons before demonstrating a benefit. An agent should never own teardown authority or decide whether its own result passed.

Priority work:

1. Specify the run manifest, stage-result schema and lifecycle invariants, including budget versus artifact-loss policy.
2. Build persisted state and a fake backend; test restart, failed sync, unreachable hosts and failed destruction.
3. Implement shared Vast lifecycle handling with independent deadlines, incremental sync and confirmed teardown.
4. Connect the span-first preflight and gates to the runner.
5. Migrate one representative journey into a recipe using existing stage executables; verify clean artifact restoration.
6. Unify evaluation failure handling and frozen promotion gates.
7. Add failure triage, then evaluate the remaining mechanisms within the bounded pilot.

The first three pieces of work overall would be:

1. Define the canonical-call, rendering and pair contracts with Claude Code fixtures.
2. Implement an all-call span conformance study producing cohort, preservation and parity evidence.
3. Specify and test the persisted loop lifecycle with a fake backend before migrating any rental workflow.

Read-only review completed. No files changed.
