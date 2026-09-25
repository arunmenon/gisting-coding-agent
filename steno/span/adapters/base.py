"""The harness adapter contract.

An adapter turns one harness's wire format into canonical `CallRecord`s, rewrites requests for
the proxy, declares the raw values that must survive compression untouched, and (in a later
wave) launches the harness for evaluation. Adapters stay thin: they may not import tokenizer,
span-analysis or segment code, and they are tested only against golden fixtures. Policy such as
reasoning-effort remapping belongs in the pair manifest, not in the adapter.

`launch` and `collect_result` are declared here so the contract is stable across waves, but this
wave (span analysis only) does not implement them: adapters raise NotImplementedError, and
callers that only need span analysis never call them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, runtime_checkable

from ..record import CallRecord, Part, RawValueRule, Reply, Usage


@dataclass
class AdapterIdentity:
    """Who this adapter is, for the pair manifest's identity hash."""

    name: str
    version: str
    capabilities: List[str] = field(default_factory=list)


@runtime_checkable
class ResponseDecoder(Protocol):
    """Turns a captured response (streaming or not) into a Reply and a Usage."""

    def decode(self, raw_response: Any, is_stream: bool) -> "tuple[Reply, Usage]":
        ...


@dataclass
class LaunchPlan:
    """How to run the harness on one evaluation task. Opaque payload for a later wave; the
    launcher backend interprets `command`, `env` and `workspace` for its own process model."""

    command: List[str]
    env: dict = field(default_factory=dict)
    workspace: Optional[str] = None
    timeout_s: Optional[float] = None


@dataclass
class HarnessResult:
    """A typed outcome for one launched harness run: ok, timeout, or transport failure. Never a
    bare exception or a silently-passed error."""

    status: str          # "ok" | "timeout" | "transport_failure" | "unsupported"
    ok: bool
    detail: str = ""
    artifacts: dict = field(default_factory=dict)


@runtime_checkable
class HarnessAdapter(Protocol):
    """The contract every harness adapter implements. See module docstring."""

    def identity(self) -> AdapterIdentity:
        ...

    def wants(self, raw: Any) -> bool:
        """True if this captured record is a model call this adapter analyses."""
        ...

    def parse_request(self, raw: Any) -> CallRecord:
        ...

    def response_decoder(self) -> ResponseDecoder:
        ...

    def rewrite_request(self, raw: Any, new_preamble: List[Part]) -> Any:
        """Inverse of parse_request: given the same raw request and the *unchanged* preamble
        parse_request produced, returns a request equal (by canonical JSON) to the original."""
        ...

    def raw_value_rules(self) -> List[RawValueRule]:
        ...

    def launch(self, task: Any, endpoint: str, workspace: str) -> LaunchPlan:
        raise NotImplementedError("launch is out of scope for the span-analysis wave")

    def collect_result(self, process: Any, artifacts: Any) -> HarnessResult:
        raise NotImplementedError("collect_result is out of scope for the span-analysis wave")
