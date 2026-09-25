"""The Claude Code harness adapter: Anthropic Messages API captured by the tap proxy.

This is the reference implementation, built by moving existing logic behind the
`HarnessAdapter` contract with no change in behaviour, per steno-design.md section 3 step 1.
It ports:

  - session_key from metadata.user_id JSON               (experiments/analysis/static_span.py)
  - the Anthropic SSE reassembly (message_start/content_block_*/message_delta) (experiments/proxy/tap.py)
  - the verbatim/raw-value line regex, declared here as a RawValueRule           (experiments/gist/segments.py)

A captured record (`raw`) is one line of the tap's requests.jsonl: a dict with at least
`path`, `status`, `request`, and (for a completed call) `response`, exactly as
`experiments/proxy/tap.py` writes it.

## Canonical system-text serialisation

The three existing code paths disagree on how to turn the Anthropic `system` field (and any
inline `role: "system"` messages) into one string:

  - `experiments/analysis/static_span.py: system_text()` joins system block texts with `"\\n"`.
  - `experiments/gist/span.py: load_dominant_request()` joins system block texts with `""`
    (no separator) and ignores inline system messages.
  - `experiments/gist/dataset.py: system_text_as_served()` joins system block texts with `""`
    and *also* folds in any inline `role: "system"` messages (minus a billing header), again
    with no separator.

This adapter picks **dataset.py's variant** as canonical: empty-string join, inline system
messages folded in. That is the text vLLM's Anthropic adapter actually concatenates and feeds
to the chat template, so it is what the served model saw, not `static_span.py`'s
display-oriented approximation (which inserts newlines that never appeared in the rendered
prompt) or `span.py`'s narrower version (which drops inline system messages that do occur in
some captures). Each system block and each inline system message becomes its own `Part`, in
this repository's captures kind="instructions", so the adapter records exactly which piece of
text produced which slice of the canonical string (`Part.source`) and `rewrite_request` can put
edited text back in the right place without needing to know about the join.

## Session identity

Unlike `static_span.py`'s `session_key()`, this adapter does **not** fall back to hashing the
first user message when `metadata.user_id` is missing or unparseable. Per the design, a missing
session id stays missing (`session_id=None`, `session_source="unavailable"`); the generic layer
must not be handed a guessed identity to split data on.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, List, Tuple

from ..record import CallRecord, Msg, Part, RawValueRule, Reply, SCHEMA_VERSION, ToolSpec, Usage, sha256_of
from .base import AdapterIdentity, HarnessAdapter, LaunchPlan, HarnessResult

ADAPTER_VERSION = "claude-code/1.0.0"

# Ported verbatim from experiments/gist/segments.py: lines that carry content a compressed
# summary cannot restore exactly (paths, UUIDs, dates, the served model name) and so must stay
# raw rather than be folded into a learned span.
VERBATIM_LINE = re.compile(
    r"(?im)^.*(?:working directory|/private/|/Users/|/home/|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"\b20\d\d-\d\d-\d\d\b|powered by the model).*$"
)

_BILLING_HEADER_PREFIX = "x-anthropic-billing-header"


def _session_key(request: dict) -> Tuple[Any, str]:
    """(session_id, source). Returns (None, "unavailable") rather than guessing."""
    metadata = request.get("metadata")
    if isinstance(metadata, dict) and "user_id" in metadata:
        try:
            parsed = json.loads(metadata["user_id"])
            session_id = parsed.get("session_id") if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            session_id = None
        if session_id:
            return session_id, "metadata.user_id"
    return None, "unavailable"


def _block_text(block: Any) -> str:
    if isinstance(block, dict):
        return block.get("text", "") or ""
    return ""


def _is_billing_header(text: str) -> bool:
    return text.startswith(_BILLING_HEADER_PREFIX)


def _system_parts(request: dict) -> Tuple[List[Part], List[dict]]:
    """One Part per system block and per non-billing inline system message, in wire order,
    matching dataset.py's system_text_as_served: empty-string join, inline system messages
    folded in after the top-level system blocks.

    Returns (parts, unconsumed) where `unconsumed` records, with a source location, any system
    block or inline system message this adapter does not turn into a Part: a non-"text" block
    type, a block with no text, or a billing-header message. Nothing is silently discarded."""
    parts: List[Part] = []
    unconsumed: List[dict] = []
    system = request.get("system")
    if isinstance(system, str):
        parts.append(Part(kind="instructions", text=system, source="system:str"))
    elif isinstance(system, list):
        for index, block in enumerate(system):
            source = "system[%d]" % index
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                extra = {k: v for k, v in block.items() if k not in ("type", "text")}
                parts.append(Part(kind="instructions", text=block["text"], source=source, extra=extra))
            else:
                unconsumed.append({"source": source, "value": block})

    messages = request.get("messages") or []
    for msg_index, message in enumerate(messages):
        if message.get("role") != "system":
            continue
        message_fields = {k: v for k, v in message.items() if k not in ("role", "content")}
        if message_fields:
            # Message-level fields on an inline system message (for example `name` or a
            # message-level `cache_control`) are not part of any preamble Part's text; keep them
            # with their location so they are never silently dropped.
            unconsumed.append({"source": "messages[%d]" % msg_index, "value": message_fields,
                               "reason": "system_message_fields"})
        content = message.get("content")
        if isinstance(content, str):
            source = "messages[%d]:str" % msg_index
            if _is_billing_header(content):
                unconsumed.append({"source": source, "value": content, "reason": "billing_header"})
            else:
                parts.append(Part(kind="instructions", text=content, source=source))
        elif isinstance(content, list):
            for block_index, block in enumerate(content):
                source = "messages[%d][%d]" % (msg_index, block_index)
                text = _block_text(block)
                is_billing = isinstance(block, dict) and text and _is_billing_header(text)
                if isinstance(block, dict) and block.get("type") == "text" and text and not is_billing:
                    extra = {k: v for k, v in block.items() if k not in ("type", "text")}
                    parts.append(Part(kind="instructions", text=text, source=source, extra=extra))
                else:
                    reason = "billing_header" if is_billing else None
                    unconsumed.append({"source": source, "value": block, "reason": reason})
        else:
            unconsumed.append({"source": "messages[%d]" % msg_index, "value": content})
    return parts, unconsumed


_KNOWN_TOOL_KEYS = ("name", "description", "input_schema")


def _tool_specs(request: dict) -> List[ToolSpec]:
    """Every tool-level field beyond name/description/input_schema (for example `strict`, or a
    `cache_control` block) is preserved in ToolSpec.extra, so tool semantics that change those
    fields are visible to catalogue_hash() (W-14): silently keeping only name/description/schema
    would let tool behaviour change without the catalogue identity changing."""
    tools = request.get("tools") or []
    specs = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        extra = {k: v for k, v in tool.items() if k not in _KNOWN_TOOL_KEYS}
        specs.append(ToolSpec(
            name=tool.get("name", ""),
            description=tool.get("description", "") or "",
            schema=tool.get("input_schema", {}) or {},
            extra=extra,
        ))
    return specs


_KNOWN_MESSAGE_KEYS = ("role", "content")


def _messages(request: dict) -> List[Msg]:
    """Content blocks are never filtered (each block dict is kept whole, so block-level fields
    such as an unexpected key alongside `type`/`text`/a tool id already survive). What was
    silently dropped before (W-14) is any field on the *message* itself besides "role" and
    "content" -- a `name`, a message-level `cache_control`, an experimental field a future
    harness version adds. Those now go into `Msg.extra`, tagged with a source location
    ("messages[i]") so they can be traced back."""
    out = []
    for index, message in enumerate(request.get("messages") or []):
        role = message.get("role", "")
        if role == "system":
            continue  # folded into the preamble by _system_parts
        content = message.get("content")
        if isinstance(content, str):
            blocks = [{"type": "text", "text": content}]
        else:
            blocks = list(content or [])
        extra = {k: v for k, v in message.items() if k not in _KNOWN_MESSAGE_KEYS}
        if extra:
            extra = {"source": "messages[%d]" % index, "fields": extra}
        out.append(Msg(role=role, blocks=blocks, extra=extra))
    return out


def _request_controls(request: dict) -> dict:
    """Template-affecting and rendering-affecting controls. `output_config` and `metadata` are
    kept in full (not just the `effort`/`user_id` sub-fields this adapter otherwise reads), per
    W-14: a nested field such as `output_config.format` must not disappear from the canonical
    record just because only one of its siblings is consumed elsewhere."""
    controls = {}
    for key in ("model", "stream", "max_tokens", "thinking", "context_management", "output_config", "metadata"):
        if key in request:
            controls[key] = request[key]
    output_config = request.get("output_config")
    if isinstance(output_config, dict) and "effort" in output_config:
        controls["effort"] = output_config["effort"]  # convenience mirror; output_config above is the full record
    return controls


def _reply_and_usage(response: dict) -> Tuple[Reply, Usage]:
    content = response.get("content") or []
    stop_reason = response.get("stop_reason")
    usage_raw = response.get("usage") or {}
    usage = Usage(
        input_tokens=usage_raw.get("input_tokens"),
        output_tokens=usage_raw.get("output_tokens"),
        cache_read_input_tokens=usage_raw.get("cache_read_input_tokens"),
        cache_creation_input_tokens=usage_raw.get("cache_creation_input_tokens"),
        source="response.usage",
    )
    # A captured dict can itself carry a stream reassembly's error/incomplete markers (this
    # adapter's own summarize_stream sets them) or a top-level "error" key from a failed body.
    error = response.get("error")
    incomplete = bool(response.get("incomplete")) or error is not None
    unknown_events = response.get("unknown_events") or []
    reply = Reply(blocks=content, stop_reason=stop_reason, incomplete=incomplete, error=error, unknown_events=unknown_events)
    return reply, usage


# --- SSE reassembly, ported from experiments/proxy/tap.py (parse_sse_events / summarize_stream) ---

def parse_sse_events(raw_bytes: bytes) -> List[Tuple[Any, dict]]:
    events = []
    for block in raw_bytes.decode("utf-8", errors="replace").split("\n\n"):
        event_name = None
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if data_lines:
            try:
                events.append((event_name, json.loads("\n".join(data_lines))))
            except json.JSONDecodeError:
                events.append((event_name, {"_raw": "\n".join(data_lines)}))
    return events


_KNOWN_STREAM_EVENT_TYPES = {
    "message_start", "content_block_start", "content_block_delta", "content_block_stop",
    "message_delta", "message_stop", "ping", "error",
}


def summarize_stream(events: List[Tuple[Any, dict]]) -> dict:
    """Reassembles a stream into the same shape as a non-streaming response, plus three fields a
    normal reply never needs: `error` (the SSE `error` event's payload, if one occurred),
    `incomplete`, and `unknown_events` (any event type this function does not specifically
    handle, preserved verbatim rather than dropped). `signature_delta` accumulates into a
    `signature` field on its content block, the same way `thinking_delta` accumulates into
    `thinking` -- both are needed to reproduce a signed thinking block exactly (W-15).

    `incomplete` is true when any of: an `error` event occurred; the stream never reached
    `message_stop`; or a content block was started (`content_block_start`) but never closed
    (`content_block_stop`) -- a truncated connection can stop mid-block without ever sending an
    `error` event, and that must not read as an ordinary finished reply just because no explicit
    error was seen."""
    content_blocks: List[dict] = []
    usage: dict = {}
    stop_reason = None
    error = None
    saw_error = False
    saw_message_stop = False
    open_block_indices = set()
    unknown_events: List[dict] = []
    for event_name, data in events:
        event_type = data.get("type", event_name)
        if event_type == "message_start":
            usage.update(data.get("message", {}).get("usage", {}))
        elif event_type == "content_block_start":
            block = dict(data.get("content_block", {}))
            if block.get("type") == "tool_use":
                block["_partial_json"] = ""
            else:
                block.setdefault("text", "")
            content_blocks.append(block)
            open_block_indices.add(data.get("index", len(content_blocks) - 1))
        elif event_type == "content_block_delta" and content_blocks:
            delta = data.get("delta", {})
            index = data.get("index", len(content_blocks) - 1)
            if index >= len(content_blocks):
                continue
            target = content_blocks[index]
            if delta.get("type") == "text_delta":
                target["text"] = target.get("text", "") + delta.get("text", "")
            elif delta.get("type") == "input_json_delta":
                target["_partial_json"] += delta.get("partial_json", "")
            elif delta.get("type") == "thinking_delta":
                target["thinking"] = target.get("thinking", "") + delta.get("thinking", "")
            elif delta.get("type") == "signature_delta":
                target["signature"] = target.get("signature", "") + delta.get("signature", "")
            else:
                unknown_events.append({"event": event_name, "data": data, "reason": "unhandled delta type"})
        elif event_type == "content_block_stop":
            open_block_indices.discard(data.get("index"))
        elif event_type == "message_delta":
            usage.update(data.get("usage", {}))
            stop_reason = data.get("delta", {}).get("stop_reason", stop_reason)
        elif event_type == "message_stop":
            saw_message_stop = True
        elif event_type == "error":
            error = data.get("error", data)
            saw_error = True
        elif event_type == "ping":
            pass  # structural marker with nothing to reassemble
        else:
            unknown_events.append({"event": event_name, "data": data})
    for block in content_blocks:
        if "_partial_json" in block:
            raw = block.pop("_partial_json")
            try:
                block["input"] = json.loads(raw) if raw else {}
                block["input_json_valid"] = True
            except json.JSONDecodeError:
                block["input_raw"] = raw
                block["input_json_valid"] = False
    truncated = (not saw_message_stop) or bool(open_block_indices)
    return {
        "content": content_blocks,
        "usage": usage,
        "stop_reason": stop_reason,
        "error": error,
        "incomplete": saw_error or truncated,
        "unknown_events": unknown_events,
    }


class ClaudeCodeResponseDecoder:
    """Decodes a captured Claude Code response, streamed or not, into (Reply, Usage)."""

    def decode(self, raw_response: Any, is_stream: bool) -> Tuple[Reply, Usage]:
        if is_stream and isinstance(raw_response, (bytes, bytearray)):
            summary = summarize_stream(parse_sse_events(bytes(raw_response)))
            return _reply_and_usage(summary)
        if isinstance(raw_response, dict):
            return _reply_and_usage(raw_response)
        return Reply(blocks=[], stop_reason=None), Usage(source="unavailable")


class ClaudeCodeAdapter:
    """HarnessAdapter for Claude Code's Anthropic Messages API traffic, as captured by the tap."""

    def identity(self) -> AdapterIdentity:
        return AdapterIdentity(name="claude-code", version=ADAPTER_VERSION, capabilities=["parse", "rewrite"])

    def wants(self, raw: Any) -> bool:
        if not isinstance(raw, dict):
            return False
        path = raw.get("path", "") or ""
        return bool(path.startswith("/v1/messages") and raw.get("request") and not path.endswith("count_tokens"))

    def parse_request(self, raw: dict) -> CallRecord:
        request = raw.get("request") or {}

        session_id, session_source = _session_key(request)
        preamble, unconsumed_system = _system_parts(request)
        tools = _tool_specs(request)
        messages = _messages(request)
        controls = _request_controls(request)

        transformation_log = [
            "session_id from %s" % session_source,
            "system text canonicalised as dataset.py's empty-string join with inline system "
            "messages folded in (see module docstring for how this relates to static_span.py "
            "and span.py's variants)",
        ]

        reply, usage, reply_note = self._decode_reply(raw)
        transformation_log.append(reply_note)

        known_request_keys = {"model", "messages", "system", "tools", "metadata", "max_tokens",
                               "thinking", "context_management", "output_config", "stream"}
        unsupported_request = {k: v for k, v in request.items() if k not in known_request_keys}

        unsupported = {}
        if unsupported_request:
            unsupported["request"] = unsupported_request
        if unconsumed_system:
            unsupported["system"] = unconsumed_system

        record = CallRecord(
            schema_version=SCHEMA_VERSION,
            call_id=raw.get("id") or sha256_of(request)[:16],
            harness="claude-code",
            adapter_version=ADAPTER_VERSION,
            session_id=session_id,
            parent_session_id=None,
            turn_index=len(messages),
            session_source=session_source,
            preamble=preamble,
            tools=tools,
            messages=messages,
            request_controls=controls,
            reply=reply,
            usage=usage,
            timing={k: raw.get(k) for k in ("ts", "ttfb_s", "ttft_s", "latency_s") if raw.get(k) is not None},
            raw_pointer=raw.get("id", ""),
            raw_hash=sha256_of(request),
            transformation_log=transformation_log,
            unsupported=unsupported,
        )
        return record

    @staticmethod
    def _decode_reply(raw: dict) -> Tuple[Any, Any, str]:
        """Routes every captured response representation through the decoder (W-15), rather than
        only handling a plain dict: a non-200 status with no reassembled response (tap.py writes
        `response_raw`, a truncated text body, for those) becomes a typed incomplete/error Reply
        instead of silently leaving reply=None with no explanation."""
        response = raw.get("response")
        status = raw.get("status")
        decoder = ClaudeCodeResponseDecoder()

        if isinstance(response, dict):
            reply, usage = decoder.decode(response, is_stream=bool(raw.get("stream")))
            return reply, usage, "reply/usage decoded from a captured response dict"

        if isinstance(response, (bytes, bytearray)):
            reply, usage = decoder.decode(response, is_stream=True)
            return reply, usage, "reply/usage decoded from raw captured SSE bytes"

        if status is not None and status != 200:
            reply = Reply(blocks=[], stop_reason=None, incomplete=True,
                           error={"status": status, "body": raw.get("response_raw")})
            return reply, Usage(source="unavailable"), "no usable response body; captured as an error reply (status %s)" % status

        return None, None, "no response captured for this call"

    def response_decoder(self) -> ClaudeCodeResponseDecoder:
        return ClaudeCodeResponseDecoder()

    def rewrite_request(self, raw: dict, new_preamble: List[Part]) -> dict:
        """Inverse of parse_request's preamble extraction. Rebuilds the `system` field (and any
        inline system messages) from `new_preamble`, keyed by each Part's `source`; every other
        field of the request is left untouched. Passing back the unchanged preamble reproduces
        the original request (compare with record.canonical_json, not byte equality, since key
        order is not semantically meaningful)."""
        import copy as _copy

        new_raw = _copy.deepcopy(raw)
        request = new_raw.get("request") or {}
        by_source = {part.source: part for part in new_preamble}

        system = request.get("system")
        if isinstance(system, str):
            part = by_source.get("system:str")
            if part is not None:
                request["system"] = part.text
        elif isinstance(system, list):
            new_blocks = []
            for index, block in enumerate(system):
                source = "system[%d]" % index
                part = by_source.get(source)
                if part is not None and isinstance(block, dict):
                    new_block = dict(block)
                    new_block["text"] = part.text
                    new_blocks.append(new_block)
                else:
                    new_blocks.append(block)
            request["system"] = new_blocks

        messages = request.get("messages")
        if isinstance(messages, list):
            new_messages = []
            for msg_index, message in enumerate(messages):
                if message.get("role") != "system":
                    new_messages.append(message)
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    part = by_source.get("messages[%d]:str" % msg_index)
                    new_message = dict(message)
                    if part is not None:
                        new_message["content"] = part.text
                    new_messages.append(new_message)
                elif isinstance(content, list):
                    new_content = []
                    for block_index, block in enumerate(content):
                        source = "messages[%d][%d]" % (msg_index, block_index)
                        part = by_source.get(source)
                        if part is not None and isinstance(block, dict):
                            new_block = dict(block)
                            new_block["text"] = part.text
                            new_content.append(new_block)
                        else:
                            new_content.append(block)
                    new_message = dict(message)
                    new_message["content"] = new_content
                    new_messages.append(new_message)
                else:
                    new_messages.append(message)
            request["messages"] = new_messages

        new_raw["request"] = request
        return new_raw

    def raw_value_rules(self) -> List[RawValueRule]:
        return [
            RawValueRule(
                name="verbatim_line",
                pattern=VERBATIM_LINE.pattern,
                description=(
                    "A whole line naming a working directory, an absolute path, a UUID, an "
                    "ISO date, or the served model name; a compressed summary cannot reproduce "
                    "these exactly, so they must stay raw (ported from experiments/gist/segments.py)."
                ),
            )
        ]

    def launch(self, task, endpoint, workspace):  # pragma: no cover - out of scope this wave
        raise NotImplementedError("launch is out of scope for the span-analysis wave")

    def collect_result(self, process, artifacts):  # pragma: no cover - out of scope this wave
        raise NotImplementedError("collect_result is out of scope for the span-analysis wave")
