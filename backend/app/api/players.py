"""Players endpoint: search/filter the 2025 player pool."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.schemas import PlayerOut
from app.repositories import player as player_repo

router = APIRouter(tags=["players"])


@router.get("/players", response_model=list[PlayerOut])
def list_players(
    position: str | None = Query(default=None, description="C, 1B, OF, or P"),
    q: str | None = Query(default=None, description="Substring match against name"),
    session: Session = Depends(get_session),
) -> list[PlayerOut]:
    """Return players filtered by position and/or name substring."""
    players = (
        player_repo.list_players_by_position(session, position)
        if position
        else player_repo.list_all_players(session)
    )
    if q:
        q_lower = q.lower()
        players = [p for p in players if q_lower in p.name.lower()]
    return [
        PlayerOut(
            id=p.id, name=p.name, mlb_team=p.mlb_team, position=p.position, stats=p.stats
        )
        for p in players
    ]
