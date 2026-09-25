# steno.span

Harness-agnostic span analysis: turns any harness's captured traffic into canonical call
records, then reports which parts of every call are fixed, which vary by session or by call,
which are declared safe to leave raw, and which are unexplained. This is wave 1 of the design
in `steno-design.md` section 1 (build order steps B1 to B3): the canonical record, the Claude
Code adapter, all-call discovery, and the invariance report. It does not yet do model rendering,
token counting, bundle enforcement at a proxy, or launching a harness for evaluation; those are
later waves.

## What it does

```
raw capture line -> select_and_parse -> CallRecord -> discover -> segment map -> validate -> JSON
```

1. A `HarnessAdapter` (one per harness, `steno/span/adapters/`) parses one captured record into
   a `CallRecord` (`steno/span/record.py`): the request's preamble, tool catalogue, message
   history, controls, reply and usage, with nothing dropped (unknown fields land in
   `unsupported`, with a source location such as `"system[1]"` so they can be traced back).
   `analysis.select_and_parse()` is the one place a raw capture becomes either a `CallRecord` or
   an explained `parse_error` outcome; nothing an adapter's `wants()` accepts is allowed to
   disappear as a silent skip.
2. `steno/span/analysis.py` groups `CallRecord`s into cohorts by tool-catalogue hash plus
   preamble structure. **Discovery** (`discover()`) derives a segment map per cohort: which
   lines are identical across every call (fixed), which are covered by a declared raw-value rule
   regardless of whether the sample happens to vary on them (protected-raw), and which vary
   without being covered by anything (unresolved, and this fails the cohort). **Validation**
   (`validate()`) is a separate operation: it checks a *fresh* set of calls against a *previously
   frozen* segment map, and a call whose cohort was never seen during discovery is reported as
   `insufficient_evidence` rather than silently passed or silently skipped. `report()` (used by
   the CLI's `report` subcommand) is discovery immediately followed by self-validation against
   the same calls -- convenient for "is this one capture internally consistent," but not a
   substitute for validating a later capture against an earlier, identified map.
3. `steno/span/manifest.py` defines two identity shapes: `DiscoveryManifest` (incomplete
   metadata allowed -- a tool catalogue or rule set may be `None`, meaning "not collected yet")
   and `DeployableBundle` (every field mandatory, including a pinned model revision and real
   tokenizer/template file hashes). See "Scope of B3" below.

## Scope of B3 (bundle identity), honestly

Build order step B3 asks for "mandatory bundle identity... enforced by proxy and dataset
builder." Wave 1 implemented the identity types and their validation
(`DiscoveryManifest`/`DeployableBundle` in `steno/span/manifest.py`, with `DeployableBundle`
requiring a pinned model revision, tokenizer hash and template hash before it validates) but did
not wire enforcement anywhere.

**Wave 2 adds enforcement, opt-in.** `steno/span/enforce.py` provides:

- `load_bundle(path)`: reads a bundle file (JSON; see the module docstring for the exact shape),
  reconstructs a `DeployableBundle`, validates every required identity field is present, and
  recomputes `bundle_sha` from the file's own content (including re-hashing the tokenizer and
  template files from their current bytes) to detect tampering or staleness. Raises on any
  problem; nothing recovers from a bad bundle silently.
- `check_request_against_bundle(call_record, bundle)`: a per-request check -- does this specific
  request's tool-catalogue hash and preamble structure match the cohort the bundle was pinned
  for? Returns `(ok, reasons)`.
- `legacy_map_status(segments_json)`: classifies an existing (pre-wave-2) segment map as
  `"legacy_hashless"` (no bundle identity recorded, the shape every map had before this wave) or
  `"identified"` (carries a `bundle_sha`).

Both `experiments/proxy/tap.py` (`--bundle <path>`) and `experiments/gist/dataset.py` (an
optional third `sys.argv` bundle-path argument) now call this. **Enforcement is opt-in**:
without `--bundle` / the bundle argument, both tools behave exactly as before -- legacy segment
maps keep working, nothing is checked against a bundle. With it:

- the tap refuses to start at all if `load_bundle()` raises (invalid or tampered bundle);
- per request, the tap only substitutes gist tokens when `check_request_against_bundle` passes;
  a failing request is forwarded in full, with the reason written to stderr and to the log
  record's `bundle_reject_reason` field;
- the dataset builder rejects (counts, does not silently drop) any example whose request fails
  the bundle check, before it ever reaches `build_example`.

What is still not done: nothing here computes a *real* `bundle_sha` end-to-end from an actual
served model's tokenizer/template files as part of a live pipeline (the tests and this doc's
examples build bundle files by hand); a model adapter that discovers and pins those paths
automatically is a later wave's work. B3 is now "identity defined, and both consumers named by
the design refuse to compress traffic that doesn't match a validated bundle when one is
supplied," not yet "the pipeline always requires one."

