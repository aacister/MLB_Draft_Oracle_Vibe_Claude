"""Tests for the draft-snapshot writer/reader."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import snapshots as snapshots_module
from app.repositories import draft as draft_repo
from app.repositories import pick as pick_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo
from app.snapshots import build_snapshot, read_snapshot, write_snapshot


@pytest.fixture
def isolated_drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(snapshots_module, "DRAFTS_DIR", tmp_path)
    return tmp_path


def _seed(session: Session) -> tuple[str, str, str]:
    draft = draft_repo.create_draft(session, name="D", config={"num_rounds": 4})
    team_a = team_repo.create_team(
        session, draft_id=draft.id, name="Bombers", strategy_name="Power Hitting"
    )
    team_b = team_repo.create_team(
        session, draft_id=draft.id, name="Speedsters", strategy_name="Speed & Defense"
    )
    player_repo.upsert_player(session, 1, "Judge", "NYY", "OF", {"HR": 58})
    pick_repo.create_pick(
        session,
        draft_id=draft.id,
        team_id=team_a.id,
        player_id=1,
        round_=1,
        pick_number=1,
        rationale="Top slugger.",
    )
    session.commit()
    return draft.id, team_a.id, team_b.id


class TestBuildSnapshot:
    def test_returns_none_for_unknown_draft(self, session: Session) -> None:
        assert build_snapshot(session, "nonexistent") is None

    def test_includes_draft_metadata(self, session: Session) -> None:
        draft_id, _, _ = _seed(session)
        snap = build_snapshot(session, draft_id)
        assert snap is not None
        assert snap["draft_id"] == draft_id
        assert snap["name"] == "D"
        assert snap["status"] == "pending"
        assert snap["config"] == {"num_rounds": 4}

    def test_includes_teams_with_picks(self, session: Session) -> None:
        draft_id, team_a, team_b = _seed(session)
        snap = build_snapshot(session, draft_id)
        assert len(snap["teams"]) == 2
        bombers = next(t for t in snap["teams"] if t["id"] == team_a)
        assert bombers["strategy"] == "Power Hitting"
        assert len(bombers["picks"]) == 1
        assert bombers["picks"][0]["player_name"] == "Judge"
        assert bombers["picks"][0]["position"] == "OF"
        speedsters = next(t for t in snap["teams"] if t["id"] == team_b)
        assert speedsters["picks"] == []


class TestWriteAndRead:
    def test_round_trip(self, session: Session, isolated_drafts_dir: Path) -> None:
        draft_id, _, _ = _seed(session)
        written = write_snapshot(session, draft_id)
        assert written is not None
        loaded = read_snapshot(draft_id)
        assert loaded == written

    def test_read_missing_returns_none(self, isolated_drafts_dir: Path) -> None:
        assert read_snapshot("nonexistent") is None

    def test_write_overwrites(self, session: Session, isolated_drafts_dir: Path) -> None:
        draft_id, _, _ = _seed(session)
        write_snapshot(session, draft_id)
        # Status change → snapshot reflects it
        draft_repo.update_status(session, draft_id, "running")
        session.commit()
        write_snapshot(session, draft_id)
        loaded = read_snapshot(draft_id)
        assert loaded["status"] == "running"
