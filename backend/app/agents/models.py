"""Pydantic Structured Output models for the three agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """One Researcher recommendation."""

    player_id: int
    player_name: str
    position: str
    rank: int = Field(ge=1, description="1 = top pick")
    rationale: str
    citations: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    """Output of the Researcher agent: 3-5 candidates ordered by rank."""

    candidates: list[Candidate]


class DraftPick(BaseModel):
    """Output of the Drafter agent: a chosen player + rationale."""

    player_id: int
    player_name: str
    position: str
    rationale: str


class GradeResult(BaseModel):
    """Output of the Grader agent: a letter and a 2-3 sentence narration."""

    letter: Literal["A", "B", "C", "D", "F"]
    rationale: str