## The adapter contract

`steno/span/adapters/base.py` defines `HarnessAdapter` as a `Protocol`:

- `identity()`: name, version, capabilities.
- `wants(raw)`: is this captured record a model call this adapter analyses.
- `parse_request(raw) -> CallRecord`: the core parse.
- `response_decoder()`: an object with `.decode(raw_response, is_stream) -> (Reply, Usage)`.
- `rewrite_request(raw, new_preamble) -> raw`: the inverse of `parse_request`'s preamble
  extraction. Passing back the *unchanged* preamble must reproduce the original request (compare
  with `canonical_json`, not byte equality; key order is not semantically meaningful).
- `raw_value_rules() -> list[RawValueRule]`: the harness's declared per-session/per-call values
  that must never be compressed away.
- `launch` / `collect_result`: declared for contract stability across waves; this wave's
  adapters raise `NotImplementedError` since launching a harness is out of scope here.

Adapters must not import tokenizer, span-analysis or segment code, and are tested only against
golden fixtures (see Testing below).

## Onboarding a new harness

Following steno-design.md's "Onboarding a new harness" steps:

1. Capture at least three sessions of five or more turns through your relay, one from a
   different working directory or tool setup if you can arrange it.
2. Implement `HarnessAdapter` in a new module under `steno/span/adapters/`: `identity`,
   `wants`, `parse_request`, `response_decoder`, `rewrite_request`, `raw_value_rules`. Keep
   `launch`/`collect_result` raising `NotImplementedError` until a later wave needs them.
3. Write golden fixtures: a handful of sanitised, real-shaped raw capture lines plus the
   `CallRecord` fields you expect from them (see `tests/span/` for the pattern used for
   Claude Code). Assert the round trip: `rewrite_request(raw, parse_request(raw).preamble)`
   must equal `raw` under `steno.span.record.canonical_json`.
4. Run `python -m steno.span.cli report --harness <name> --captures <jsonl>` against a fresh
   capture. Every cohort should either pass, or fail for a reason you can name (missing rule,
   real bug). Add or fix raw-value rules until the only remaining failures are real gaps you are
   tracking, not false positives.
5. Register the adapter in `steno/span/cli.py`'s `ADAPTERS` mapping.

## Running the report

```
python -m steno.span.cli report   --harness claude-code --captures path/to/requests.jsonl --out report.json
python -m steno.span.cli discover --harness claude-code --captures path/to/requests.jsonl --out map.json
python -m steno.span.cli validate --harness claude-code --captures path/to/another.jsonl --map map.json --out report.json
```

`report` discovers and self-validates in one step; prints a short summary (cohorts, unresolved
ranges, capture outcomes, overall PASS/FAIL) and, with `--out`, writes the full JSON report,
including a `capture_outcomes` block accounting for every selected capture. `discover` freezes a
segment map to disk; `validate` checks a *different* capture against that frozen map (the actual
onboarding-packet workflow: discover once on a large capture, then validate every later capture
against the frozen result). The process exits non-zero whenever the analysis fails, or when any
selected capture produced a `parse_error` -- an unexplained exclusion fails the run.

## Running the tests

```
/Users/arunmenon/projects/gisting/experiments/.venv/bin/python -m pytest tests/span -q
```

`tests/span/fixtures/claude_code_captures.jsonl` is a small (12-line) sanitised fixture derived
from a real local capture (`experiments/journeys/j1-e0-tap/results/requests.jsonl`): usernames,
session ids, the source device id, request ids and tool-use ids are all replaced with synthetic
values (the same source id always maps to the same synthetic id, so relationships such as "these
turns share a session" survive), large text blocks are truncated, and the tool catalogue is
trimmed to 5 entries. `tests/span/test_fixture_hygiene.py` scans the fixture for any identifier
still present in the source capture (skipped if that source file is not available locally) and
for em dashes, so a future edit cannot silently reintroduce either. This fixture is safe to
commit; it is not a substitute for running the CLI against a real, uncommitted capture before
trusting an adapter.

## Known gaps (see also `analysis.known_gaps()`)

- Comparison is line-granular, matching the line-oriented raw-value rules; a varying run that
  does not align to a whole line is not separately analysed within that line.
- Token counting goes through `analysis.character_count()`, a placeholder. A model adapter (a
  later wave) should replace call sites of it with real token counts; nothing here assumes
  characters and tokens are interchangeable.
- Session-consistency classification trusts that a given `session_id` came from one run; it does
  not detect a session id accidentally reused across unrelated captures.
- Bundle-identity enforcement is opt-in, not mandatory, and no pipeline yet requires a bundle to
  run at all; see "Scope of B3" above.
- `validate()`'s per-line check assumes a call's part has the same number of lines as the frozen
  map; a structural change (lines inserted or removed) is reported as a line-count mismatch
  rather than being re-aligned.
