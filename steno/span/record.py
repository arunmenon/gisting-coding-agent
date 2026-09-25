"""The canonical call record: one model call, wire format removed, nothing lost.

Every harness adapter parses its wire format into a CallRecord. Everything downstream of the
adapter (discovery, classification, the invariance report, the model adapter in a later wave)
works only against this shape, never against a harness's raw JSON. Unknown or unmodelled fields
are preserved in `unsupported`, never dropped, so a harness adapter can be incomplete without
being lossy.

A missing session id stays missing (`session_id=None`); nothing here guesses one from message
text or any other heuristic. The generic layer must not split training and evaluation data on a
guessed identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional


SCHEMA_VERSION = "steno-call-record/v1"


def canonical_json(value: Any) -> str:
    """Stable JSON text for hashing and for comparing two structures for semantic equality.

    Sorted keys, compact separators, no ASCII escaping games: two structures that are the same
    data, however key order or dict-literal order differed, produce identical text.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _as_dict(value):
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _list_to_dict(values):
    return [v.to_dict() if hasattr(v, "to_dict") else v for v in values]


@dataclass
class Part:
    """One ordered piece of the preamble: instructions, a tool catalogue description, or other
    harness-specific content. `source` names where in the raw request this part came from
    (for example "system[0]"), so a harness adapter can rewrite exactly that location later."""

    kind: str
    text: str
    source: str
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "source": self.source, "extra": self.extra}

    @classmethod
    def from_dict(cls, data: dict) -> "Part":
        return cls(kind=data["kind"], text=data["text"], source=data["source"], extra=data.get("extra", {}))


@dataclass
class ToolSpec:
    """One entry in the tool catalogue, full schema kept. The generic layer computes the
    catalogue hash; adapters only report the catalogue as the harness declared it.

    `extra` carries every tool-level field beyond name/description/schema (for example
    `strict`, or a `cache_control` block) so tool behaviour that changes those fields is not
    invisible to `catalogue_hash()` -- `to_dict()` includes `extra`, and the hash is computed
    over the full `to_dict()` of every tool."""

    name: str
    description: str
    schema: dict
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "schema": self.schema, "extra": self.extra}

    @classmethod
    def from_dict(cls, data: dict) -> "ToolSpec":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            schema=data.get("schema", {}),
            extra=data.get("extra", {}),
        )


@dataclass
class Msg:
    """One message in the call's history. `blocks` is the ordered list of typed content blocks
    (text, tool_use, tool_result, thinking, ...) exactly as the harness represented them; the
    generic layer does not require a specific block vocabulary, it only reasons about spans of
    text within blocks it recognises. Block-level fields are never filtered (each block dict is
    kept whole), but a message can also carry fields alongside "role" and "content" (a `name`, a
    message-level `cache_control`, an experimental harness field); those land in `extra`, keyed
    by field name, so they survive a round trip instead of silently disappearing."""

    role: str
    blocks: list
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"role": self.role, "blocks": self.blocks, "extra": self.extra}

    @classmethod
    def from_dict(cls, data: dict) -> "Msg":
        return cls(role=data["role"], blocks=data.get("blocks", []), extra=data.get("extra", {}))


@dataclass
class Reply:
    """The model's reply to this call, if one was captured.

    `incomplete` and `error` give the reply a typed way to say "this is not a normal finished
    reply": a transport failure, a non-200 status, or a stream that ended in an `error` SSE event
    rather than a clean `message_delta`/stop reason. `unknown_events` preserves any streamed
    event type this decoder does not specifically model, so a new event type never silently
    disappears."""

    blocks: list
    stop_reason: Optional[str] = None
    incomplete: bool = False
    error: Optional[dict] = None
    unknown_events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "blocks": self.blocks,
            "stop_reason": self.stop_reason,
            "incomplete": self.incomplete,
            "error": self.error,
            "unknown_events": self.unknown_events,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Reply":
        return cls(
            blocks=data.get("blocks", []),
            stop_reason=data.get("stop_reason"),
            incomplete=data.get("incomplete", False),
            error=data.get("error"),
            unknown_events=data.get("unknown_events", []),
        )


