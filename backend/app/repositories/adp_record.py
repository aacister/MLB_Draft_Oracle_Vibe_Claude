"""Repository functions for the AdpRecord table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdpRecord


def create_adp_record(
    session: Session,
    draft_id: str,
    player_id: int,
    pick_number: int,
    season: int,
) -> AdpRecord:
    """Insert a new ADP record and return it."""
    record = AdpRecord(
        draft_id=draft_id,
        player_id=player_id,
        pick_number=pick_number,
        season=season,
    )
    session.add(record)
    session.flush()
    return record


def list_adp_records_for_player(session: Session, player_id: int) -> list[AdpRecord]:
    """Return every ADP record for a single player, oldest first."""
    return list(
        session.scalars(
            select(AdpRecord)
            .where(AdpRecord.player_id == player_id)
            .order_by(AdpRecord.created_at)
        )
    )
