"""Per-draft append-only event log used for SSE streaming.

Events live at ``./memory/drafts/<draft_id>.events.jsonl`` (one JSON object per
line). Each event has a sequential string id so SSE clients can resume via
``Last-Event-ID``.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from app.paths import DRAFTS_DIR


def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _log_path(draft_id: str) -> Any:
    return DRAFTS_DIR / f"{draft_id}.events.jsonl"


def _count_events(path: Any) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def emit_event(draft_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append an event to the draft's log. Returns the full event (with id, ts)."""
    path = _log_path(draft_id)
    next_id = _count_events(path) + 1
    event = {**payload, "id": str(next_id), "ts": _utcnow_iso(), "draft_id": draft_id}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return event


def read_events(draft_id: str, *, since_id: str | None = None) -> list[dict[str, Any]]:
    """Read events for a draft, optionally starting after ``since_id``."""
    path = _log_path(draft_id)
    if not path.exists():
        return []
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if since_id is None:
        return events
    for i, ev in enumerate(events):
        if ev.get("id") == since_id:
            return events[i + 1 :]
    return events
