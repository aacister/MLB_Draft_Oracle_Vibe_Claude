"""End-to-end engine tests with mocked agents.

Every call to ``run_researcher``, ``run_drafter``, ``run_grader`` is mocked.
Real DB, real embeddings, real file I/O for vectors / snapshots / events.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app import engine as engine_module
from app import events as events_module
from app import snapshots as snapshots_module
from app import vectors as vectors_module
from app.agents.models import Candidate, DraftPick, GradeResult, ResearchResult
from app.engine import DraftError, run_draft
from app.events import read_events
from app.repositories import draft as draft_repo
from app.repositories import grade as grade_repo
from app.repositories import pick as pick_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo
from app.snapshots import read_snapshot


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point all filesystem-touching paths at tmp_path subdirs."""
    drafts = tmp_path / "drafts"
    picks = tmp_path / "vectors" / "picks"
    adp = tmp_path / "vectors" / "adp"
    monkeypatch.setattr(events_module, "DRAFTS_DIR", drafts)
    monkeypatch.setattr(snapshots_module, "DRAFTS_DIR", drafts)
    monkeypatch.setattr(vectors_module, "VECTORS_PICKS_DIR", picks)
    monkeypatch.setattr(vectors_module, "VECTORS_ADP_DIR", adp)
    vectors_module._clear_cache()
    return tmp_path


def _seed_draft(session: Session, num_rounds: int = 2) -> tuple[str, str, str]:
    """Create a draft, two teams, and 4 players (one per position)."""
    draft = draft_repo.create_draft(
        session, name="Test Draft", config={"num_rounds": num_rounds}
    )
    team_a = team_repo.create_team(
        session, draft_id=draft.id, name="Bombers", strategy_name="Power Hitting"
    )
    team_b = team_repo.create_team(
        session, draft_id=draft.id, name="Speedsters", strategy_name="Speed & Defense"
    )
    # Player pool: many players per position so the drafter has options
    pos_players = {
        "OF": [(100, "Judge", {"HR": 58, "RBI": 144, "SB": 12, "AVG": 0.295, "OBP": 0.420, "SLG": 0.690, "R": 130, "AB": 540}),
               (101, "Acuna", {"HR": 30, "SB": 50, "R": 110, "AVG": 0.305, "OBP": 0.390, "SLG": 0.560, "RBI": 80, "AB": 520})],
        "1B": [(200, "Olson", {"HR": 38, "RBI": 110, "SLG": 0.530, "OBP": 0.360, "AVG": 0.260, "R": 85, "AB": 500}),
               (201, "Freeman", {"HR": 28, "RBI": 95, "AVG": 0.330, "OBP": 0.410, "SLG": 0.560, "R": 100, "AB": 550})],
        "C":  [(300, "Realmuto", {"HR": 25, "RBI": 80, "SB": 12, "AVG": 0.275, "OBP": 0.340, "SLG": 0.470, "R": 65, "AB": 480}),
               (301, "Smith", {"HR": 22, "RBI": 75, "AVG": 0.260, "OBP": 0.330, "SLG": 0.430, "R": 60, "AB": 460})],
        "P":  [(400, "deGrom", {"K": 200, "W": 12, "S": 0, "ERA": 2.50, "WHIP": 0.95, "IP": 180}),
               (401, "Hader", {"K": 90, "W": 4, "S": 35, "ERA": 2.10, "WHIP": 0.90, "IP": 65})],
    }
    for pos, players in pos_players.items():
        for pid, name, stats in players:
            player_repo.upsert_player(session, pid, name, "NYY", pos, stats)
    session.commit()
    return draft.id, team_a.id, team_b.id


def _candidate_for(pid: int, name: str, position: str, rank: int = 1) -> Candidate:
    return Candidate(
        player_id=pid,
        player_name=name,
        position=position,
        rank=rank,
        rationale=f"Top {position} on board.",
    )


