"""Repository functions for the Grade table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Grade


def create_grade(
    session: Session,
    team_id: str,
    draft_id: str,
    alignment_score: int,
    letter: str,
    rationale: str,
) -> Grade:
    """Insert a new grade and return it."""
    grade = Grade(
        team_id=team_id,
        draft_id=draft_id,
        alignment_score=alignment_score,
        letter=letter,
        rationale=rationale,
    )
    session.add(grade)
    session.flush()
    return grade


def list_grades_for_draft(session: Session, draft_id: str) -> list[Grade]:
    """Return all grades in a draft (one per team)."""
    return list(session.scalars(select(Grade).where(Grade.draft_id == draft_id)))
