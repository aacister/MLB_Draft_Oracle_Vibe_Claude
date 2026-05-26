"""Repository functions for the Team table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Team


def create_team(session: Session, draft_id: str, name: str, strategy_name: str) -> Team:
    """Insert a new team and return it."""
    team = Team(draft_id=draft_id, name=name, strategy_name=strategy_name)
    session.add(team)
    session.flush()
    return team


def get_team(session: Session, team_id: str) -> Team | None:
    """Return the team with the given id, or None."""
    return session.get(Team, team_id)


def list_teams_for_draft(session: Session, draft_id: str) -> list[Team]:
    """Return both teams for a given draft."""
    return list(session.scalars(select(Team).where(Team.draft_id == draft_id)))
