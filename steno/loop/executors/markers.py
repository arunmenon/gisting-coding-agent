"""Parses the STATE marker lines a vast journey chain script writes (see
`experiments/vast/conn_chain.sh`'s `mark()` calls) into typed records, with no execution of
anything. This is generic to "a script that appends `<ISO8601 timestamp> <event text>` lines to
`/root/STATE`"; the specific marker shapes recognised below (`ckpt_built`, `server_up`, `B6 ...`,
`*_FAILED`) are the ones `conn_chain.sh` actually writes, ported by reading that script, not
invented from a schema. A later journey with a different chain script will need its own marker
shapes added here (or its own small parser module) -- this is deliberately not a generic
key=value grammar, because the chain scripts are not one either.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TS_LINE = re.compile(r"^(?P<ts>\S+)\s+(?P<rest>.*)$")

B6_LINE = re.compile(
    r"^B6\s+conn=(?P<conn>\d+)\s+arm=(?P<arm>\S+)\s+c=(?P<c>\d+)\s+rpm=(?P<rpm>[\d.]+)\s+"
    r"max_running=(?P<max_running>[\d.]+)\s+kv_max=(?P<kv_max>[\d.]+)\s+preempt=(?P<preempt>[\d.]+)\s+"
    r"ok=(?P<ok>\d+)\s+err=(?P<err>\d+)$"
)
B6_FAILED_LINE = re.compile(r"^B6_FAILED\s+conn=(?P<conn>\d+)\s+arm=(?P<arm>\S+)\s+c=(?P<c>\d+)$")
SERVER_UP_LINE = re.compile(
    r"^server_up\s+len=(?P<len>\d+)\s+seqs=(?P<seqs>\d+)\s+util=(?P<util>[\d.]+)\s+batched=(?P<batched>\d+)$"
)
CKPT_BUILT_LINE = re.compile(r"^ckpt_built\s*(?:\((?P<detail>.*)\))?$")
CHAIN_START_LINE = re.compile(r"^conn_chain_start\s*(?P<detail>.*)$")
DOWNLOAD_ATTEMPT_LINE = re.compile(r"^download_attempt_(?P<attempt>\d+)$")


@dataclass
class Marker:
    """One classified STATE line. `kind` is one of: chain_start, download_attempt, ckpt_built,
    server_up, b6_result, b6_failed, b6_done, bench_done, infra_failure, verdict_text, unknown.
    `fields` holds the parsed, typed values for kinds that carry them; `raw` is the original
    line, always kept so nothing is lost even for `unknown`."""

    ts: Optional[str]
    kind: str
    raw: str
    fields: Dict[str, Any] = field(default_factory=dict)


def _classify(ts: Optional[str], rest: str, raw: str) -> Marker:
    match = B6_LINE.match(rest)
    if match:
        g = match.groupdict()
        return Marker(ts=ts, kind="b6_result", raw=raw, fields={
            "conn": int(g["conn"]), "arm": g["arm"], "c": int(g["c"]),
            "rpm": float(g["rpm"]), "max_running": float(g["max_running"]),
            "kv_max": float(g["kv_max"]), "preempt": float(g["preempt"]),
            "ok": int(g["ok"]), "err": int(g["err"]),
        })

    match = B6_FAILED_LINE.match(rest)
    if match:
        g = match.groupdict()
        return Marker(ts=ts, kind="b6_failed", raw=raw,
                      fields={"conn": int(g["conn"]), "arm": g["arm"], "c": int(g["c"])})

    if rest == "B6_done":
        return Marker(ts=ts, kind="b6_done", raw=raw)
    if rest == "BENCH_DONE":
        return Marker(ts=ts, kind="bench_done", raw=raw)

    match = SERVER_UP_LINE.match(rest)
    if match:
        g = match.groupdict()
        return Marker(ts=ts, kind="server_up", raw=raw, fields={
            "max_model_len": int(g["len"]), "max_num_seqs": int(g["seqs"]),
            "gpu_util": float(g["util"]), "max_batched": int(g["batched"]),
        })

    match = CKPT_BUILT_LINE.match(rest)
    if match:
        return Marker(ts=ts, kind="ckpt_built", raw=raw, fields={"detail": match.group("detail") or ""})

    match = CHAIN_START_LINE.match(rest)
    if match:
        return Marker(ts=ts, kind="chain_start", raw=raw, fields={"detail": match.group("detail").strip()})

    match = DOWNLOAD_ATTEMPT_LINE.match(rest)
    if match:
        return Marker(ts=ts, kind="download_attempt", raw=raw, fields={"attempt": int(match.group("attempt"))})

    if rest.startswith("=== VERDICT") or rest.startswith("RESULT:") or re.match(r"^conn=\d", rest):
        return Marker(ts=ts, kind="verdict_text", raw=raw)

    if rest.startswith("DEADLINE"):
        return Marker(ts=ts, kind="infra_failure", raw=raw, fields={"reason": "deadline_exceeded", "detail": rest})

    first_token = rest.split(" ", 1)[0]
    if first_token.endswith("_FAILED"):
        return Marker(ts=ts, kind="infra_failure", raw=raw, fields={"reason": first_token, "detail": rest})

    return Marker(ts=ts, kind="unknown", raw=raw)


def parse_state_text(text: str) -> List[Marker]:
    """Parses the full contents of a STATE file (or any subset of its lines) into a list of
    `Marker`s, in file order. Blank lines are skipped; every non-blank line produces exactly one
    marker (an unrecognised line becomes `kind="unknown"`, never dropped)."""
    markers: List[Marker] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = TS_LINE.match(line)
        ts, rest = (match.group("ts"), match.group("rest")) if match else (None, line)
        markers.append(_classify(ts, rest, line))
    return markers


def parse_state_file(path: str) -> List[Marker]:
    with open(path) as handle:
        return parse_state_text(handle.read())
