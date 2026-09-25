import copy
import json
import os
import sys

import pytest

from steno.span.adapters.claude_code import ClaudeCodeAdapter
from steno.span.enforce import (
    _enforced_sha,
    bind_segments_to_bundle,
    bind_tokenizer_to_bundle,
    check_request_against_bundle,
    legacy_map_status,
    load_bundle,
)
from steno.span.manifest import DeployableBundle

PROXY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "experiments", "proxy")
DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "experiments", "gist")


def _write_file(path, content=b"identity-file-bytes"):
    with open(path, "wb") as handle:
        handle.write(content)
    return str(path)


def _bundle_dict(tmp_path, tokenizer_path=None, template_path=None, **overrides):
    """A valid bundle file's contents, matching steno.span.enforce's documented file shape,
    before any deliberate corruption a test wants to apply."""
    tokenizer_path = tokenizer_path or _write_file(tmp_path / "tokenizer.bin")
    template_path = template_path or _write_file(tmp_path / "template.jinja", b"{{ chat template }}")
    data = dict(
        harness_adapter_name="claude-code",
        harness_adapter_version="claude-code/1.0.0",
        model_id="Qwen/Qwen3.8-27B",
        model_revision="qwen3.8-27b-rev-1",
        tool_catalogue=[{"name": "Read", "description": "reads a file", "schema": {}, "extra": {}}],
        raw_value_rules=[{"name": "verbatim_line", "pattern": "x", "description": "d"}],
        tokenizer_path=tokenizer_path,
        template_path=template_path,
        instruction_structure=["system[0]"],
    )
    data.update(overrides)
    bundle = DeployableBundle(
        harness_adapter_name=data["harness_adapter_name"],
        harness_adapter_version=data["harness_adapter_version"],
        model_id=data["model_id"],
        model_revision=data["model_revision"],
        tool_catalogue=data["tool_catalogue"],
        raw_value_rules=data["raw_value_rules"],
        tokenizer_path=data["tokenizer_path"],
        template_path=data["template_path"],
    )
    data["bundle_sha"] = bundle.bundle_sha
    data["enforced_sha"] = _enforced_sha(bundle.bundle_sha, data["instruction_structure"])
    return data


def _write_bundle(tmp_path, data, name="bundle.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return str(path)


# --------------------------------------------------------------------------------------
# load_bundle
# --------------------------------------------------------------------------------------

def test_valid_bundle_loads(tmp_path):
    data = _bundle_dict(tmp_path)
    path = _write_bundle(tmp_path, data)
    bundle = load_bundle(path)
    assert isinstance(bundle, DeployableBundle)
    assert bundle.bundle_sha == data["bundle_sha"]
    assert bundle.instruction_structure == ["system[0]"]


@pytest.mark.parametrize("missing_field,value", [
    ("harness_adapter_name", ""),
    ("model_id", ""),
    ("model_revision", ""),
    ("tool_catalogue", None),
    ("raw_value_rules", None),
])
def test_missing_identity_field_rejected(tmp_path, missing_field, value):
    data = _bundle_dict(tmp_path)
    data[missing_field] = value
    # bundle_sha was computed for the *valid* version; recompute isn't needed since validate()
    # (checked before the bundle_sha comparison) must raise first.
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError):
        load_bundle(path)


def test_missing_tokenizer_path_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    data["tokenizer_path"] = None
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError):
        load_bundle(path)


def test_missing_template_path_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    data["template_path"] = None
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError):
        load_bundle(path)


def test_tampered_bundle_sha_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    # Mutate an identity field without updating the recorded bundle_sha: this is exactly what a
    # hand-edited or corrupted bundle file looks like.
    data["model_id"] = "Qwen/Qwen3.8-27B-tampered"
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError, match="tampered"):
        load_bundle(path)


def test_tampered_tokenizer_file_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    path = _write_bundle(tmp_path, data)
    # Edit the tokenizer file's bytes after the bundle_sha was recorded: load_bundle re-hashes
    # from the current file contents, so this must also be caught as tampering.
    _write_file(data["tokenizer_path"], b"different-bytes-now")
    with pytest.raises(ValueError, match="tampered"):
        load_bundle(path)


# --------------------------------------------------------------------------------------
# X-5: instruction_structure is required and authenticated (enforced_sha)
# --------------------------------------------------------------------------------------

