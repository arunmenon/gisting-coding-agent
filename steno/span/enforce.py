"""Bundle enforcement: the B3 half that `steno/span/manifest.py` deliberately left undone.

`manifest.py` defines `DeployableBundle` (every identity field mandatory) and can validate one
in memory, but nothing reads a bundle off disk, checks it for tampering, or checks a live
request against it. This module is that wiring, kept separate from `manifest.py` so the identity
*shape* and its *enforcement* stay independently testable, per steno-design.md and
`steno/span/README.md`'s "Scope of B3" section.

## Bundle file format

A bundle file is JSON holding everything needed to reconstruct a `DeployableBundle` plus the
authenticated identity recorded when the file was written:

    {
      "harness_adapter_name": "...", "harness_adapter_version": "...",
      "model_id": "...", "model_revision": "...",
      "tool_catalogue": [...], "raw_value_rules": [...],
      "tokenizer_path": "...", "template_path": "...",
      "instruction_structure": ["system[0]", "system[1]", ...],
      "bundle_sha": "<DeployableBundle.bundle_sha recorded at write time>",
      "enforced_sha": "<sha256 of {bundle_sha, instruction_structure} recorded at write time>"
    }

`tool_catalogue` / `raw_value_rules` are the raw collected lists (not just their hashes) so
`load_bundle` can recompute every hash, including `bundle_sha`, from the file's own content and
compare it against the recorded `bundle_sha`: any edit to a hash field, to `tool_catalogue`, to
`raw_value_rules`, or to the tokenizer/template file's bytes (re-hashed from `tokenizer_path` /
`template_path` at load time, not trusted from the file) changes the recomputed `bundle_sha` and
is caught as tampering.

`instruction_structure` is not part of `DeployableBundle` in `manifest.py`, so it is not covered
by `bundle_sha`. It records the preamble-part `source` sequence
(`CallRecord.preamble[i].source`, matching `steno.span.analysis._cohort_key`'s structure
component) that this bundle's cohort was built against. Because it sits outside `bundle_sha`, it
gets its own authenticated hash, `enforced_sha`, computed over `{bundle_sha, instruction_structure}`.
`instruction_structure` is a **required** key (it may legitimately be an empty list -- a cohort
with zero preamble parts is a real state -- but the key must be present), and `load_bundle`
requires `enforced_sha` to match a freshly recomputed value: deleting `instruction_structure`,
or editing it without updating `enforced_sha`, is rejected exactly like a `bundle_sha` mismatch
(W-X5). `check_request_against_bundle` then compares a live request's structure against
`bundle.instruction_structure` unconditionally, including when it is empty, rather than skipping
the comparison whenever the expected value happens to be falsy.

## What "enforcement" means here

Per steno-design.md, a proxy or dataset builder must refuse to compress traffic against an
unpinned or tampered bundle, and must only compress a specific request when that request is
actually consistent with the bundle's cohort. A valid, untampered bundle is still not enough on
its own (W-X4): the *artifacts actually used to compress a request* -- the segment map handing
out gist tokens, and (for the dataset builder) the tokenizer used to render/encode -- must
themselves be shown to be the ones this bundle identifies, not merely loaded alongside it. This
module covers all three checks:

- `load_bundle` refuses to start on a bad bundle (missing fields, tampering).
- `bind_segments_to_bundle` refuses to use a segment map that is not authenticated against the
  loaded bundle: a legacy (hashless) map is always rejected in enforcement mode, and an
  identified map must carry the bundle's own `bundle_sha` and matching adapter identity.
- `bind_tokenizer_to_bundle` refuses to use a tokenizer file that does not hash to the bundle's
  recorded `tokenizer_hash`.
- `check_request_against_bundle` refuses to substitute for a request that does not match the
  bundle's cohort, per request, even once the map and tokenizer are both bound correctly.
"""
from __future__ import annotations

import json
from typing import Any, List, Tuple

