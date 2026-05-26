"""Repository functions for the Pick table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Pick


def create_pick(
    session: Session,
    draft_id: str,
    team_id: str,
    player_id: int,
    round_: int,
    pick_number: int,
    rationale: str,
) -> Pick:
    """Insert a new pick and return it."""
    pick = Pick(
        draft_id=draft_id,
        team_id=team_id,
        player_id=player_id,
        round=round_,
        pick_number=pick_number,
        rationale=rationale,
    )
    session.add(pick)
    session.flush()
    return pick


def list_picks_for_draft(session: Session, draft_id: str) -> list[Pick]:
    """Return all picks in a draft in pick-number order."""
    return list(
        session.scalars(
            select(Pick).where(Pick.draft_id == draft_id).order_by(Pick.pick_number)
        )
    )


def list_picks_for_team(session: Session, team_id: str) -> list[Pick]:
    """Return a single team's picks in pick-number order."""
    return list(
        session.scalars(
            select(Pick).where(Pick.team_id == team_id).order_by(Pick.pick_number)
        )
    )
