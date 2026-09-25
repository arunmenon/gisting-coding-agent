"""The append-only spend ledger (steno-design.md section 2, "Compute backends").

"The ledger becomes a JSONL the loop writes on create, sync and destroy;
``ledger.md`` is rendered from it." This module writes one JSONL entry per
event and renders a Markdown table on demand; it never rewrites history.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

LEDGER_FILENAME = "ledger.jsonl"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ledger_path(run_dir: str) -> str:
    return os.path.join(run_dir, LEDGER_FILENAME)


def append_event(
    run_dir: str,
    event: str,
    *,
    resource_id: str,
    spend_usd_estimate: float,
    detail: str = "",
) -> None:
    """Appends one ledger row. event is one of "provision", "sync", "destroy"."""
    os.makedirs(run_dir, exist_ok=True)
    row = {
        "time": _now_iso(),
        "event": event,
        "resource_id": resource_id,
        "spend_usd_estimate": round(float(spend_usd_estimate), 6),
        "detail": detail,
    }
    with open(ledger_path(run_dir), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_events(run_dir: str) -> list[dict[str, Any]]:
    path = ledger_path(run_dir)
    if not os.path.exists(path):
        return []
    events = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def render_markdown(run_dir: str) -> str:
    """Renders the ledger at run_dir as a Markdown table, newest event last."""
    events = read_events(run_dir)
    lines = ["| time | event | resource_id | spend_usd_estimate | detail |", "| --- | --- | --- | --- | --- |"]
    for row in events:
        lines.append(
            f"| {row.get('time', '')} | {row.get('event', '')} | {row.get('resource_id', '')} "
            f"| {row.get('spend_usd_estimate', '')} | {row.get('detail', '')} |"
        )
    if not events:
        lines.append("| (no events recorded) | | | | |")
    return "\n".join(lines) + "\n"
