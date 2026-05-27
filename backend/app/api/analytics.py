"""Analytics endpoints: per-draft grades, historical leaderboard, ADP trends."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import (
    avg_score_by_strategy,
    ignored_positions,
    overdrafted_players,
    season_shift,
)
from app.api.deps import get_session
from app.api.schemas import GradeOut
from app.repositories import grade as grade_repo
from app.repositories import team as team_repo

router = APIRouter(tags=["analytics"])


@router.get("/drafts/{draft_id}/grade", response_model=list[GradeOut])
def get_grades(draft_id: str, session: Session = Depends(get_session)) -> list[GradeOut]:
    """Grades for both teams in a draft."""
    grades = grade_repo.list_grades_for_draft(session, draft_id)
    if not grades:
        raise HTTPException(404, f"no grades found for draft {draft_id}")
    out: list[GradeOut] = []
    for g in grades:
        team = team_repo.get_team(session, g.team_id)
        out.append(
            GradeOut(
                team_id=g.team_id,
                team_name=team.name if team else "Unknown",
                strategy=team.strategy_name if team else "Unknown",
                alignment_score=g.alignment_score,
                letter=g.letter,
                rationale=g.rationale,
            )
        )
    return out


@router.get("/leaderboard")
def leaderboard(
    strategy: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Historical mean alignment_score grouped by strategy."""
    return avg_score_by_strategy(session, strategy=strategy)


@router.get("/adp/trends")
def adp_trends(
    view: str = Query(default="overdrafted"),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """ADP analysis. ``view`` is one of: overdrafted, ignored_positions, season_shift."""
    if view == "overdrafted":
        return overdrafted_players(session)
    if view == "ignored_positions":
        return ignored_positions(session)
    if view == "season_shift":
        return season_shift(session)
    raise HTTPException(400, f"unknown view: {view}")
