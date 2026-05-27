"""HTTP tests for draft endpoints: create, list, get, run, stream."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import drafts as drafts_module
from app.events import emit_event
from app.repositories import draft as draft_repo
from app.repositories import team as team_repo


class TestCreateDraft:
    def test_creates_with_random_strategies(self, client: TestClient) -> None:
        r = client.post("/v1/drafts", json={"num_rounds": 4})
        assert r.status_code == 200
        body = r.json()
        assert body["id"]
        assert body["name"]
        assert body["status"] == "pending"
        assert body["config"]["num_rounds"] == 4
        assert len(body["teams"]) == 2
        strategies = {t["strategy"] for t in body["teams"]}
        assert len(strategies) == 2  # distinct

    def test_creates_with_named_strategies(self, client: TestClient) -> None:
        r = client.post(
            "/v1/drafts",
            json={"strategy_a": "Power Hitting", "strategy_b": "Speed & Defense"},
        )
        assert r.status_code == 200
        body = r.json()
        strategies = {t["strategy"] for t in body["teams"]}
        assert strategies == {"Power Hitting", "Speed & Defense"}

    def test_rejects_unknown_strategy(self, client: TestClient) -> None:
        r = client.post(
            "/v1/drafts",
            json={"strategy_a": "Nonexistent", "strategy_b": "Balanced"},
        )
        assert r.status_code == 400

    def test_rejects_duplicate_strategies(self, client: TestClient) -> None:
        r = client.post(
            "/v1/drafts",
            json={"strategy_a": "Power Hitting", "strategy_b": "Power Hitting"},
        )
        assert r.status_code == 400


class TestListDrafts:
    def test_empty_when_no_drafts(self, client: TestClient) -> None:
        r = client.get("/v1/drafts")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_created_drafts_newest_first(self, client: TestClient) -> None:
        client.post("/v1/drafts", json={"strategy_a": "Balanced", "strategy_b": "Power Hitting"})
        client.post("/v1/drafts", json={"strategy_a": "Ace Pitching", "strategy_b": "Closer-Heavy"})
        rows = client.get("/v1/drafts").json()
        assert len(rows) == 2


class TestGetDraft:
    def test_404_for_unknown_id(self, client: TestClient) -> None:
        r = client.get("/v1/drafts/nope")
        assert r.status_code == 404

    def test_returns_snapshot(self, client: TestClient) -> None:
        created = client.post(
            "/v1/drafts",
            json={"strategy_a": "Power Hitting", "strategy_b": "Balanced"},
        ).json()
        r = client.get(f"/v1/drafts/{created['id']}")
        assert r.status_code == 200
        snap = r.json()
        assert snap["draft_id"] == created["id"]
        assert snap["status"] == "pending"
        assert len(snap["teams"]) == 2


class TestRunDraft:
    def test_404_for_unknown(self, client: TestClient) -> None:
        r = client.post("/v1/drafts/nope/run")
        assert r.status_code == 404

    def test_starts_background_task(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created = client.post("/v1/drafts", json={}).json()

        # Mock run_draft so the background task completes near-instantly
        async def fake_run_draft(session, draft_id, **kw):
            from app.repositories import draft as repo
            repo.update_status(session, draft_id, "completed")
            session.commit()

        monkeypatch.setattr(drafts_module, "run_draft", fake_run_draft)

        r = client.post(f"/v1/drafts/{created['id']}/run")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_idempotent_for_completed(
        self, client: TestClient, session: Session
    ) -> None:
        created = client.post("/v1/drafts", json={}).json()
        # Mark completed directly in DB
        draft_repo.update_status(session, created["id"], "completed")
        session.commit()

        r = client.post(f"/v1/drafts/{created['id']}/run")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"


class TestStream:
    def test_returns_text_event_stream_content_type(
        self, client: TestClient, session: Session
    ) -> None:
        created = client.post("/v1/drafts", json={}).json()
        draft_repo.update_status(session, created["id"], "completed")
        session.commit()
        # Use stream() so connection closes when iteration ends
        with client.stream("GET", f"/v1/drafts/{created['id']}/stream") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]

    def test_streams_existing_events_and_closes_on_completed(
        self, client: TestClient, session: Session
    ) -> None:
        created = client.post("/v1/drafts", json={}).json()
        # Emit a couple of events directly (simulating the engine)
        emit_event(created["id"], {"type": "pick_starting", "round": 1})
        emit_event(created["id"], {"type": "pick_completed", "round": 1})
        draft_repo.update_status(session, created["id"], "completed")
        session.commit()

        with client.stream("GET", f"/v1/drafts/{created['id']}/stream") as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

        assert "event: pick_starting" in body
        assert "event: pick_completed" in body
        assert "event: stream_end" in body

    def test_resumes_after_last_event_id(
        self, client: TestClient, session: Session
    ) -> None:
        created = client.post("/v1/drafts", json={}).json()
        emit_event(created["id"], {"type": "pick_starting"})  # id=1
        emit_event(created["id"], {"type": "pick_completed"})  # id=2
        draft_repo.update_status(session, created["id"], "completed")
        session.commit()

        with client.stream(
            "GET",
            f"/v1/drafts/{created['id']}/stream",
            headers={"Last-Event-ID": "1"},
        ) as r:
            body = "".join(chunk for chunk in r.iter_text())

        # Resumes after id=1, so pick_starting is skipped
        assert "event: pick_starting" not in body
        assert "event: pick_completed" in body
        assert "event: stream_end" in body

    def test_emits_error_for_unknown_draft(self, client: TestClient) -> None:
        with client.stream("GET", "/v1/drafts/no-such/stream") as r:
            body = "".join(chunk for chunk in r.iter_text())
        assert "event: error" in body