def test_missing_instruction_structure_key_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    del data["instruction_structure"]  # deleting the field entirely must not silently become []
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError, match="instruction_structure"):
        load_bundle(path)


def test_missing_enforced_sha_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    del data["enforced_sha"]
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError, match="enforced_sha"):
        load_bundle(path)


def test_tampered_instruction_structure_rejected(tmp_path):
    data = _bundle_dict(tmp_path)
    # Edit instruction_structure without updating enforced_sha: exactly what the review's offline
    # probe did to turn a rejected request into an accepted one before this fix.
    data["instruction_structure"] = []
    path = _write_bundle(tmp_path, data)
    with pytest.raises(ValueError, match="enforced_sha"):
        load_bundle(path)


def test_empty_instruction_structure_is_loaded_and_authenticated(tmp_path):
    data = _bundle_dict(tmp_path, instruction_structure=[])
    path = _write_bundle(tmp_path, data)
    bundle = load_bundle(path)
    assert bundle.instruction_structure == []


# --------------------------------------------------------------------------------------
# check_request_against_bundle
# --------------------------------------------------------------------------------------

def _call_and_bundle_for(fixture_raws, tmp_path):
    raw = fixture_raws[0]
    call = ClaudeCodeAdapter().parse_request(raw)
    data = _bundle_dict(
        tmp_path,
        tool_catalogue=call.to_dict()["tools"],
        instruction_structure=[part.source for part in call.preamble],
    )
    path = _write_bundle(tmp_path, data)
    return raw, call, load_bundle(path)


def test_matching_request_passes(fixture_raws, tmp_path):
    _, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    ok, reasons = check_request_against_bundle(call, bundle)
    assert ok is True
    assert reasons == []


def test_changed_catalogue_fails(fixture_raws, tmp_path):
    raw, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    tampered_raw = copy.deepcopy(raw)
    tampered_raw["request"]["tools"] = (tampered_raw["request"].get("tools") or []) + [
        {"name": "NewTool", "description": "not in the bundle", "input_schema": {}}
    ]
    tampered_call = ClaudeCodeAdapter().parse_request(tampered_raw)
    ok, reasons = check_request_against_bundle(tampered_call, bundle)
    assert ok is False
    assert any("catalogue" in reason for reason in reasons)


def test_changed_instruction_structure_fails(fixture_raws, tmp_path):
    _, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    bundle.instruction_structure = ["system[0]", "system[99]"]  # does not match call's real structure
    ok, reasons = check_request_against_bundle(call, bundle)
    assert ok is False
    assert any("structure" in reason for reason in reasons)


def test_empty_expected_structure_is_compared_not_skipped(fixture_raws, tmp_path):
    # X-5 regression: an empty bundle.instruction_structure used to short-circuit the comparison
    # (a falsy "expected" meant "nothing to check"). A real call with any preamble parts against
    # such a bundle must be reported as a mismatch, not silently passed.
    _, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    bundle.instruction_structure = []
    assert call.preamble  # the fixture call actually has preamble parts
    ok, reasons = check_request_against_bundle(call, bundle)
    assert ok is False
    assert any("structure" in reason for reason in reasons)


# --------------------------------------------------------------------------------------
# legacy_map_status
# --------------------------------------------------------------------------------------

def test_legacy_map_classified_hashless():
    segments_json = {"ratio": 8, "tools_hash": "abc123", "segments": []}
    assert legacy_map_status(segments_json) == "legacy_hashless"


def test_legacy_map_classified_identified():
    segments_json = {"ratio": 8, "tools_hash": "abc123", "segments": [], "bundle_sha": "deadbeef"}
    assert legacy_map_status(segments_json) == "identified"


def test_legacy_map_classified_unrecognisable_shape():
    assert legacy_map_status(None) == "legacy_hashless"
    assert legacy_map_status("not even a dict") == "legacy_hashless"


# --------------------------------------------------------------------------------------
# tap.py's bundle gate (request-rewrite function), exercised directly, no network
# --------------------------------------------------------------------------------------

def _import_tap():
    if PROXY_DIR not in sys.path:
        sys.path.insert(0, PROXY_DIR)
    import tap  # noqa: E402
    return tap


