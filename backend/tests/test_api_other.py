"""HTTP tests for players, analytics, and admin endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import admin as admin_module
from app.repositories import adp_record as adp_repo
from app.repositories import draft as draft_repo
from app.repositories import grade as grade_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestPlayers:
    def test_empty_when_no_players(self, client: TestClient) -> None:
        r = client.get("/v1/players")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_all(self, client: TestClient, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Judge", "NYY", "OF", {"HR": 58})
        player_repo.upsert_player(session, 2, "Realmuto", "PHI", "C", {"HR": 25})
        session.commit()

        r = client.get("/v1/players")
        assert r.status_code == 200
        names = {p["name"] for p in r.json()}
        assert names == {"Judge", "Realmuto"}

    def test_filter_by_position(self, client: TestClient, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Judge", "NYY", "OF", {})
        player_repo.upsert_player(session, 2, "Realmuto", "PHI", "C", {})
        session.commit()

        r = client.get("/v1/players?position=C")
        assert {p["name"] for p in r.json()} == {"Realmuto"}

    def test_search_by_name(self, client: TestClient, session: Session) -> None:
        player_repo.upsert_player(session, 1, "Aaron Judge", "NYY", "OF", {})
        player_repo.upsert_player(session, 2, "Bo Bichette", "TOR", "OF", {})
        session.commit()

        r = client.get("/v1/players?q=judge")
        assert {p["name"] for p in r.json()} == {"Aaron Judge"}


class TestGetGrades:
    def test_404_when_no_grades(self, client: TestClient) -> None:
        r = client.get("/v1/drafts/nope/grade")
        assert r.status_code == 404

    def test_returns_grades_for_draft(self, client: TestClient, session: Session) -> None:
        draft = draft_repo.create_draft(session, name="D")
        team = team_repo.create_team(
            session, draft_id=draft.id, name="T", strategy_name="Power Hitting"
        )
        grade_repo.create_grade(
            session,
            team_id=team.id,
            draft_id=draft.id,
            alignment_score=80,
            letter="B",
            rationale="solid",
        )
        session.commit()

        r = client.get(f"/v1/drafts/{draft.id}/grade")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["letter"] == "B"
        assert rows[0]["alignment_score"] == 80
        assert rows[0]["team_name"] == "T"


class TestLeaderboard:
    def test_empty(self, client: TestClient) -> None:
        r = client.get("/v1/leaderboard")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_avg_score_per_strategy(
        self, client: TestClient, session: Session
    ) -> None:
        for score in (70, 90):
            d = draft_repo.create_draft(session, name=f"D{score}")
            t = team_repo.create_team(
                session, draft_id=d.id, name="T", strategy_name="Power Hitting"
            )
            grade_repo.create_grade(
                session,
                team_id=t.id,
                draft_id=d.id,
                alignment_score=score,
                letter="B",
                rationale="r",
            )
        session.commit()

        r = client.get("/v1/leaderboard")
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["strategy"] == "Power Hitting"
        assert rows[0]["avg_score"] == 80.0


class TestAdpTrends:
    def test_unknown_view_400(self, client: TestClient) -> None:
        r = client.get("/v1/adp/trends?view=bogus")
        assert r.status_code == 400

    def test_overdrafted_view(self, client: TestClient, session: Session) -> None:
        player_repo.upsert_player(session, 1, "P", "NYY", "OF", {"HR": 30})
        for _ in range(3):
            d = draft_repo.create_draft(session, name="D")
            adp_repo.create_adp_record(session, d.id, 1, 5, 2025)
        session.commit()

        r = client.get("/v1/adp/trends?view=overdrafted")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_ignored_positions_view(self, client: TestClient, session: Session) -> None:
        player_repo.upsert_player(session, 1, "P", "NYY", "OF", {})
        d = draft_repo.create_draft(session, name="D")
        adp_repo.create_adp_record(session, d.id, 1, 5, 2025)
        session.commit()

        r = client.get("/v1/adp/trends?view=ignored_positions")
        assert r.status_code == 200


class TestAdminIngest:
    def test_calls_ingest_season(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {}

        def fake_ingest(session, season=2025, limit=75):
            called["season"] = season
            called["limit"] = limit
            return 42

        monkeypatch.setattr(admin_module, "ingest_season", fake_ingest)

        r = client.post("/v1/admin/ingest?season=2024&limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["ingested"] == 42
        assert called == {"season": 2024, "limit": 10}
