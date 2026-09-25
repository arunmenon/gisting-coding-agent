"""W-15: streaming decoding preserves signature_delta and unknown events, and exposes typed
error/incomplete outcomes. Fixtures here are small, synthetic SSE byte streams (not derived from
any real capture) built directly from the Anthropic Messages streaming event shapes."""
import json

from steno.span.adapters.claude_code import ClaudeCodeAdapter, parse_sse_events, summarize_stream


def _sse(event_name, data):
    return "event: %s\ndata: %s\n\n" % (event_name, json.dumps(data))


def test_signature_delta_is_preserved_on_its_content_block():
    stream = "".join([
        _sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 10}}}),
        _sse("content_block_start", {"type": "content_block_start", "index": 0,
                                      "content_block": {"type": "thinking", "thinking": ""}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                      "delta": {"type": "thinking_delta", "thinking": "reasoning..."}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                      "delta": {"type": "signature_delta", "signature": "sig-abc"}}),
        _sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        _sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 5}}),
        _sse("message_stop", {"type": "message_stop"}),
    ]).encode("utf-8")

    summary = summarize_stream(parse_sse_events(stream))

    assert summary["content"][0]["thinking"] == "reasoning..."
    assert summary["content"][0]["signature"] == "sig-abc"
    assert summary["error"] is None
    assert summary["incomplete"] is False
    assert summary["unknown_events"] == []


def test_unknown_event_type_is_preserved_not_dropped():
    stream = "".join([
        _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}}),
        _sse("a_future_event_type", {"type": "a_future_event_type", "payload": {"anything": 1}}),
        _sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        _sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}}),
        _sse("message_stop", {"type": "message_stop"}),
    ]).encode("utf-8")

    summary = summarize_stream(parse_sse_events(stream))

    assert summary["content"][0]["text"] == "hi"
    assert len(summary["unknown_events"]) == 1
    assert summary["unknown_events"][0]["data"]["type"] == "a_future_event_type"
    assert summary["incomplete"] is False


def test_stream_with_no_message_stop_is_marked_incomplete():
    """A connection can drop after message_delta without ever sending message_stop; that must
    not read as an ordinary finished reply."""
    stream = "".join([
        _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}}),
        _sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        _sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}}),
        # no message_stop: the connection was cut here
    ]).encode("utf-8")

    summary = summarize_stream(parse_sse_events(stream))

    assert summary["error"] is None  # truncated, not an explicit error
    assert summary["incomplete"] is True


def test_stream_with_an_unfinished_content_block_is_marked_incomplete():
    """A connection can drop mid-block, before content_block_stop, even if message_stop somehow
    still arrives (or is faked by an upstream); an unfinished block is incomplete regardless."""
    stream = "".join([
        _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "cut off mid-"}}),
        # no content_block_stop for index 0
        _sse("message_stop", {"type": "message_stop"}),
    ]).encode("utf-8")

    summary = summarize_stream(parse_sse_events(stream))

    assert summary["content"][0]["text"] == "cut off mid-"
    assert summary["incomplete"] is True


def test_error_event_marks_the_reply_incomplete_with_the_error_payload():
    stream = "".join([
        _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        _sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "partial"}}),
        _sse("error", {"type": "error", "error": {"type": "overloaded_error", "message": "server overloaded"}}),
    ]).encode("utf-8")

    summary = summarize_stream(parse_sse_events(stream))

    assert summary["incomplete"] is True
    assert summary["error"]["type"] == "overloaded_error"
    assert summary["stop_reason"] is None  # the stream never reached message_delta


def test_response_decoder_surfaces_incomplete_streams_as_a_typed_reply():
    stream = "".join([
        _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        _sse("error", {"type": "error", "error": {"type": "timeout", "message": "upstream timed out"}}),
    ]).encode("utf-8")

    decoder = ClaudeCodeAdapter().response_decoder()
    reply, usage = decoder.decode(stream, is_stream=True)

    assert reply.incomplete is True
    assert reply.error["type"] == "timeout"


def test_parse_request_marks_a_non_200_capture_as_an_error_reply():
    adapter = ClaudeCodeAdapter()
    raw = {
        "id": "r1", "path": "/v1/messages", "status": 502,
        "request": {"model": "qwen3.8-27b", "messages": [{"role": "user", "content": "hi"}]},
        "response_raw": "upstream error: connection reset",
    }
    record = adapter.parse_request(raw)
    assert record.reply.incomplete is True
    assert record.reply.error["status"] == 502
    assert "connection reset" in record.reply.error["body"]