def test_tap_bundle_gate_passes_matching_request(fixture_raws, tmp_path):
    raw, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    tap = _import_tap()
    tap.BUNDLE = bundle
    try:
        ok, reason = tap.check_request_bundle_gate(raw["request"])
    finally:
        tap.BUNDLE = None
    assert ok is True
    assert reason == "ok"


def test_tap_bundle_gate_rejects_changed_catalogue(fixture_raws, tmp_path):
    raw, call, bundle = _call_and_bundle_for(fixture_raws, tmp_path)
    tampered_request = copy.deepcopy(raw["request"])
    tampered_request["tools"] = (tampered_request.get("tools") or []) + [
        {"name": "NewTool", "description": "not in the bundle", "input_schema": {}}
    ]
    tap = _import_tap()
    tap.BUNDLE = bundle
    try:
        ok, reason = tap.check_request_bundle_gate(tampered_request)
    finally:
        tap.BUNDLE = None
    assert ok is False
    assert "catalogue" in reason


# --------------------------------------------------------------------------------------
# X-4: bind_segments_to_bundle / bind_tokenizer_to_bundle (unit level)
# --------------------------------------------------------------------------------------

def test_bind_segments_to_bundle_rejects_legacy_map(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    legacy_segments = {"ratio": 8, "tools_hash": "abc123", "segments": []}
    ok, reasons = bind_segments_to_bundle(legacy_segments, bundle)
    assert ok is False
    assert any("legacy_hashless" in reason for reason in reasons)


def test_bind_segments_to_bundle_accepts_matching_identified_map(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    bound_segments = {
        "ratio": 8, "segments": [], "bundle_sha": bundle.bundle_sha,
        "harness_adapter_name": bundle.harness_adapter_name,
        "harness_adapter_version": bundle.harness_adapter_version,
    }
    ok, reasons = bind_segments_to_bundle(bound_segments, bundle)
    assert ok is True
    assert reasons == []


def test_bind_segments_to_bundle_rejects_map_stamped_for_a_different_bundle(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    other_data = _bundle_dict(tmp_path, model_id="Qwen/Qwen3.8-27B-other")
    other_bundle = load_bundle(_write_bundle(tmp_path, other_data, name="other_bundle.json"))
    mismatched_segments = {
        "ratio": 8, "segments": [], "bundle_sha": other_bundle.bundle_sha,
        "harness_adapter_name": other_bundle.harness_adapter_name,
        "harness_adapter_version": other_bundle.harness_adapter_version,
    }
    ok, reasons = bind_segments_to_bundle(mismatched_segments, bundle)
    assert ok is False
    assert any("bundle_sha" in reason for reason in reasons)


def test_bind_tokenizer_to_bundle_accepts_matching_file(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    ok, reason = bind_tokenizer_to_bundle(data["tokenizer_path"], bundle)
    assert ok is True
    assert reason == "ok"


def test_bind_tokenizer_to_bundle_rejects_mismatched_file(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    other_tokenizer = _write_file(tmp_path / "other_tokenizer.bin", b"not the bundle's tokenizer")
    ok, reason = bind_tokenizer_to_bundle(other_tokenizer, bundle)
    assert ok is False
    assert "tokenizer_hash" in reason


# --------------------------------------------------------------------------------------
# X-4: end-to-end mismatch tests, tap and dataset
# --------------------------------------------------------------------------------------

def test_tap_refuses_to_start_on_legacy_segment_map(tmp_path):
    """A valid bundle plus a legacy (hashless) segments.json: the tap must refuse the map, not
    trust it because --bundle loaded cleanly. Exercises tap.check_segments_bound_to_bundle
    directly (the function main() calls before serving), no network, no server started."""
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    tap = _import_tap()
    legacy_raw_spec = {"ratio": 8, "tools_hash": "abc123", "segments": []}
    ok, reason = tap.check_segments_bound_to_bundle(legacy_raw_spec, bundle)
    assert ok is False
    assert "legacy_hashless" in reason


def test_tap_refuses_to_start_on_segment_map_for_a_different_bundle(tmp_path):
    data = _bundle_dict(tmp_path)
    bundle = load_bundle(_write_bundle(tmp_path, data))
    other_data = _bundle_dict(tmp_path, model_id="Qwen/Qwen3.8-27B-other")
    other_bundle = load_bundle(_write_bundle(tmp_path, other_data, name="other_bundle.json"))
    tap = _import_tap()
    mismatched_raw_spec = {
        "ratio": 8, "segments": [], "bundle_sha": other_bundle.bundle_sha,
        "harness_adapter_name": other_bundle.harness_adapter_name,
        "harness_adapter_version": other_bundle.harness_adapter_version,
    }
    ok, reason = tap.check_segments_bound_to_bundle(mismatched_raw_spec, bundle)
    assert ok is False
    assert "bundle_sha" in reason


def _make_gist_out(tmp_path, segments_extra=None):
    gist_out = tmp_path / "gist_out"
    tokenizer_dir = gist_out / "tokenizer"
    tokenizer_dir.mkdir(parents=True, exist_ok=True)
    tokenizer_file = tokenizer_dir / "tokenizer.json"
    if not tokenizer_file.exists():
        tokenizer_file.write_bytes(b"tokenizer-bytes-for-dataset-binding-test")
    segments = {"ratio": 8, "tools_hash": "abc123", "segments": []}
    if segments_extra:
        segments.update(segments_extra)
    (gist_out / "segments.json").write_text(json.dumps(segments))
    return str(gist_out), str(tokenizer_file)


def _import_dataset(monkeypatch, gist_out):
    monkeypatch.setenv("GIST_OUT", gist_out)
    sys.modules.pop("dataset", None)
    sys.modules.pop("span", None)
    if DATASET_DIR not in sys.path:
        sys.path.insert(0, DATASET_DIR)
    import dataset  # noqa: E402 -- reads GIST_OUT at import time, must happen after setenv+pop
    return dataset


def test_dataset_refuses_bundle_with_legacy_segments(monkeypatch, tmp_path):
    gist_out, tokenizer_file = _make_gist_out(tmp_path)  # no bundle_sha: legacy_hashless
    dataset = _import_dataset(monkeypatch, gist_out)

    data = _bundle_dict(tmp_path, tokenizer_path=tokenizer_file)
    bundle_path = _write_bundle(tmp_path, data)

    with pytest.raises(ValueError, match="not bound"):
        dataset.load_bundle_context(bundle_path)


def test_dataset_refuses_bundle_with_mismatched_tokenizer(monkeypatch, tmp_path):
    data = _bundle_dict(tmp_path)  # tokenizer_path is its own tmp file, not the dataset's tokenizer.json
    bundle = load_bundle(_write_bundle(tmp_path, data))
    gist_out, _ = _make_gist_out(tmp_path, segments_extra={
        "bundle_sha": bundle.bundle_sha,
        "harness_adapter_name": bundle.harness_adapter_name,
        "harness_adapter_version": bundle.harness_adapter_version,
    })
    dataset = _import_dataset(monkeypatch, gist_out)

    with pytest.raises(ValueError, match="tokenizer"):
        dataset.load_bundle_context(_write_bundle(tmp_path, data, name="bundle2.json"))


def test_dataset_accepts_bundle_bound_to_its_own_segments_and_tokenizer(monkeypatch, tmp_path):
    gist_out, tokenizer_file = _make_gist_out(tmp_path)
    data = _bundle_dict(tmp_path, tokenizer_path=tokenizer_file)
    bundle = DeployableBundle(
        harness_adapter_name=data["harness_adapter_name"], harness_adapter_version=data["harness_adapter_version"],
        model_id=data["model_id"], model_revision=data["model_revision"],
        tool_catalogue=data["tool_catalogue"], raw_value_rules=data["raw_value_rules"],
        tokenizer_path=data["tokenizer_path"], template_path=data["template_path"],
    )
    gist_out, tokenizer_file = _make_gist_out(tmp_path, segments_extra={
        "bundle_sha": bundle.bundle_sha,
        "harness_adapter_name": bundle.harness_adapter_name,
        "harness_adapter_version": bundle.harness_adapter_version,
    })
    dataset = _import_dataset(monkeypatch, gist_out)
    bundle_path = _write_bundle(tmp_path, data, name="bound_bundle.json")

    loaded_bundle, gate = dataset.load_bundle_context(bundle_path)
    assert loaded_bundle.bundle_sha == bundle.bundle_sha
    assert callable(gate)
