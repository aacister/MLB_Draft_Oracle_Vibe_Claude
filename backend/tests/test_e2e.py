"""End-to-end test: full 2-team / 2-round draft through the HTTP API.

Mocks the LLM (all 3 agents) and indirectly web search (Researcher is mocked).
Asserts both grade rows exist and the expected pick vectors land on disk.

This is the canonical CLAUDE.MD §Coding Conventions e2e test.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import engine as engine_module
from app.agents.models import Candidate, DraftPick, GradeResult, ResearchResult
from app.repositories import player as player_repo


def _seed_player_pool(session: Session) -> None:
    """Six players, one or two per draftable position, with realistic stats."""
    players = [
        (100, "Aaron Judge", "OF",
         {"HR": 58, "RBI": 144, "R": 130, "SB": 12, "AVG": 0.295,
          "OBP": 0.420, "SLG": 0.690, "AB": 540}),
        (101, "Ronald Acuna", "OF",
         {"HR": 30, "RBI": 80, "R": 110, "SB": 50, "AVG": 0.305,
          "OBP": 0.390, "SLG": 0.560, "AB": 520}),
        (200, "Matt Olson", "1B",
         {"HR": 38, "RBI": 110, "R": 85, "SB": 1, "AVG": 0.260,
          "OBP": 0.360, "SLG": 0.530, "AB": 500}),
        (201, "Freddie Freeman", "1B",
         {"HR": 28, "RBI": 95, "R": 100, "SB": 6, "AVG": 0.330,
          "OBP": 0.410, "SLG": 0.560, "AB": 550}),
        (300, "J.T. Realmuto", "C",
         {"HR": 25, "RBI": 80, "R": 65, "SB": 12, "AVG": 0.275,
          "OBP": 0.340, "SLG": 0.470, "AB": 480}),
        (400, "Jacob deGrom", "P",
         {"K": 200, "W": 12, "S": 0, "ERA": 2.50, "WHIP": 0.95, "IP": 180}),
    ]
    for pid, name, pos, stats in players:
        player_repo.upsert_player(session, pid, name, "NYY", pos, stats)
    session.commit()


def _wait_for_status(client: TestClient, draft_id: str, target: str, timeout: float = 10.0) -> str:
    """Poll GET /drafts/{id} until status hits target. Return last seen status."""
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        r = client.get(f"/v1/drafts/{draft_id}")
        assert r.status_code == 200, r.text
        last_status = r.json()["status"]
        if last_status == target:
            return last_status
        time.sleep(0.1)
    return last_status


def test_e2e_two_team_two_round_draft(
    client: TestClient,
    session: Session,
    isolated_paths: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical end-to-end test: full HTTP lifecycle, mocked LLM + search."""
    _seed_player_pool(session)

    # The Researcher always returns the full candidate list; the Drafter picks
    # in this exact order. With snake order (round 2 reversed), team A picks
    # rounds 1 and 4 (positions in iter slots 0 and 3); team B picks slots 1 and 2.
    pick_plan = iter([
        DraftPick(player_id=100, player_name="Aaron Judge", position="OF",
                  rationale="Top slugger in the pool — fits Power Hitting."),
        DraftPick(player_id=101, player_name="Ronald Acuna", position="OF",
                  rationale="Elite SB total — fits Speed & Defense."),
        DraftPick(player_id=200, player_name="Matt Olson", position="1B",
                  rationale="Power corner."),
        DraftPick(player_id=400, player_name="Jacob deGrom", position="P",
                  rationale="Ace pitching to round out."),
    ])

    async def fake_researcher(**_kwargs: object) -> ResearchResult:
        return ResearchResult(candidates=[
            Candidate(player_id=100, player_name="Aaron Judge", position="OF", rank=1, rationale="r"),
            Candidate(player_id=101, player_name="Ronald Acuna", position="OF", rank=2, rationale="r"),
            Candidate(player_id=200, player_name="Matt Olson", position="1B", rank=3, rationale="r"),
            Candidate(player_id=201, player_name="Freddie Freeman", position="1B", rank=4, rationale="r"),
            Candidate(player_id=300, player_name="J.T. Realmuto", position="C", rank=5, rationale="r"),
            Candidate(player_id=400, player_name="Jacob deGrom", position="P", rank=6, rationale="r"),
        ])

    async def fake_drafter(*_args: object, **_kwargs: object) -> DraftPick:
        return next(pick_plan)

    async def fake_grader(**_kwargs: object) -> GradeResult:
        return GradeResult(letter="B", rationale="Solid draft execution.")

    monkeypatch.setattr(engine_module, "run_researcher", fake_researcher)
    monkeypatch.setattr(engine_module, "run_drafter", fake_drafter)
    monkeypatch.setattr(engine_module, "run_grader", fake_grader)

    # 1) Create draft via HTTP
    r = client.post("/v1/drafts", json={
        "strategy_a": "Power Hitting",
        "strategy_b": "Speed & Defense",
        "num_rounds": 2,
    })
    assert r.status_code == 200, r.text
    draft = r.json()
    draft_id = draft["id"]
    assert draft["status"] == "pending"
    assert len(draft["teams"]) == 2

    # 2) Trigger the engine via HTTP (background asyncio task)
    r = client.post(f"/v1/drafts/{draft_id}/run")
    assert r.status_code == 200
    assert r.json()["status"] == "running"

    # 3) Poll status via HTTP until the background engine reaches "completed"
    final = _wait_for_status(client, draft_id, "completed")
    assert final == "completed", f"draft did not complete (status={final})"

    # 4) Verify grades via HTTP — exactly two grades, one per team
    r = client.get(f"/v1/drafts/{draft_id}/grade")
    assert r.status_code == 200
    grades = r.json()
    assert len(grades) == 2
    assert all(g["letter"] == "B" for g in grades)
    assert all(0 <= g["alignment_score"] <= 100 for g in grades)
    assert {g["strategy"] for g in grades} == {"Power Hitting", "Speed & Defense"}

    # 5) Verify pick vectors on disk — 2 teams × 2 rounds = 4
    picks_dir = isolated_paths / "memory" / "vectors" / "picks"
    pick_files = list(picks_dir.glob("*.json"))
    assert len(pick_files) == 4, f"expected 4 pick vectors, got {len(pick_files)}"

    # 6) Verify ADP vectors — one per pick
    adp_dir = isolated_paths / "memory" / "vectors" / "adp"
    adp_files = list(adp_dir.glob("*.json"))
    assert len(adp_files) == 4

    # 7) Verify event log contains the expected sequence of event types
    events_log = isolated_paths / "memory" / "drafts" / f"{draft_id}.events.jsonl"
    assert events_log.exists()
    import json
    events = [json.loads(line) for line in events_log.read_text().splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert types[0] == "draft_started"
    assert types.count("pick_starting") == 4
    assert types.count("research_complete") == 4
    assert types.count("pick_completed") == 4
    assert types.count("team_graded") == 2
    assert types[-1] == "draft_completed"

    # 8) Verify draft snapshot reflects the completed state
    r = client.get(f"/v1/drafts/{draft_id}")
    snap = r.json()
    assert snap["status"] == "completed"
    assert all(len(t["picks"]) == 2 for t in snap["teams"])
