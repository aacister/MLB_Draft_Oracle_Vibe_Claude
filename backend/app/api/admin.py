"""Dev-only admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.ingest import ingest_season

router = APIRouter(tags=["admin"], prefix="/admin")


@router.post("/ingest")
def trigger_ingest(
    season: int = Query(default=2025),
    limit: int = Query(default=75),
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    """Re-ingest the player pool for a season. Idempotent via the upsert."""
    count = ingest_season(session, season=season, limit=limit)
    return {"status": "ok", "season": season, "ingested": count}
