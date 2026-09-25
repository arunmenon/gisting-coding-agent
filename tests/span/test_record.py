from steno.span.record import CallRecord, Part, RawValueRule, Reply, SCHEMA_VERSION, ToolSpec, Usage


def make_record(session_id=None):
    return CallRecord(
        schema_version=SCHEMA_VERSION,
        call_id="call-1",
        harness="claude-code",
        adapter_version="claude-code/1.0.0",
        session_id=session_id,
        session_source="metadata.user_id" if session_id else "unavailable",
        turn_index=2,
        preamble=[Part(kind="instructions", text="hello", source="system[0]", extra={"cache_control": {"type": "ephemeral"}})],
        tools=[ToolSpec(name="Read", description="reads a file", schema={"type": "object"})],
        messages=[],
        request_controls={"model": "qwen3.8-27b", "stream": True},
        reply=Reply(blocks=[{"type": "text", "text": "hi"}], stop_reason="end_turn"),
        usage=Usage(input_tokens=10, output_tokens=5, source="response.usage"),
        raw_pointer="line-0",
        raw_hash="deadbeef",
        transformation_log=["session_id from metadata.user_id"],
        unsupported={"request": {"weird_field": 1}},
    )


def test_json_round_trip_preserves_all_fields():
    record = make_record(session_id="session-abc")
    restored = CallRecord.from_json(record.to_json())
    assert restored.to_dict() == record.to_dict()
    assert restored.preamble[0].extra == {"cache_control": {"type": "ephemeral"}}
    assert restored.unsupported == {"request": {"weird_field": 1}}


def test_dict_round_trip_is_a_deep_copy_not_aliased():
    record = make_record(session_id="session-abc")
    data = record.to_dict()
    data["preamble"][0]["text"] = "mutated"
    assert record.preamble[0].text == "hello"


def test_session_id_none_stays_none_and_records_why():
    record = make_record(session_id=None)
    assert record.session_id is None
    assert record.session_source == "unavailable"
    restored = CallRecord.from_json(record.to_json())
    assert restored.session_id is None
    assert restored.session_source == "unavailable"


def test_catalogue_hash_is_stable_and_order_sensitive():
    record = make_record()
    first = record.catalogue_hash()
    same = make_record()
    assert first == same.catalogue_hash()

    reordered = make_record()
    reordered.tools = [ToolSpec(name="Write", description="writes a file", schema={"type": "object"}), record.tools[0]]
    assert reordered.catalogue_hash() != first


def test_raw_value_rule_round_trip():
    rule = RawValueRule(name="verbatim_line", pattern=r"(?im)^.*working directory.*$", description="a path line")
    restored = RawValueRule.from_dict(rule.to_dict())
    assert restored == rule