from .manifest import DeployableBundle, _hash_file
from .record import CallRecord, sha256_of


def _enforced_sha(bundle_sha: str, instruction_structure: List[str]) -> str:
    return sha256_of({"bundle_sha": bundle_sha, "instruction_structure": list(instruction_structure)})


def load_bundle(path: str) -> DeployableBundle:
    """Loads a bundle file, reconstructs a `DeployableBundle` from its raw fields (recomputing
    every hash, including file hashes for the tokenizer/template from their *current* on-disk
    bytes), validates every required identity field is present, and rejects the bundle if the
    freshly recomputed `bundle_sha` (or `enforced_sha`, covering `instruction_structure`) does not
    match what was recorded in the file (tampering, staleness, or a deleted field). Raises
    `ValueError` (missing fields, tampering) or `FileNotFoundError` (tokenizer/template path does
    not exist) -- both are meant to be fatal to a caller deciding whether to serve or train
    against this bundle."""
    with open(path) as handle:
        data = json.load(handle)

    if "instruction_structure" not in data:
        raise ValueError(
            "bundle file missing instruction_structure: this field is required (it may be an "
            "empty list, but the key must be present) so its absence can never silently disable "
            "the instruction-structure check"
        )
    instruction_structure = data["instruction_structure"]
    if not isinstance(instruction_structure, list) or not all(isinstance(item, str) for item in instruction_structure):
        raise ValueError("bundle file's instruction_structure must be a list of strings")

    bundle = DeployableBundle(
        harness_adapter_name=data.get("harness_adapter_name", ""),
        harness_adapter_version=data.get("harness_adapter_version", ""),
        model_id=data.get("model_id", ""),
        model_revision=data.get("model_revision", ""),
        tool_catalogue=data.get("tool_catalogue"),
        raw_value_rules=data.get("raw_value_rules"),
        tokenizer_path=data.get("tokenizer_path"),
        template_path=data.get("template_path"),
    )
    bundle.validate()  # raises ValueError naming every missing required identity field

    recorded_sha = data.get("bundle_sha")
    if not recorded_sha:
        raise ValueError("bundle file missing bundle_sha: cannot verify it has not been tampered with")
    if recorded_sha != bundle.bundle_sha:
        raise ValueError(
            "bundle tampered or stale: recorded bundle_sha=%s does not match recomputed bundle_sha=%s "
            "(a hash field, tool_catalogue, raw_value_rules, or the tokenizer/template file's bytes "
            "changed since this bundle file was written)" % (recorded_sha, bundle.bundle_sha)
        )

    recorded_enforced_sha = data.get("enforced_sha")
    fresh_enforced_sha = _enforced_sha(bundle.bundle_sha, instruction_structure)
    if not recorded_enforced_sha:
        raise ValueError("bundle file missing enforced_sha: instruction_structure is not authenticated")
    if recorded_enforced_sha != fresh_enforced_sha:
        raise ValueError(
            "bundle tampered or stale: recorded enforced_sha=%s does not match recomputed enforced_sha=%s "
            "(instruction_structure changed since this bundle file was written, without updating enforced_sha)"
            % (recorded_enforced_sha, fresh_enforced_sha)
        )

    bundle.instruction_structure = list(instruction_structure)
    return bundle


