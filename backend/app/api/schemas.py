"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateDraftRequest(BaseModel):
    """``POST /v1/drafts`` request body. Strategies are optional (random if omitted)."""

    strategy_a: str | None = None
    strategy_b: str | None = None
    num_rounds: int = Field(default=4, ge=1, le=20)


class TeamSummary(BaseModel):
    id: str
    name: str
    strategy: str


class DraftSummary(BaseModel):
    """Compact draft view used in list responses and ``POST /v1/drafts`` reply."""

    id: str
    name: str
    status: str
    created_at: datetime.datetime
    config: dict[str, Any]
    teams: list[TeamSummary]


class PlayerOut(BaseModel):
    id: int
    name: str
    mlb_team: str
    position: str
    stats: dict[str, Any]


class GradeOut(BaseModel):
    team_id: str
    team_name: str
    strategy: str
    alignment_score: int
    letter: Literal["A", "B", "C", "D", "F"]
    rationale: str


class RunResponse(BaseModel):
    status: str
    draft_id: str
