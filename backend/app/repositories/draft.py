"""Repository functions for the Draft table."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Draft


def create_draft(session: Session, name: str, config: dict[str, Any] | None = None) -> Draft:
    """Insert a new draft and return it."""
    draft = Draft(name=name, config=config or {})
    session.add(draft)
    session.flush()
    return draft


def get_draft(session: Session, draft_id: str) -> Draft | None:
    """Return the draft with the given id, or None."""
    return session.get(Draft, draft_id)


def list_drafts(session: Session) -> list[Draft]:
    """Return all drafts, newest first."""
    return list(session.scalars(select(Draft).order_by(Draft.created_at.desc())))


def update_status(session: Session, draft_id: str, status: str) -> Draft | None:
    """Update a draft's status; return the updated draft or None if not found."""
    draft = session.get(Draft, draft_id)
    if draft is None:
        return None
    draft.status = status
    session.flush()
    return draft