def check_request_against_bundle(call_record: CallRecord, bundle: DeployableBundle) -> Tuple[bool, List[str]]:
    """Checks one parsed request against an already-loaded, already-validated bundle: does its
    tool catalogue hash match the bundle's, and does its preamble structure match the cohort the
    bundle declares? Returns (ok, reasons); an empty reasons list iff ok is True. This is a
    per-request check, called on every request a proxy or dataset builder considers compressing
    -- a valid bundle does not mean every request against it is safe to compress, only that the
    identity it was pinned for is trustworthy.

    The instruction-structure comparison is unconditional (W-X5): an empty `bundle.
    instruction_structure` is a real, meaningful expectation ("this cohort has zero preamble
    parts"), not "nothing to check," so a live request with any preamble parts against such a
    bundle is correctly reported as a mismatch rather than silently passed."""
    reasons: List[str] = []

    live_catalogue_hash = call_record.catalogue_hash()
    if live_catalogue_hash != bundle.tool_catalogue_hash:
        reasons.append(
            "tool catalogue hash mismatch: request=%s bundle=%s"
            % (live_catalogue_hash, bundle.tool_catalogue_hash)
        )

    expected_structure = tuple(getattr(bundle, "instruction_structure", None) or ())
    live_structure = tuple(part.source for part in call_record.preamble)
    if live_structure != expected_structure:
        reasons.append(
            "instruction structure mismatch: request=%s bundle=%s" % (list(live_structure), list(expected_structure))
        )

    return (not reasons, reasons)


def legacy_map_status(segments_json: Any) -> str:
    """Classifies an existing segment map (the shape `experiments/gist/segments.py` writes to
    `segments.json`) as `"legacy_hashless"` (no bundle identity was recorded -- every map
    produced before this wave) or `"identified"` (it carries a `bundle_sha`, meaning it was
    produced against, or later stamped with, a real `DeployableBundle`). This never raises: an
    unrecognisable shape is treated as legacy, since the whole point is to flag "this map cannot
    prove what it was built against," not to require a specific schema."""
    if isinstance(segments_json, dict) and segments_json.get("bundle_sha"):
        return "identified"
    return "legacy_hashless"


def bind_segments_to_bundle(segments_json: Any, bundle: DeployableBundle) -> Tuple[bool, List[str]]:
    """Checks that the segment map actually being used to hand out gist tokens is the one this
    bundle identifies (W-X4): a valid, untampered bundle says nothing about which map a caller
    loaded next to it, so this must be checked explicitly, every time enforcement is on. A legacy
    (hashless) map is always rejected in enforcement mode, regardless of whether its content
    happens to be compatible -- it carries no proof either way. Returns (ok, reasons)."""
    reasons: List[str] = []
    if legacy_map_status(segments_json) == "legacy_hashless":
        reasons.append("segment map is legacy_hashless: it carries no bundle identity and is rejected when enforcement is enabled")
        return False, reasons

    if segments_json.get("bundle_sha") != bundle.bundle_sha:
        reasons.append(
            "segment map bundle_sha=%s does not match loaded bundle_sha=%s"
            % (segments_json.get("bundle_sha"), bundle.bundle_sha)
        )
    if segments_json.get("harness_adapter_name") != bundle.harness_adapter_name:
        reasons.append(
            "segment map harness_adapter_name=%r does not match bundle harness_adapter_name=%r"
            % (segments_json.get("harness_adapter_name"), bundle.harness_adapter_name)
        )
    if segments_json.get("harness_adapter_version") != bundle.harness_adapter_version:
        reasons.append(
            "segment map harness_adapter_version=%r does not match bundle harness_adapter_version=%r"
            % (segments_json.get("harness_adapter_version"), bundle.harness_adapter_version)
        )
    return (not reasons, reasons)


def bind_tokenizer_to_bundle(tokenizer_file_path: str, bundle: DeployableBundle) -> Tuple[bool, str]:
    """Checks that a tokenizer file actually loaded for rendering/encoding hashes to the bundle's
    recorded `tokenizer_hash` (W-X4): loading *some* tokenizer next to a valid bundle proves
    nothing about whether it is the one the bundle pins. Returns (ok, reason); raises
    `FileNotFoundError` if `tokenizer_file_path` does not exist, since that is itself fatal to a
    caller about to rely on this tokenizer."""
    live_hash = _hash_file(tokenizer_file_path)
    if live_hash != bundle.tokenizer_hash:
        return False, "tokenizer file %s hashes to %s, bundle requires tokenizer_hash=%s" % (
            tokenizer_file_path, live_hash, bundle.tokenizer_hash,
        )
    return True, "ok"
