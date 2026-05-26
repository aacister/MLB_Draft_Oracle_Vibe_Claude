"""Grader agent: narrates a letter + rationale given the deterministic alignment_score.

The Grader never re-computes the score — it only converts the numeric score into
a letter and supplies prose explanation referencing specific picks.
"""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

from app.agents.models import GradeResult

MAX_TURNS = 3
MODEL = "gpt-4o-mini"

INSTRUCTIONS = """You are the Grader for a completed fantasy baseball draft team.

You are given:
- The team's name and strategy
- All of the team's picks (with stats)
- A deterministic alignment_score from 0 to 100 (pre-computed; do NOT re-compute)

Produce:
- A letter grade based ONLY on the alignment_score:
  90-100 -> "A"
  75-89  -> "B"
  55-74  -> "C"
  35-54  -> "D"
  0-34   -> "F"
- A 2-3 sentence rationale that references the alignment_score and names
  one or two specific picks (best fit, biggest miss).

Return a GradeResult.
"""


def _build_input(
    team_name: str,
    strategy_name: str,
    picks: list[dict[str, Any]],
    alignment_score: int,
) -> str:
    return (
        f"Team: {team_name}\n"
        f"Strategy: {strategy_name}\n"
        f"Alignment score: {alignment_score}\n\n"
        f"Picks:\n{json.dumps(picks)}\n"
    )


def _build_agent() -> Agent:
    return Agent(
        name="Grader",
        instructions=INSTRUCTIONS,
        tools=[],
        model=MODEL,
        output_type=GradeResult,
    )


async def run_grader(
    team_name: str,
    strategy_name: str,
    picks: list[dict[str, Any]],
    alignment_score: int,
) -> GradeResult:
    """Call the Grader and return the letter + rationale."""
    agent = _build_agent()
    user_input = _build_input(team_name, strategy_name, picks, alignment_score)
    result = await Runner.run(agent, input=user_input, max_turns=MAX_TURNS)
    return result.final_output
