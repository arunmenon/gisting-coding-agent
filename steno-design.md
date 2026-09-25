# Steno design: harness adapters and the run loop

This is the design for two Steno capabilities: span analysis that works for any harness through adapters, and a single run loop with a small set of self-improvement mechanisms. It combines two independent design opinions, from Fable and from Codex (`gpt-6-astra`, medium effort), both grounded in this repository's code. They agree on the structure; where they differed, the choice made here is noted.

Sources: `experiments/journeys/reviews/steno-design-20260925/` holds the brief and both opinions verbatim. Build status and open work live in [`steno-capability.md`](steno-capability.md).

## 1. Span analysis for any harness

### The shape

Two adapters, with everything between them generic:

```
raw traffic ──> HarnessAdapter ──> CallRecord ──> generic span analysis ──> ModelAdapter ──> token ids
                (per harness)      (canonical)    (same for every harness)   (per model)
```

- **Harness adapter:** turns one harness's wire format into a canonical call record, rewrites requests for the proxy, and launches the harness for evaluation.
- **Model adapter:** turns canonical calls into the exact tokens the served model sees: tokenizer, chat template, special tokens.
- **Pair manifest:** pins a harness adapter version and a model adapter version together. Every artifact downstream records it.

Onboarding a new harness, including an in-house PayPal harness, means writing one harness adapter and its fixtures. Nothing else changes.

### The canonical call record

One model call, with the wire format removed and nothing lost:

| Field | Contents |
|---|---|
| Identity | Schema version, call ID, run, task and attempt IDs, harness and adapter versions |
| Session | Session ID or explicitly none, parent session if known, turn index, where the identity came from |
| Preamble | Ordered parts (instructions, tool catalogue, other), exact text, source location |
| Tools | Ordered catalogue with full schemas; its hash is computed by the generic layer |
| Messages | Canonical roles and typed blocks, including tool calls and results |
| Request controls | Requested model, streaming, reasoning and template-affecting options |
| Response and usage | Reply blocks, stop reason, token usage and its source, timing |
| Provenance | Pointer to the raw capture line, raw hash, transformation log, unsupported fields |

Unknown content is kept and marked, never dropped. A missing session ID stays missing; the generic layer refuses to split training and evaluation data on a guess.

### The harness adapter contract

```python
class HarnessAdapter(Protocol):
    identity() -> AdapterIdentity                 # name, version, capabilities
    wants(raw) -> bool                            # is this captured request a model call we analyse
    parse_request(raw) -> CallRecord
    response_decoder() -> ResponseDecoder         # streaming and non-streaming replies, fragments, errors
    rewrite_request(raw, new_preamble) -> raw     # inverse of parse_request; the proxy uses it to swap in Steno tokens
    raw_value_rules() -> list[RawValueRule]       # declared per-session values that must stay raw
    launch(task, endpoint, workspace) -> LaunchPlan   # how to run the harness on an evaluation task
    collect_result(process, artifacts) -> HarnessResult   # typed outcome: ok, timeout, transport failure
```

Adapters stay thin: they may not import tokenizer, span or segment code, and they are tested only against golden fixtures. Policies such as reasoning-effort remapping belong in the pair manifest, not in the adapter.

The Claude Code adapter is built first by moving existing code behind this interface, with no change in behaviour. That becomes the reference implementation.

### What is generic

1. **Capture:** a wire-agnostic relay stores raw bytes plus canonical records, and accounts for every request, including failed and unsupported ones.
2. **Discovery:** looks at every call, not the most common one. Calls are grouped into cohorts by catalogue and instruction structure, and every cohort is reported.
3. **Classification:** each span is labelled fixed, session-varying, call-varying, protected raw, or unresolved. Only validated fixed spans are compressed.
4. **Invariance report:** every call is checked against the proposed segment map: complete match, ordering, raw values preserved exactly. Any difference across sessions that no rule covers fails the run. This report, not the raw-value regex, is the safety net.
5. **Counting:** tokens are counted only through the model adapter, on the full rendered call.
6. **Identity:** the segment map records harness, adapter version, model, tokenizer, template, catalogue and rules hashes. The proxy refuses a bundle with any of them missing.
7. **Reporting:** share of input, cohorts, exclusions and provenance. "Invariant" means within the captured evidence.

At serving time, a call that does not fully match the segment map is sent with the full prompt, and the reason is logged.

### The model adapter contract

```python
class ModelAdapter(Protocol):
    identity() -> RenderingIdentity               # model revision, tokenizer, template, serving front end
    render(call) -> RenderedPrompt                # exact token ids plus a map from source parts to token ranges
    prefix_boundary(rendered) -> int              # where the first non-preamble turn starts
    register_steno_tokens(n) -> TokenRange        # reserves contiguous new token ids
    swap_template() -> Path                       # the chat template that activates Steno tokens by token id
    verify_server(call, endpoint) -> ParityReport # rendered token ids against what the engine actually received
```

This removes today's model literals from span code: the `<|im_start|>user` search, the hand-ordered Qwen tool block, the hardcoded embedding row count, and the template's substring test for `<gist_`.

### Onboarding a new harness

1. **Capture:** at least three sessions of five or more turns through the relay, including one run from a different working directory and one with a different tool setup.
2. **Adapter:** implement the contract, declare the raw-value rules and the launch recipe.
3. **Golden fixtures:** 20 raw requests with their expected call records. Parse, then rewrite with the same preamble, must reproduce the request byte for byte.
4. **Invariance report:** 100 percent of calls in each cohort match; every declared rule fires; every observed difference is covered by a rule or explicitly accepted.
5. **Rendering parity:** for 20 calls, the model adapter's token ids match the serving engine's.
6. **Validation capture:** a fresh capture, taken after discovery, passes the same report before the adapter gets a version tag.

