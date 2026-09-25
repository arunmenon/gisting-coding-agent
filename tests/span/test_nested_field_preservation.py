"""W-14: unconsumed nested request/tool fields are preserved with a source location, and tool
semantics beyond name/description/schema participate in catalogue_hash()."""
from steno.span.adapters.claude_code import ClaudeCodeAdapter
from steno.span.record import ToolSpec


def _base_request():
    return {
        "model": "qwen3.8-27b",
        "messages": [{"role": "user", "content": "hi"}],
        "system": [{"type": "text", "text": "be helpful"}],
        "tools": [{
            "name": "Read",
            "description": "reads a file",
            "input_schema": {"type": "object"},
            "strict": True,
        }],
        "output_config": {"effort": "high", "format": "markdown"},
        "metadata": {"user_id": '{"session_id": "s-1"}', "extra_field": "kept"},
    }


def test_tool_strict_field_is_preserved_and_hashed():
    adapter = ClaudeCodeAdapter()
    raw = {"id": "r1", "path": "/v1/messages", "request": _base_request()}
    record = adapter.parse_request(raw)

    assert record.tools[0].extra.get("strict") is True

    without_strict = _base_request()
    del without_strict["tools"][0]["strict"]
    other_record = adapter.parse_request({"id": "r2", "path": "/v1/messages", "request": without_strict})
    assert record.catalogue_hash() != other_record.catalogue_hash()


def test_output_config_format_is_preserved_in_request_controls():
    adapter = ClaudeCodeAdapter()
    raw = {"id": "r1", "path": "/v1/messages", "request": _base_request()}
    record = adapter.parse_request(raw)

    assert record.request_controls["output_config"]["format"] == "markdown"
    assert record.request_controls["effort"] == "high"  # convenience mirror still present


def test_metadata_beyond_session_id_is_preserved():
    adapter = ClaudeCodeAdapter()
    raw = {"id": "r1", "path": "/v1/messages", "request": _base_request()}
    record = adapter.parse_request(raw)

    assert record.request_controls["metadata"]["extra_field"] == "kept"


def test_non_text_system_block_is_preserved_with_a_source_location():
    adapter = ClaudeCodeAdapter()
    request = _base_request()
    request["system"] = [
        {"type": "text", "text": "be helpful"},
        {"type": "image", "source": {"type": "base64", "data": "not-really-an-image"}},
    ]
    raw = {"id": "r1", "path": "/v1/messages", "request": request}
    record = adapter.parse_request(raw)

    assert len(record.preamble) == 1  # only the text block became a Part
    unconsumed = record.unsupported.get("system", [])
    assert len(unconsumed) == 1
    assert unconsumed[0]["source"] == "system[1]"
    assert unconsumed[0]["value"]["type"] == "image"


def test_message_level_extra_field_is_preserved_with_a_source_location():
    """A field on the message itself, alongside role/content (e.g. a message-level
    cache_control, distinct from a block-level one), must not disappear (W-14)."""
    adapter = ClaudeCodeAdapter()
    request = _base_request()
    request["messages"] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello", "cache_control": {"type": "ephemeral"}, "name": "custom-name"},
    ]
    raw = {"id": "r1", "path": "/v1/messages", "request": request}
    record = adapter.parse_request(raw)

    assistant_msg = record.messages[-1]
    assert assistant_msg.role == "assistant"
    assert assistant_msg.extra["source"] == "messages[1]"
    assert assistant_msg.extra["fields"] == {"cache_control": {"type": "ephemeral"}, "name": "custom-name"}


def test_message_with_no_extra_fields_has_an_empty_extra():
    adapter = ClaudeCodeAdapter()
    raw = {"id": "r1", "path": "/v1/messages", "request": _base_request()}
    record = adapter.parse_request(raw)
    assert record.messages[0].extra == {}


def test_tool_spec_extra_round_trips_through_json():
    tool = ToolSpec(name="Read", description="d", schema={}, extra={"strict": True, "cache_control": {"type": "ephemeral"}})
    restored = ToolSpec.from_dict(tool.to_dict())
    assert restored.extra == {"strict": True, "cache_control": {"type": "ephemeral"}}
