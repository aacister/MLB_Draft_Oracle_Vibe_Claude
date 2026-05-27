"""Tests for the analytics SQL queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics import (
    avg_score_by_strategy,
    ignored_positions,
    overdrafted_players,
    season_shift,
)
from app.repositories import adp_record as adp_repo
from app.repositories import draft as draft_repo
from app.repositories import grade as grade_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo


def _seed_draft_with_grade(session: Session, strategy: str, score: int) -> str:
    draft = draft_repo.create_draft(session, name=f"D-{strategy}-{score}")
    team = team_repo.create_team(
        session, draft_id=draft.id, name="T", strategy_name=strategy
    )
    grade_repo.create_grade(
        session,
        team_id=team.id,
        draft_id=draft.id,
        alignment_score=score,
        letter="B",
        rationale="r",
    )
    session.commit()
    return draft.id


class TestAvgScoreByStrategy:
    def test_empty_returns_empty(self, session: Session) -> None:
        assert avg_score_by_strategy(session) == []

    def test_groups_and_averages(self, session: Session) -> None:
        _seed_draft_with_grade(session, "Power Hitting", 80)
        _seed_draft_with_grade(session, "Power Hitting", 90)
        _seed_draft_with_grade(session, "Speed & Defense", 60)
        rows = avg_score_by_strategy(session)
        by_strat = {r["strategy"]: r for r in rows}
        assert by_strat["Power Hitting"]["avg_score"] == 85.0
        assert by_strat["Power Hitting"]["drafts"] == 2
        assert by_strat["Speed & Defense"]["avg_score"] == 60.0

    def test_filter_by_strategy(self, session: Session) -> None:
        _seed_draft_with_grade(session, "Power Hitting", 80)
        _seed_draft_with_grade(session, "Speed & Defense", 70)
        rows = avg_score_by_strategy(session, strategy="Power Hitting")
        assert len(rows) == 1
        assert rows[0]["strategy"] == "Power Hitting"


class TestOverdraftedPlayers:
    def test_filters_by_min_appearances(self, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Solo", "NYY", "OF", {"HR": 30})
        d1 = draft_repo.create_draft(session, name="D1")
        adp_repo.create_adp_record(session, d1.id, 1, 2, 2025)
        session.commit()
        # Only 1 appearance — below default min_appearances=3
        assert overdrafted_players(session) == []
        assert len(overdrafted_players(session, min_appearances=1)) == 1

    def test_includes_player_metadata(self, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Judge", "NYY", "OF", {"HR": 58})
        d1 = draft_repo.create_draft(session, name="D1")
        d2 = draft_repo.create_draft(session, name="D2")
        d3 = draft_repo.create_draft(session, name="D3")
        for d in (d1, d2, d3):
            adp_repo.create_adp_record(session, d.id, 1, 1, 2025)
        session.commit()
        rows = overdrafted_players(session)
        assert len(rows) == 1
        assert rows[0]["player_name"] == "Judge"
        assert rows[0]["mean_pick"] == 1.0
        assert rows[0]["appearances"] == 3
        assert rows[0]["hr"] == 58


class TestIgnoredPositions:
    def test_empty_when_no_adp(self, session: Session) -> None:
        assert ignored_positions(session) == []

    def test_marks_above_median(self, session: Session) -> None:
        for pid, pos in [(1, "C"), (2, "1B"), (3, "OF"), (4, "P")]:
            player_repo.upsert_player(session, pid, f"P{pid}", "NYY", pos, {})
        d = draft_repo.create_draft(session, name="D")
        # Picks: C=8 (late), 1B=3, OF=1 (early), P=5
        adp_repo.create_adp_record(session, d.id, 1, 8, 2025)
        adp_repo.create_adp_record(session, d.id, 2, 3, 2025)
        adp_repo.create_adp_record(session, d.id, 3, 1, 2025)
        adp_repo.create_adp_record(session, d.id, 4, 5, 2025)
        session.commit()
        rows = ignored_positions(session)
        by_pos = {r["position"]: r for r in rows}
        # Median of [1,3,5,8] sorted is 5; positions with mean_pick > 5 are above
        assert by_pos["C"]["above_median"] is True
        assert by_pos["OF"]["above_median"] is False


class TestSeasonShift:
    def test_empty_when_no_data(self, session: Session) -> None:
        assert season_shift(session) == []

    def test_rolling_mean_smooths_across_drafts(self, session: Session) -> None:
        import time as _time
        player_repo.upsert_player(session, 1, "P", "NYY", "OF", {})
        d1 = draft_repo.create_draft(session, name="D1")
        _time.sleep(0.02)  # Windows datetime.now() ~16ms resolution; force a gap
        d2 = draft_repo.create_draft(session, name="D2")
        adp_repo.create_adp_record(session, d1.id, 1, 10, 2025)
        adp_repo.create_adp_record(session, d2.id, 1, 20, 2025)
        session.commit()
        rows = season_shift(session, window=2)
        assert len(rows) == 2
        assert rows[0]["rolling_mean_pick"] == 10.0  # only d1 in window
        assert rows[1]["rolling_mean_pick"] == 15.0  # avg(10, 20)