The output is an onboarding packet: fixtures, invariance report, parity evidence, cohorts and exclusions.

### Where the abstraction will strain

- A harness with no single system field, or with tool schemas inside messages. Keep preamble parts open-ended and let the generic layer treat any part as a candidate span.
- Unstable or missing session identity. Adapters report what they know; they do not guess.
- Multimodal content and lossy protocol conversion. Keep it opaque and mark the call unsupported rather than approximating.
- Server-side template changes. The parity check catches them.

## 2. One run loop

### The shape

One entry point, `steno run <spec.yaml>`, replaces the per-journey scripts. A journey becomes a spec file plus the run directory the loop writes.

```yaml
schema: steno-run/v1
pair: pairs/<harness>-<model>.yaml          # pinned adapter, model, tokenizer and template identities
inputs: {captures: <digest>, tasks: <digest>, recipe: {ratio: 8, lr: 1e-3, accum: 8}}
stages: [span, data, train, serve, evaluate, benchmark]   # span always runs first and gates the rest
budget: {max_usd: 40, max_hours: 8, min_credit: 30, cleanup_reserve_usd: 5, max_attempts_per_stage: 2}
gates: {span: {share_min: 0.25, invariance: all_calls}, evaluate: held_out_policy, benchmark: common_slo}
compute: {backend: vast, gpu_query: "...", image: vllm/vllm-openai:v0.28.0}
artifacts: {store: <durable destination>, emergency_policy: terminate_and_record_loss}
```

The spec is validated before any money is spent: inputs present, credit above the floor, ports allocated once, pair identities pinned.

### Stages

`preflight, span, data, train, serve, evaluate, benchmark`. Each stage declares its required inputs, produces content-addressed outputs, has its own deadline, and returns a typed result. A span failure stops everything downstream. Evaluation separates infrastructure failure from task failure, and neither can quietly become a pass. A later run may reuse an earlier stage's outputs only after their identity and gate are re-verified.

### Lifecycle

Work and rented resources have separate states, persisted after every transition so a restart can reconcile against the provider:

```
Stage:     pending -> running -> succeeded | failed | cancelled
Resource:  requested -> provisioning -> ready -> active -> syncing -> sync_verified
           -> destroy_requested -> destroy_confirmed
```

A run is complete only when required artifacts are verified and destruction is confirmed by the provider. An API error means unknown, not destroyed. Spend and wall-clock limits are enforced independently of GPU activity, including while a host is unreachable.

### Compute backends

```python
quote(resources); provision(spec, idempotency_key); inspect(id); execute(id, stage_plan)
transfer(id, manifest); cost(id); destroy(id); confirm_destroyed(id)
```

Local and vast.ai first. SSH, endpoints and billing stay behind the backend. The ledger becomes a JSONL the loop writes on create, sync and destroy; `ledger.md` is rendered from it.

### Self-improvement: four bounded mechanisms

Taken from the recursive self-improvement line of thinking, deliberately limited to four, piloted on one recipe family with a fixed spend cap.

| Mechanism | What it does | Guardrails | How we know it helps |
|---|---|---|---|
| Failure triage | Classifies a failed stage (provisioning, SSH, out of memory, divergence, unhealthy server, evaluation transport, gate failure) and retries only allowlisted classes, at most twice | Retries count against the budget; unknown failures stop; changed settings get a new run identity | Unattended completion rate; spend per completed run; wrong retries |
| Lessons as checks | Turns each incident into a preflight check or postcondition, as the September 15 liveness incident already did | Proposed with a reproducer, reviewed like code; never edits gates or the runner by itself | Repeat incidents; failures caught before any rental |
| Gated promotion | A candidate bundle replaces the incumbent only after passing a frozen held-out suite against the full prompt measured in the same run, with full substitution and invariance checks | Paired repeats; a margin declared in advance; limited promotion cadence so the held-out set stays held out; rollback | Promotions later reverted; cost per successful task |
| Next-recipe proposer | Reads the results ledger and proposes one next recipe from an allowed set of fields | Proposal only; a person approves; fixed quota and spend; cannot change gates, budgets, adapters or code; no access to held-out results | Gate pass rate of proposed versus hand-written recipes; improvement per experiment dollar |

Not adopted: self-modifying loop code or prompts, automatic loosening of gates, open-ended search, agents spawning agents, and any agent with teardown authority or the power to judge its own result. Each adds cost and invalidates comparisons before showing any benefit.

## 3. Build order

1. **Canonical record and Claude Code adapter.** Define the call record and pair manifest; move the Claude Code parsing behind the harness adapter with no change in behaviour; one serialisation for all three current code paths.
2. **Invariance report as stage zero.** All-call discovery, cohorts and the per-call check; fail on any uncovered difference.
3. **Mandatory bundle identity.** Required hashes in every segment map, enforced by the proxy and the dataset builder; mark the existing maps without hashes as legacy.
4. **Qwen model adapter.** Move the Qwen literals out of span code; add the server parity check.
5. **Run spec, preflight and persisted lifecycle,** tested against a fake backend for restart, failed sync, unreachable host and failed teardown.
6. **Vast backend** with independent deadlines, incremental sync and confirmed teardown.
7. **Migrate one journey** into a spec using the existing stage scripts; confirm a clean restore of its artifacts.
8. **Failure triage** with typed stage markers, then lessons as checks.
9. **Golden fixtures and onboarding packet** for the Claude Code adapter, as the template for the next harness.
10. **Gated promotion,** then the recipe proposer, inside the bounded pilot.

Steps 1, 2 and 5 come first: they unblock both capabilities and expose the current serialisation disagreement immediately.
