"""CRUD tests for each repository module."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.repositories import adp_record as adp_repo
from app.repositories import draft as draft_repo
from app.repositories import grade as grade_repo
from app.repositories import pick as pick_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo


def _seed_draft_with_team(session: Session) -> tuple[str, str]:
    draft = draft_repo.create_draft(session, name="Test Draft")
    team = team_repo.create_team(
        session, draft_id=draft.id, name="Bombers", strategy_name="Power Hitting"
    )
    return draft.id, team.id


def _seed_player(session: Session, player_id: int = 12345) -> int:
    player_repo.upsert_player(
        session,
        player_id=player_id,
        name="Aaron Judge",
        mlb_team="NYY",
        position="OF",
        stats={"HR": 58, "RBI": 144},
    )
    return player_id


class TestDraftRepo:
    def test_create_and_get(self, session: Session) -> None:
        draft = draft_repo.create_draft(session, name="My Draft", config={"num_rounds": 4})
        assert draft.id
        assert draft.config == {"num_rounds": 4}

        fetched = draft_repo.get_draft(session, draft.id)
        assert fetched is not None
        assert fetched.name == "My Draft"

    def test_list_orders_newest_first(self, session: Session) -> None:
        d1 = draft_repo.create_draft(session, name="First")
        time.sleep(0.02)  # Windows datetime.now has ~16ms resolution; force a gap
        d2 = draft_repo.create_draft(session, name="Second")
        all_drafts = draft_repo.list_drafts(session)
        assert [d.id for d in all_drafts] == [d2.id, d1.id]

    def test_update_status(self, session: Session) -> None:
        draft = draft_repo.create_draft(session, name="X")
        updated = draft_repo.update_status(session, draft.id, "running")
        assert updated is not None
        assert updated.status == "running"

    def test_update_status_missing_returns_none(self, session: Session) -> None:
        assert draft_repo.update_status(session, "no-such-id", "running") is None


class TestTeamRepo:
    def test_create_and_list(self, session: Session) -> None:
        draft_id, _ = _seed_draft_with_team(session)
        team_repo.create_team(
            session, draft_id=draft_id, name="Speedsters", strategy_name="Speed & Defense"
        )
        teams = team_repo.list_teams_for_draft(session, draft_id)
        assert {t.name for t in teams} == {"Bombers", "Speedsters"}

    def test_get(self, session: Session) -> None:
        _, team_id = _seed_draft_with_team(session)
        team = team_repo.get_team(session, team_id)
        assert team is not None
        assert team.strategy_name == "Power Hitting"


class TestPlayerRepo:
    def test_upsert_inserts_then_updates(self, session: Session) -> None:
        p1 = player_repo.upsert_player(
            session, 1, "A", "NYY", "OF", {"HR": 10}
        )
        assert p1.stats == {"HR": 10}

        p2 = player_repo.upsert_player(
            session, 1, "A", "NYY", "OF", {"HR": 20}
        )
        assert p2.id == p1.id
        assert p2.stats == {"HR": 20}
        assert len(player_repo.list_all_players(session)) == 1

    def test_list_by_position(self, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Catcher A", "NYY", "C", {})
        player_repo.upsert_player(session, 2, "Outfielder A", "NYY", "OF", {})
        player_repo.upsert_player(session, 3, "Outfielder B", "BOS", "OF", {})

        ofs = player_repo.list_players_by_position(session, "OF")
        assert {p.id for p in ofs} == {2, 3}


class TestPickRepo:
    def test_create_and_list(self, session: Session) -> None:
        draft_id, team_id = _seed_draft_with_team(session)
        player_id = _seed_player(session)

        pick = pick_repo.create_pick(
            session,
            draft_id=draft_id,
            team_id=team_id,
            player_id=player_id,
            round_=1,
            pick_number=1,
            rationale="Top of board.",
        )
        assert pick.id

        picks = pick_repo.list_picks_for_draft(session, draft_id)
        assert len(picks) == 1
        assert picks[0].rationale == "Top of board."

    def test_list_for_team(self, session: Session) -> None:
        draft_id, team_id = _seed_draft_with_team(session)
        player_id = _seed_player(session)
        pick_repo.create_pick(session, draft_id, team_id, player_id, 1, 1, "r1")

        picks = pick_repo.list_picks_for_team(session, team_id)
        assert len(picks) == 1


class TestGradeRepo:
    def test_create_and_list(self, session: Session) -> None:
        draft_id, team_id = _seed_draft_with_team(session)

        grade = grade_repo.create_grade(
            session,
            team_id=team_id,
            draft_id=draft_id,
            alignment_score=88,
            letter="B",
            rationale="Solid build.",
        )
        assert grade.id

        grades = grade_repo.list_grades_for_draft(session, draft_id)
        assert len(grades) == 1
        assert grades[0].letter == "B"


class TestAdpRecordRepo:
    def test_create_and_list_for_player(self, session: Session) -> None:
        draft_id, _ = _seed_draft_with_team(session)
        player_id = _seed_player(session)

        adp_repo.create_adp_record(
            session, draft_id=draft_id, player_id=player_id, pick_number=3, season=2025
        )
        records = adp_repo.list_adp_records_for_player(session, player_id)
        assert len(records) == 1
        assert records[0].pick_number == 3
