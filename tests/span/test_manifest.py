import pytest

from steno.span.manifest import DeployableBundle, DiscoveryManifest


def make_discovery(**overrides):
    kwargs = dict(
        harness_adapter_name="claude-code",
        harness_adapter_version="claude-code/1.0.0",
        model_id="Qwen/Qwen3.8-27B",
        tool_catalogue=[{"name": "Read", "description": "reads a file", "schema": {}, "extra": {}}],
        raw_value_rules=[{"name": "verbatim_line", "pattern": "x", "description": "d"}],
    )
    kwargs.update(overrides)
    return DiscoveryManifest(**kwargs)


def make_deployable(tokenizer_path=None, template_path=None, **overrides):
    kwargs = dict(
        harness_adapter_name="claude-code",
        harness_adapter_version="claude-code/1.0.0",
        model_id="Qwen/Qwen3.8-27B",
        model_revision="qwen3.8-27b-rev-1",
        tool_catalogue=[{"name": "Read", "description": "reads a file", "schema": {}, "extra": {}}],
        raw_value_rules=[{"name": "verbatim_line", "pattern": "x", "description": "d"}],
        tokenizer_path=tokenizer_path,
        template_path=template_path,
    )
    kwargs.update(overrides)
    return DeployableBundle(**kwargs)


# --- DiscoveryManifest: incomplete metadata is expected, not an error ---

def test_discovery_manifest_validate_passes_with_only_identity():
    manifest = DiscoveryManifest(
        harness_adapter_name="claude-code", harness_adapter_version="claude-code/1.0.0",
        model_id="Qwen/Qwen3.8-27B",
    )
    manifest.validate()  # tool_catalogue and raw_value_rules are None: discovery incomplete, not invalid


def test_discovery_manifest_validate_raises_on_missing_model_id():
    manifest = make_discovery(model_id="")
    with pytest.raises(ValueError) as excinfo:
        manifest.validate()
    assert "model_id" in str(excinfo.value)


def test_discovery_manifest_distinguishes_absent_from_empty_collections():
    absent = DiscoveryManifest("claude-code", "claude-code/1.0.0", "Qwen/Qwen3.8-27B")
    empty = DiscoveryManifest("claude-code", "claude-code/1.0.0", "Qwen/Qwen3.8-27B", tool_catalogue=[], raw_value_rules=[])

    assert absent.completeness() == {"tool_catalogue_collected": False, "raw_value_rules_collected": False}
    assert absent.tool_catalogue_hash is None

    assert empty.completeness() == {"tool_catalogue_collected": True, "raw_value_rules_collected": True}
    assert empty.tool_catalogue_hash is not None  # sha256([]) is a real hash, and that is the point


# --- DeployableBundle: every field mandatory, including pinned rendering identity ---

def test_deployable_bundle_validate_raises_without_tokenizer_and_template():
    bundle = make_deployable()  # no tokenizer_path/template_path
    with pytest.raises(ValueError) as excinfo:
        bundle.validate()
    message = str(excinfo.value)
    assert "tokenizer_hash" in message
    assert "template_hash" in message


def test_deployable_bundle_validate_raises_on_uncollected_tool_catalogue(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    bundle = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file), tool_catalogue=None)
    with pytest.raises(ValueError) as excinfo:
        bundle.validate()
    assert "tool_catalogue_hash" in str(excinfo.value)


def test_deployable_bundle_accepts_an_explicitly_empty_tool_catalogue(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    bundle = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file), tool_catalogue=[])
    bundle.validate()  # must not raise: [] is a collected, confirmed-empty catalogue


def test_deployable_bundle_validate_raises_on_missing_model_revision(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    bundle = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file), model_revision="")
    with pytest.raises(ValueError) as excinfo:
        bundle.validate()
    assert "model_revision" in str(excinfo.value)


def test_bundle_sha_is_stable_for_identical_inputs(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    first = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file))
    second = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file))
    assert first.bundle_sha == second.bundle_sha
    assert first.bundle_sha


def test_bundle_sha_changes_when_the_model_revision_changes(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    first = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file))
    second = make_deployable(tokenizer_path=str(tokenizer_file), template_path=str(template_file), model_revision="a-different-revision")
    assert first.bundle_sha != second.bundle_sha


def test_deployable_bundle_raises_on_a_missing_tokenizer_file(tmp_path):
    template_file = tmp_path / "template.jinja"
    template_file.write_text("{{ x }}")
    with pytest.raises(FileNotFoundError):
        make_deployable(tokenizer_path=str(tmp_path / "does-not-exist.json"), template_path=str(template_file))


def test_discovery_manifest_promotes_to_a_deployable_bundle(tmp_path):
    tokenizer_file = tmp_path / "tokenizer.json"
    template_file = tmp_path / "template.jinja"
    tokenizer_file.write_text("{}")
    template_file.write_text("{{ x }}")
    manifest = make_discovery()
    bundle = manifest.to_deployable(model_revision="rev-1", tokenizer_path=str(tokenizer_file), template_path=str(template_file))
    bundle.validate()
    assert bundle.tool_catalogue_hash == manifest.tool_catalogue_hash