@dataclass
class Usage:
    """Token usage as the harness reported it, plus where it came from (a header, a response
    field, a non-streaming vs streaming reassembly). Token counting through a model adapter is a
    later wave; this is whatever the harness itself claimed."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    source: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Usage":
        return cls(
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            cache_read_input_tokens=data.get("cache_read_input_tokens"),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens"),
            source=data.get("source", "unknown"),
        )


@dataclass
class RawValueRule:
    """A declared rule for a per-session or per-call value that must survive compression
    unchanged: a working directory, a UUID, a timestamp, a served model name. The generic layer
    uses these to explain a varying range as "protected raw" rather than "unresolved"; it never
    invents a rule on its own."""

    name: str
    pattern: str
    description: str

    def to_dict(self) -> dict:
        return {"name": self.name, "pattern": self.pattern, "description": self.description}

    @classmethod
    def from_dict(cls, data: dict) -> "RawValueRule":
        return cls(name=data["name"], pattern=data["pattern"], description=data.get("description", ""))


@dataclass
class CallRecord:
    """One model call, canonical, with the wire format removed."""

    # Identity
    schema_version: str
    call_id: str
    harness: str
    adapter_version: str
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    attempt_id: Optional[str] = None

    # Session
    session_id: Optional[str] = None
    parent_session_id: Optional[str] = None
    turn_index: Optional[int] = None
    session_source: str = "unavailable"

    # Preamble and tools
    preamble: list = field(default_factory=list)     # list[Part]
    tools: list = field(default_factory=list)         # list[ToolSpec]

    # Messages
    messages: list = field(default_factory=list)      # list[Msg]

    # Request controls: requested model, streaming, reasoning/template options
    request_controls: dict = field(default_factory=dict)

    # Response and usage
    reply: Optional[Reply] = None
    usage: Optional[Usage] = None
    timing: dict = field(default_factory=dict)

    # Provenance
    raw_pointer: str = ""
    raw_hash: str = ""
    transformation_log: list = field(default_factory=list)
    unsupported: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "call_id": self.call_id,
            "harness": self.harness,
            "adapter_version": self.adapter_version,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "turn_index": self.turn_index,
            "session_source": self.session_source,
            "preamble": _list_to_dict(self.preamble),
            "tools": _list_to_dict(self.tools),
            "messages": _list_to_dict(self.messages),
            "request_controls": self.request_controls,
            "reply": _as_dict(self.reply),
            "usage": _as_dict(self.usage),
            "timing": self.timing,
            "raw_pointer": self.raw_pointer,
            "raw_hash": self.raw_hash,
            "transformation_log": self.transformation_log,
            "unsupported": self.unsupported,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CallRecord":
        data = copy.deepcopy(data)
        reply = data.get("reply")
        usage = data.get("usage")
        return cls(
            schema_version=data["schema_version"],
            call_id=data["call_id"],
            harness=data["harness"],
            adapter_version=data["adapter_version"],
            run_id=data.get("run_id"),
            task_id=data.get("task_id"),
            attempt_id=data.get("attempt_id"),
            session_id=data.get("session_id"),
            parent_session_id=data.get("parent_session_id"),
            turn_index=data.get("turn_index"),
            session_source=data.get("session_source", "unavailable"),
            preamble=[Part.from_dict(p) for p in data.get("preamble", [])],
            tools=[ToolSpec.from_dict(t) for t in data.get("tools", [])],
            messages=[Msg.from_dict(m) for m in data.get("messages", [])],
            request_controls=data.get("request_controls", {}),
            reply=Reply.from_dict(reply) if reply is not None else None,
            usage=Usage.from_dict(usage) if usage is not None else None,
            timing=data.get("timing", {}),
            raw_pointer=data.get("raw_pointer", ""),
            raw_hash=data.get("raw_hash", ""),
            transformation_log=data.get("transformation_log", []),
            unsupported=data.get("unsupported", {}),
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> "CallRecord":
        return cls.from_dict(json.loads(text))

    def catalogue_hash(self) -> str:
        """Hash of the tool catalogue, computed here in the generic layer, not by the adapter."""
        return sha256_of(_list_to_dict(self.tools))

    def instruction_text(self) -> str:
        """The preamble parts joined in order, used to group calls into cohorts by structure."""
        return "".join(part.text for part in self.preamble)
