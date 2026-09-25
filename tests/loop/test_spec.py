import pytest

from steno.loop.spec import SpecValidationError, spec_from_dict


def valid_spec_dict():
    return {
        "schema": "steno-run/v1",
        "pair": "pairs/claude-code-qwen38.yaml",
        "inputs": {"captures": "sha256:abc", "tasks": "sha256:def"},
        "stages": ["span", "data", "train", "serve", "evaluate", "benchmark"],
        "budget": {"max_usd": 40, "max_hours": 8, "min_credit": 30, "cleanup_reserve_usd": 5, "max_attempts_per_stage": 2},
        "gates": {"span": {"share_min": 0.25}},
        "compute": {"backend": "vast"},
        "artifacts": {"store": "journeys/j-x/results", "emergency_policy": "terminate_and_record_loss"},
    }


def test_valid_spec_passes():
    spec = spec_from_dict(valid_spec_dict())
    spec.validate()  # must not raise


def test_wrong_schema_rejected():
    document = valid_spec_dict()
    document["schema"] = "steno-run/v2"
    with pytest.raises(SpecValidationError, match="unsupported schema"):
        spec_from_dict(document).validate()


def test_missing_pair_rejected():
    document = valid_spec_dict()
    document["pair"] = ""
    with pytest.raises(SpecValidationError, match="pair"):
        spec_from_dict(document).validate()


def test_span_must_be_first_stage():
    # span (index 1 in KNOWN_STAGE_ORDER) appearing after data (index 2) is
    # caught by the general ordering rule, which is exactly how "span must be
    # first" is enforced: nothing in KNOWN_STAGE_ORDER can legally precede it
    # except preflight.
    document = valid_spec_dict()
    document["stages"] = ["data", "span", "train"]
    with pytest.raises(SpecValidationError, match="order"):
        spec_from_dict(document).validate()


def test_span_after_preflight_is_fine():
    document = valid_spec_dict()
    document["stages"] = ["preflight", "span", "data"]
    spec_from_dict(document).validate()  # must not raise


def test_unknown_stage_rejected():
    document = valid_spec_dict()
    document["stages"] = ["span", "teleport"]
    with pytest.raises(SpecValidationError, match="unknown stage"):
        spec_from_dict(document).validate()


def test_duplicate_stage_rejected():
    document = valid_spec_dict()
    document["stages"] = ["span", "data", "data"]
    with pytest.raises(SpecValidationError, match="more than once"):
        spec_from_dict(document).validate()


def test_out_of_order_stage_rejected():
    document = valid_spec_dict()
    document["stages"] = ["train", "data"]
    with pytest.raises(SpecValidationError, match="order"):
        spec_from_dict(document).validate()


def test_empty_stages_rejected():
    document = valid_spec_dict()
    document["stages"] = []
    with pytest.raises(SpecValidationError, match="non-empty"):
        spec_from_dict(document).validate()


@pytest.mark.parametrize("field_name", ["max_usd", "max_hours", "min_credit", "cleanup_reserve_usd"])
def test_missing_budget_field_rejected(field_name):
    document = valid_spec_dict()
    del document["budget"][field_name]
    with pytest.raises(SpecValidationError, match=field_name):
        spec_from_dict(document).validate()


@pytest.mark.parametrize("field_name", ["max_usd", "max_hours", "min_credit", "cleanup_reserve_usd"])
def test_non_positive_budget_field_rejected(field_name):
    document = valid_spec_dict()
    document["budget"][field_name] = 0
    with pytest.raises(SpecValidationError, match="positive"):
        spec_from_dict(document).validate()


def test_cleanup_reserve_must_be_below_max_usd():
    document = valid_spec_dict()
    document["budget"]["cleanup_reserve_usd"] = 40
    document["budget"]["max_usd"] = 40
    with pytest.raises(SpecValidationError, match="cleanup_reserve_usd"):
        spec_from_dict(document).validate()


def test_max_attempts_per_stage_must_be_positive_int():
    document = valid_spec_dict()
    document["budget"]["max_attempts_per_stage"] = 0
    with pytest.raises(SpecValidationError, match="max_attempts_per_stage"):
        spec_from_dict(document).validate()


def test_missing_artifact_store_rejected():
    document = valid_spec_dict()
    document["artifacts"] = {"emergency_policy": "terminate_and_record_loss"}
    with pytest.raises(SpecValidationError, match="artifacts.store"):
        spec_from_dict(document).validate()


def test_unsupported_emergency_policy_rejected():
    document = valid_spec_dict()
    document["artifacts"]["emergency_policy"] = "shrug_and_hope"
    with pytest.raises(SpecValidationError, match="emergency_policy"):
        spec_from_dict(document).validate()


def test_missing_emergency_policy_rejected():
    document = valid_spec_dict()
    del document["artifacts"]["emergency_policy"]
    with pytest.raises(SpecValidationError, match="emergency_policy"):
        spec_from_dict(document).validate()


def test_dependent_stage_without_span_rejected():
    document = valid_spec_dict()
    document["stages"] = ["train"]
    with pytest.raises(SpecValidationError, match="require a span stage"):
        spec_from_dict(document).validate()


def test_evaluate_without_span_rejected():
    document = valid_spec_dict()
    document["stages"] = ["data", "evaluate"]
    with pytest.raises(SpecValidationError, match="require a span stage"):
        spec_from_dict(document).validate()


def test_data_only_stage_does_not_require_span():
    document = valid_spec_dict()
    document["stages"] = ["data"]
    spec_from_dict(document).validate()  # must not raise: data alone has no span dependency


def test_unsupported_gate_rejected():
    document = valid_spec_dict()
    document["gates"] = {"data": {"whatever": 1}}
    with pytest.raises(SpecValidationError, match="unsupported gate"):
        spec_from_dict(document).validate()


def test_missing_required_input_key_rejected():
    document = valid_spec_dict()
    document["inputs"] = {"captures": "sha256:abc"}  # tasks missing
    with pytest.raises(SpecValidationError, match="missing required key"):
        spec_from_dict(document).validate()


def test_empty_inputs_rejected():
    document = valid_spec_dict()
    document["inputs"] = {}
    with pytest.raises(SpecValidationError, match="non-empty"):
        spec_from_dict(document).validate()


def test_identity_digest_stable_and_sensitive_to_inputs():
    document = valid_spec_dict()
    spec_a = spec_from_dict(document)
    spec_b = spec_from_dict(dict(document))
    assert spec_a.identity_digest() == spec_b.identity_digest()

    changed = valid_spec_dict()
    changed["inputs"]["captures"] = "sha256:different"
    spec_c = spec_from_dict(changed)
    assert spec_c.identity_digest() != spec_a.identity_digest()


def test_json_file_round_trips_without_pyyaml_dependency(tmp_path):
    import json

    from steno.loop.spec import load_spec

    document = valid_spec_dict()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(document))
    spec = load_spec(str(spec_path))
    spec.validate()
    assert spec.pair == document["pair"]