def _draft_pick_for(pid: int, name: str, position: str) -> DraftPick:
    return DraftPick(
        player_id=pid,
        player_name=name,
        position=position,
        rationale=f"{position} pick — strategy fit.",
    )


@pytest.mark.asyncio
async def test_full_draft_persists_picks_and_grades(
    session: Session, isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_id, team_a, team_b = _seed_draft(session, num_rounds=2)

    # Plan the picks so the engine produces a valid snake draft:
    # Round 1: team_a (Power Hitting) picks Judge OF; team_b (Speed) picks Acuna OF (different player)
    # Round 2 (reversed): team_b picks Olson 1B; team_a picks Freeman 1B
    pick_plan = [
        _draft_pick_for(100, "Judge", "OF"),     # team_a R1
        _draft_pick_for(101, "Acuna", "OF"),     # team_b R1
        _draft_pick_for(200, "Olson", "1B"),     # team_b R2 (snake)
        _draft_pick_for(201, "Freeman", "1B"),   # team_a R2
    ]
    drafter_calls = iter(pick_plan)

    async def fake_researcher(**kwargs):
        # Return all available players as candidates — drafter chooses
        return ResearchResult(candidates=[
            _candidate_for(100, "Judge", "OF", 1),
            _candidate_for(101, "Acuna", "OF", 2),
            _candidate_for(200, "Olson", "1B", 3),
            _candidate_for(201, "Freeman", "1B", 4),
        ])

    async def fake_drafter(*args, **kwargs):
        return next(drafter_calls)

    async def fake_grader(**kwargs):
        return GradeResult(letter="B", rationale="Strong build.")

    monkeypatch.setattr(engine_module, "run_researcher", fake_researcher)
    monkeypatch.setattr(engine_module, "run_drafter", fake_drafter)
    monkeypatch.setattr(engine_module, "run_grader", fake_grader)

    await run_draft(session, draft_id)

    # All 4 picks landed
    picks = pick_repo.list_picks_for_draft(session, draft_id)
    assert len(picks) == 4
    # Snake order: pick_number 1..4 with team_a, team_b, team_b, team_a
    assert [p.pick_number for p in picks] == [1, 2, 3, 4]
    team_a_picks = [p for p in picks if p.team_id == team_a]
    team_b_picks = [p for p in picks if p.team_id == team_b]
    assert len(team_a_picks) == 2
    assert len(team_b_picks) == 2

    # Grades exist for both teams
    grades = grade_repo.list_grades_for_draft(session, draft_id)
    assert len(grades) == 2
    assert all(g.letter == "B" for g in grades)
    assert all(0 <= g.alignment_score <= 100 for g in grades)

    # Draft status is completed
    draft = draft_repo.get_draft(session, draft_id)
    assert draft.status == "completed"

    # 4 pick vectors on disk
    picks_dir = isolated_paths / "vectors" / "picks"
    assert len(list(picks_dir.glob("*.json"))) == 4
    # 4 ADP vectors on disk
    adp_dir = isolated_paths / "vectors" / "adp"
    assert len(list(adp_dir.glob("*.json"))) == 4

    # Snapshot exists and reflects final state
    snap = read_snapshot(draft_id)
    assert snap is not None
    assert snap["status"] == "completed"
    assert all(len(t["picks"]) == 2 for t in snap["teams"])

    # Events: draft_started, pick_starting/research_complete/pick_completed *4, team_graded *2, draft_completed
    events = read_events(draft_id)
    types = [e["type"] for e in events]
    assert types[0] == "draft_started"
    assert types.count("pick_starting") == 4
    assert types.count("research_complete") == 4
    assert types.count("pick_completed") == 4
    assert types.count("team_graded") == 2
    assert types[-1] == "draft_completed"


@pytest.mark.asyncio
async def test_drafter_retry_skips_invalid_pick(
    session: Session, isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First attempt picks an already-drafted player; engine retries with next candidate."""
    draft_id, team_a, team_b = _seed_draft(session, num_rounds=1)

    # Seed Judge as already drafted by team_b (round 0, not part of the snake)
    pick_repo.create_pick(
        session,
        draft_id=draft_id,
        team_id=team_b,
        player_id=100,
        round_=0,
        pick_number=0,
        rationale="seed",
    )
    session.commit()

    drafter_returns = iter([
        _draft_pick_for(100, "Judge", "OF"),     # team_a attempt 1 — invalid (already drafted)
        _draft_pick_for(101, "Acuna", "OF"),     # team_a attempt 2 — valid
        _draft_pick_for(200, "Olson", "1B"),     # team_b — valid (different pos than seed)
    ])

    async def fake_researcher(**kwargs):
        return ResearchResult(candidates=[
            _candidate_for(100, "Judge", "OF", 1),
            _candidate_for(101, "Acuna", "OF", 2),
            _candidate_for(200, "Olson", "1B", 3),
        ])

    async def fake_drafter(*args, **kwargs):
        return next(drafter_returns)

    async def fake_grader(**kwargs):
        return GradeResult(letter="C", rationale="OK.")

    monkeypatch.setattr(engine_module, "run_researcher", fake_researcher)
    monkeypatch.setattr(engine_module, "run_drafter", fake_drafter)
    monkeypatch.setattr(engine_module, "run_grader", fake_grader)

    await run_draft(session, draft_id)

    # Team A's new pick should be Acuna (the retry), not the rejected Judge
    team_a_picks = pick_repo.list_picks_for_team(session, team_a)
    new_picks = [p for p in team_a_picks if p.round > 0]
    assert len(new_picks) == 1
    assert new_picks[0].player_id == 101


@pytest.mark.asyncio
async def test_drafter_hallucinated_id_falls_back(
    session: Session, isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drafter returning a player_id NOT in the candidate list is rejected;
    after the retry budget is exhausted the engine falls back to the top
    valid candidate instead of raising.
    """
    draft_id, team_a, _ = _seed_draft(session, num_rounds=1)

    async def fake_researcher(**_kwargs):
        return ResearchResult(candidates=[
            _candidate_for(100, "Judge", "OF", 1),
            _candidate_for(200, "Olson", "1B", 2),
        ])

    # Drafter consistently hallucinates an id (999999) not in the candidates.
    async def fake_drafter(*_args, **_kwargs):
        return _draft_pick_for(999999, "Phantom", "OF")

    async def fake_grader(**_kwargs):
        return GradeResult(letter="C", rationale="OK.")

    monkeypatch.setattr(engine_module, "run_researcher", fake_researcher)
    monkeypatch.setattr(engine_module, "run_drafter", fake_drafter)
    monkeypatch.setattr(engine_module, "run_grader", fake_grader)

    await run_draft(session, draft_id)

    # The engine must NOT have inserted a pick with the hallucinated id.
    team_a_picks = pick_repo.list_picks_for_team(session, team_a)
    new_picks = [p for p in team_a_picks if p.round > 0]
    assert len(new_picks) == 1
    assert new_picks[0].player_id != 999999
    # The fallback must have picked the top valid candidate (Judge, id=100).
    assert new_picks[0].player_id == 100
    assert "Fallback" in new_picks[0].rationale


@pytest.mark.asyncio
async def test_engine_raises_on_unknown_draft(session: Session, isolated_paths: Path) -> None:
    with pytest.raises(DraftError):
        await run_draft(session, "does-not-exist")


@pytest.mark.asyncio
async def test_engine_raises_when_team_count_wrong(
    session: Session, isolated_paths: Path
) -> None:
    draft = draft_repo.create_draft(session, name="Solo")
    # Only one team
    team_repo.create_team(
        session, draft_id=draft.id, name="X", strategy_name="Power Hitting"
    )
    session.commit()

    with pytest.raises(DraftError, match="2 teams"):
        await run_draft(session, draft.id)
