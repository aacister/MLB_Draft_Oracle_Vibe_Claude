"""Repository functions for the Player table."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Player


def upsert_player(
    session: Session,
    player_id: int,
    name: str,
    mlb_team: str,
    position: str,
    stats: dict[str, Any],
) -> Player:
    """Insert or update a player by natural id. Used by 2025-season ingestion."""
    player = session.get(Player, player_id)
    if player is None:
        player = Player(
            id=player_id, name=name, mlb_team=mlb_team, position=position, stats=stats
        )
        session.add(player)
    else:
        player.name = name
        player.mlb_team = mlb_team
        player.position = position
        player.stats = stats
    session.flush()
    return player


def get_player(session: Session, player_id: int) -> Player | None:
    """Return the player with the given MLB id, or None."""
    return session.get(Player, player_id)


def list_all_players(session: Session) -> list[Player]:
    """Return the entire player pool, ordered by name."""
    return list(session.scalars(select(Player).order_by(Player.name)))


def list_players_by_position(session: Session, position: str) -> list[Player]:
    """Return all players at the given position (C / 1B / OF / P)."""
    return list(
        session.scalars(select(Player).where(Player.position == position).order_by(Player.name))
    )
