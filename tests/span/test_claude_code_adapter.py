import json

from steno.span.adapters.claude_code import ClaudeCodeAdapter, VERBATIM_LINE
from steno.span.record import canonical_json


def test_wants_only_messages_calls_with_a_request(fixture_raws):
    adapter = ClaudeCodeAdapter()
    wanted = [raw for raw in fixture_raws if adapter.wants(raw)]
    assert len(wanted) == len(fixture_raws)  # the whole fixture is model-call traffic
    assert not adapter.wants({"path": "/v1/messages/count_tokens", "request": {}})
    assert not adapter.wants({"path": "/v1/messages", "request": None})
    assert not adapter.wants({"path": "/other"})


def test_golden_parse_of_first_capture(fixture_raws):
    adapter = ClaudeCodeAdapter()
    raw = fixture_raws[0]
    record = adapter.parse_request(raw)

    assert record.harness == "claude-code"
    assert record.call_id == raw["id"]
    assert record.session_id == "00000000-0000-4000-8000-000000000002"
    assert record.session_source == "metadata.user_id"
    assert len(record.tools) == 5
    assert record.tools[0].name == raw["request"]["tools"][0]["name"]
    # the canonical instruction text is the empty-string join of system blocks, with any inline
    # role="system" messages folded in after them (dataset.py's system_text_as_served variant)
    expected_instruction_text = "".join(
        block["text"] for block in raw["request"]["system"] if block.get("type") == "text"
    )
    for message in raw["request"]["messages"]:
        if message.get("role") != "system":
            continue
        for block in message.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                expected_instruction_text += block["text"]
    assert record.instruction_text() == expected_instruction_text
    # inline system messages are folded into the preamble, not left in the message history
    assert all(msg.role != "system" for msg in record.messages)
    assert record.reply is not None
    assert record.usage is not None


def test_session_id_is_none_when_metadata_is_missing():
    adapter = ClaudeCodeAdapter()
    raw = {
        "id": "no-session",
        "path": "/v1/messages",
        "request": {"model": "qwen3.8-27b", "messages": [{"role": "user", "content": "hi"}], "system": "be nice", "tools": []},
    }
    record = adapter.parse_request(raw)
    assert record.session_id is None
    assert record.session_source == "unavailable"


def test_rewrite_with_unchanged_preamble_reproduces_the_original(fixture_raws):
    adapter = ClaudeCodeAdapter()
    for raw in fixture_raws:
        record = adapter.parse_request(raw)
        rewritten = adapter.rewrite_request(raw, record.preamble)
        assert canonical_json(rewritten) == canonical_json(raw)


def test_rewrite_with_edited_preamble_only_changes_the_preamble(fixture_raws):
    adapter = ClaudeCodeAdapter()
    raw = fixture_raws[0]
    record = adapter.parse_request(raw)
    edited = [
        p if p.source != record.preamble[0].source else
        type(p)(kind=p.kind, text="<gisted>", source=p.source, extra=p.extra)
        for p in record.preamble
    ]
    rewritten = adapter.rewrite_request(raw, edited)
    assert rewritten["request"]["system"][0]["text"] == "<gisted>"
    # everything outside the rewritten preamble slot is untouched
    assert rewritten["request"]["messages"] == raw["request"]["messages"]
    assert rewritten["request"]["tools"] == raw["request"]["tools"]


def test_raw_value_rules_cover_the_working_directory_line(fixture_raws):
    adapter = ClaudeCodeAdapter()
    rules = adapter.raw_value_rules()
    assert len(rules) == 1
    pattern = rules[0].pattern
    assert pattern == VERBATIM_LINE.pattern

    record = adapter.parse_request(fixture_raws[0])
    instruction_lines = record.instruction_text().split("\n")
    matched_a_line = any(VERBATIM_LINE.search(line) for line in instruction_lines)
    assert matched_a_line, "fixture should retain at least one working-directory / path line"


def test_inline_system_message_fields_are_preserved():
    """Recheck 2, W-14: `name` and a message-level `cache_control` on an inline system
    message must survive parsing, with their source location."""
    from steno.span.adapters.claude_code import ClaudeCodeAdapter

    raw = {
        "path": "/v1/messages",
        "request": {
            "model": "m",
            "system": [{"type": "text", "text": "rules"}],
            "messages": [
                {"role": "system", "name": "policy", "cache_control": {"type": "ephemeral"}, "content": "extra rules"},
                {"role": "user", "content": "hi"},
            ],
        },
    }
    record = ClaudeCodeAdapter().parse_request(raw)
    serialised = record.to_json()
    assert "policy" in serialised and "ephemeral" in serialised
    assert "system_message_fields" in serialised
