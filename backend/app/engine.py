"""Draft engine: snake-order orchestration of Researcher, Drafter, Grader.

For each pick, the engine:
1. Emits ``pick_starting`` event
2. Calls the Researcher to get candidates
3. Emits ``research_complete``
4. Calls the Drafter; validates the pick; retries with the next candidate on
   failure (max 3 attempts)
5. Persists the pick, writes a pick vector, writes an ADP record + vector,
   rewrites the draft snapshot
6. Emits ``pick_completed``

After all picks, computes ``alignment_score`` for each team, calls the Grader
to narrate the letter, persists the grade, and emits ``team_graded``.

A typed ``DraftError`` is raised if the Drafter cannot produce a valid pick.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.drafter import run_drafter
from app.agents.grader import run_grader
from app.agents.models import Candidate, DraftPick
from app.agents.researcher import run_researcher
from app.embeddings import embed, pick_text
from app.events import emit_event
from app.grading import alignment_score
from app.repositories import adp_record as adp_repo
from app.repositories import draft as draft_repo
from app.repositories import grade as grade_repo
from app.repositories import pick as pick_repo
from app.repositories import player as player_repo
from app.repositories import team as team_repo
from app.snapshots import write_snapshot
from app.vectors import load_pick_vectors, write_adp_vector, write_pick_vector

logger = logging.getLogger(__name__)

DEFAULT_NUM_ROUNDS = 4
DRAFTER_MAX_ATTEMPTS = 3
ALL_POSITIONS = {"C", "1B", "OF", "P"}


class DraftError(RuntimeError):
    """Raised when the engine cannot make progress (e.g., no valid candidates)."""


def _player_dict(player: Any) -> dict[str, Any]:
    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "mlb_team": player.mlb_team,
        "stats": player.stats,
    }


def _pick_summary(pick: Any) -> dict[str, Any]:
    return {
        "round": pick.round,
        "pick_number": pick.pick_number,
        "team_id": pick.team_id,
        "player_id": pick.player_id,
        "player_name": pick.player.name,
        "position": pick.player.position,
        "rationale": pick.rationale,
    }


def _roster_needs(team_picks: list[Any]) -> list[str]:
    filled = {p.player.position for p in team_picks}
    return sorted(ALL_POSITIONS - filled)


def _validate(
    pick: DraftPick,
    team_picks: list[Any],
    drafted_ids: set[int],
    candidate_ids: set[int],
) -> bool:
    """A Drafter pick is valid iff:

    - ``player_id`` is one of the Researcher's candidates (rejects hallucinations)
    - ``player_id`` is not already drafted in this draft
    - ``position`` is not already filled on this team
    """
    if pick.player_id not in candidate_ids:
        return False
    if pick.player_id in drafted_ids:
        return False
    filled = {p.player.position for p in team_picks}
    return pick.position not in filled


def _fallback_pick(
    candidates: list[Candidate],
    team_picks: list[Any],
    drafted_ids: set[int],
) -> DraftPick | None:
    """The highest-ranked candidate (Researcher already sorted them) that
    still has an open position and isn't drafted. Used when the Drafter
    exhausts its retry budget without producing a valid pick.
    """
    filled = {p.player.position for p in team_picks}
    for c in candidates:
        if c.player_id in drafted_ids:
            continue
        if c.position in filled:
            continue
        return DraftPick(
            player_id=c.player_id,
            player_name=c.player_name,
            position=c.position,
            rationale=(
                f"Fallback selection: top Researcher-ranked candidate at {c.position} "
                f"after the Drafter could not produce a valid pick. {c.rationale}"
            ).strip(),
        )
    return None


async def _select_pick(
    candidates: list[Candidate],
    team_picks: list[Any],
    drafted_ids: set[int],
    strategy_name: str,
) -> DraftPick:
    """Loop Drafter calls until a valid pick is produced. Falls back to the
    top valid candidate if the Drafter is uncooperative for too many attempts.
    """
    current_roster = [_pick_summary(p) for p in team_picks]
    candidate_ids = {c.player_id for c in candidates}
    remaining = list(candidates)
    for attempt in range(DRAFTER_MAX_ATTEMPTS):
        if not remaining:
            break
        pick = await run_drafter(remaining, current_roster, strategy_name)
        if _validate(pick, team_picks, drafted_ids, candidate_ids):
            return pick
        reason = (
            "hallucinated id"
            if pick.player_id not in candidate_ids
            else "already drafted" if pick.player_id in drafted_ids else "position filled"
        )
        logger.warning(
            "Drafter attempt %d rejected (%s; player_id=%d position=%s)",
            attempt + 1,
            reason,
            pick.player_id,
            pick.position,
        )
        remaining = [c for c in remaining if c.player_id != pick.player_id]

    # Fallback: the engine should make forward progress rather than crashing.
    fallback = _fallback_pick(candidates, team_picks, drafted_ids)
    if fallback is not None:
        logger.warning(
            "Drafter failed after %d attempts; using fallback %s (%s)",
            DRAFTER_MAX_ATTEMPTS,
            fallback.player_name,
            fallback.position,
        )
        return fallback
    raise DraftError(
        f"No valid candidate found in {len(candidates)} after {DRAFTER_MAX_ATTEMPTS} attempts"
    )


async def _do_pick(
    session: Session, draft: Any, team: Any, round_: int, pick_number: int, season: int
) -> None:
    emit_event(
        draft.id,
        {
            "type": "pick_starting",
            "round": round_,
            "pick_number": pick_number,
            "team_id": team.id,
            "team_name": team.name,
            "strategy": team.strategy_name,
        },
    )

    team_picks = pick_repo.list_picks_for_team(session, team.id)
    drafted_ids = {p.player_id for p in pick_repo.list_picks_for_draft(session, draft.id)}
    available = [
        p for p in player_repo.list_all_players(session) if p.id not in drafted_ids
    ]

    research = await run_researcher(
        strategy_name=team.strategy_name,
        roster_needs=_roster_needs(team_picks),
        available_players=[_player_dict(p) for p in available],
        draft_history=[
            _pick_summary(p) for p in pick_repo.list_picks_for_draft(session, draft.id)
        ],
    )
    emit_event(
        draft.id,
        {
            "type": "research_complete",
            "team_id": team.id,
            "candidates": [c.model_dump() for c in research.candidates],
        },
    )

    chosen = await _select_pick(
        research.candidates, team_picks, drafted_ids, team.strategy_name
    )

    # Resolve the player BEFORE persisting so a hallucinated id from the
    # Researcher can't leave a half-written pick row behind. SQLite doesn't
    # enforce FKs by default, so we have to check ourselves.
    player = player_repo.get_player(session, chosen.player_id)
    if player is None:
        raise DraftError(
            f"Picked player_id={chosen.player_id} ('{chosen.player_name}') "
            "is not in the player pool — agent likely fabricated the id."
        )

    pick_repo.create_pick(
        session,
        draft_id=draft.id,
        team_id=team.id,
        player_id=chosen.player_id,
        round_=round_,
        pick_number=pick_number,
        rationale=chosen.rationale,
    )

    write_pick_vector(
        draft_id=draft.id,
        team_id=team.id,
        strategy=team.strategy_name,
        round_=round_,
        pick_number=pick_number,
        player_id=player.id,
        player_name=player.name,
        position=player.position,
        rationale=chosen.rationale,
        stats_snapshot=player.stats,
    )
    adp_repo.create_adp_record(
        session,
        draft_id=draft.id,
        player_id=player.id,
        pick_number=pick_number,
        season=season,
    )
    write_adp_vector(
        draft_id=draft.id,
        player_id=player.id,
        player_name=player.name,
        position=player.position,
        pick_number=pick_number,
        season=season,
    )

    session.commit()
    write_snapshot(session, draft.id)

    emit_event(
        draft.id,
        {
            "type": "pick_completed",
            "team_id": team.id,
            "pick": {
                "round": round_,
                "pick_number": pick_number,
                "player_id": player.id,
                "player_name": player.name,
                "position": player.position,
                "rationale": chosen.rationale,
            },
        },
    )


async def _grade_team(session: Session, draft: Any, team: Any) -> None:
    picks = pick_repo.list_picks_for_team(session, team.id)
    pick_dicts: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []
    for p in picks:
        snapshot = {
            "player_name": p.player.name,
            "position": p.player.position,
            "rationale": p.rationale,
            "stats_snapshot": p.player.stats,
        }
        pick_dicts.append(snapshot)
        text = pick_text(
            p.player.name, p.player.position, team.strategy_name, p.rationale, p.player.stats
        )
        embeddings.append(embed(text))

    all_vectors = load_pick_vectors()
    score = alignment_score(
        pick_dicts,
        embeddings,
        team.strategy_name,
        current_draft_id=draft.id,
        all_vectors=all_vectors,
    )

    grade = await run_grader(
        team_name=team.name,
        strategy_name=team.strategy_name,
        picks=pick_dicts,
        alignment_score=score,
    )

    grade_repo.create_grade(
        session,
        team_id=team.id,
        draft_id=draft.id,
        alignment_score=score,
        letter=grade.letter,
        rationale=grade.rationale,
    )
    session.commit()

    emit_event(
        draft.id,
        {
            "type": "team_graded",
            "team_id": team.id,
            "team_name": team.name,
            "alignment_score": score,
            "letter": grade.letter,
            "rationale": grade.rationale,
        },
    )


async def run_draft(session: Session, draft_id: str, *, season: int = 2025) -> None:
    """Run a draft to completion: snake-order picks, then grade both teams."""
    draft = draft_repo.get_draft(session, draft_id)
    if draft is None:
        raise DraftError(f"Draft {draft_id} not found")

    teams = team_repo.list_teams_for_draft(session, draft_id)
    if len(teams) != 2:
        raise DraftError(f"Draft {draft_id} must have exactly 2 teams, found {len(teams)}")

    draft_repo.update_status(session, draft_id, "running")
    session.commit()
    emit_event(draft_id, {"type": "draft_started", "name": draft.name})

    num_rounds = int(draft.config.get("num_rounds", DEFAULT_NUM_ROUNDS))
    pick_number = 0
    for round_idx in range(num_rounds):
        round_num = round_idx + 1
        order = teams if round_idx % 2 == 0 else list(reversed(teams))
        for team in order:
            pick_number += 1
            await _do_pick(session, draft, team, round_num, pick_number, season)

    for team in teams:
        await _grade_team(session, draft, team)

    draft_repo.update_status(session, draft_id, "completed")
    session.commit()
    write_snapshot(session, draft_id)
    emit_event(draft_id, {"type": "draft_completed"})
