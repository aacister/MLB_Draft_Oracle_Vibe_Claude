"""Tests for the three agent runner functions.

``agents.Runner.run`` is mocked everywhere so no real OpenAI calls happen.
We verify each agent function builds its input correctly and unwraps the
``final_output`` from the result.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.drafter import MAX_TURNS as DRAFTER_MAX
from app.agents.drafter import run_drafter
from app.agents.grader import MAX_TURNS as GRADER_MAX
from app.agents.grader import run_grader
from app.agents.models import (
    Candidate,
    DraftPick,
    GradeResult,
    ResearchResult,
)
from app.agents.researcher import MAX_TURNS as RESEARCHER_MAX
from app.agents.researcher import run_researcher


def _runner_result(output) -> SimpleNamespace:
    return SimpleNamespace(final_output=output)


@pytest.mark.asyncio
async def test_researcher_unwraps_final_output() -> None:
    payload = ResearchResult(
        candidates=[
            Candidate(
                player_id=1,
                player_name="X",
                position="OF",
                rank=1,
                rationale="r",
            )
        ]
    )
    with patch(
        "app.agents.researcher.Runner.run",
        new=AsyncMock(return_value=_runner_result(payload)),
    ) as mock_run:
        result = await run_researcher("Power Hitting", ["OF"], [], [])

    assert result is payload
    # max_turns passed through
    _, kwargs = mock_run.call_args
    assert kwargs["max_turns"] == RESEARCHER_MAX


@pytest.mark.asyncio
async def test_researcher_input_includes_strategy_and_needs() -> None:
    payload = ResearchResult(candidates=[])
    with patch(
        "app.agents.researcher.Runner.run",
        new=AsyncMock(return_value=_runner_result(payload)),
    ) as mock_run:
        await run_researcher(
            strategy_name="Power Hitting",
            roster_needs=["OF", "P"],
            available_players=[{"id": 1, "name": "X", "position": "OF", "stats": {}}],
            draft_history=[],
        )

    _, kwargs = mock_run.call_args
    user_input = kwargs["input"]
    assert "Power Hitting" in user_input
    assert "OF" in user_input
    assert "P" in user_input


@pytest.mark.asyncio
async def test_drafter_unwraps_final_output() -> None:
    payload = DraftPick(player_id=1, player_name="X", position="OF", rationale="r")
    with patch(
        "app.agents.drafter.Runner.run",
        new=AsyncMock(return_value=_runner_result(payload)),
    ) as mock_run:
        result = await run_drafter(
            [Candidate(player_id=1, player_name="X", position="OF", rank=1, rationale="r")],
            [],
            "Power Hitting",
        )

    assert result is payload
    _, kwargs = mock_run.call_args
    assert kwargs["max_turns"] == DRAFTER_MAX


@pytest.mark.asyncio
async def test_grader_unwraps_final_output() -> None:
    payload = GradeResult(letter="B", rationale="solid build")
    with patch(
        "app.agents.grader.Runner.run",
        new=AsyncMock(return_value=_runner_result(payload)),
    ) as mock_run:
        result = await run_grader(
            team_name="T", strategy_name="Power Hitting", picks=[], alignment_score=80
        )

    assert result is payload
    _, kwargs = mock_run.call_args
    assert kwargs["max_turns"] == GRADER_MAX
    # input mentions the score
    assert "80" in kwargs["input"]
