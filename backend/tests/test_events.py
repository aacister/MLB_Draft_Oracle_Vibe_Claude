"""Tests for the per-draft append-only event log."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import events as events_module
from app.events import emit_event, read_events


@pytest.fixture
def isolated_drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(events_module, "DRAFTS_DIR", tmp_path)
    return tmp_path


class TestEmitEvent:
    def test_first_event_has_id_one(self, isolated_drafts_dir: Path) -> None:
        ev = emit_event("d1", {"type": "pick_starting"})
        assert ev["id"] == "1"
        assert ev["type"] == "pick_starting"
        assert ev["draft_id"] == "d1"
        assert "ts" in ev

    def test_ids_are_sequential(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "a"})
        emit_event("d1", {"type": "b"})
        ev3 = emit_event("d1", {"type": "c"})
        assert ev3["id"] == "3"

    def test_separate_drafts_have_separate_ids(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "x"})
        emit_event("d1", {"type": "y"})
        ev_d2 = emit_event("d2", {"type": "z"})
        assert ev_d2["id"] == "1"

    def test_writes_to_jsonl_file(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "a"})
        emit_event("d1", {"type": "b"})
        log = isolated_drafts_dir / "d1.events.jsonl"
        assert log.exists()
        lines = log.read_text().splitlines()
        assert len(lines) == 2


class TestReadEvents:
    def test_empty_log_returns_empty(self, isolated_drafts_dir: Path) -> None:
        assert read_events("nonexistent") == []

    def test_returns_all_events(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "a"})
        emit_event("d1", {"type": "b"})
        emit_event("d1", {"type": "c"})
        events = read_events("d1")
        assert [e["type"] for e in events] == ["a", "b", "c"]

    def test_since_id_filters(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "a"})
        emit_event("d1", {"type": "b"})
        emit_event("d1", {"type": "c"})
        events = read_events("d1", since_id="1")
        assert [e["type"] for e in events] == ["b", "c"]

    def test_unknown_since_id_returns_all(self, isolated_drafts_dir: Path) -> None:
        emit_event("d1", {"type": "a"})
        events = read_events("d1", since_id="999")
        assert [e["type"] for e in events] == ["a"]
