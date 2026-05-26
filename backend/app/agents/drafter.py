"""Drafter agent: chooses one candidate from the Researcher's list."""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

from app.agents.models import Candidate, DraftPick

MAX_TURNS = 4
MODEL = "gpt-4o-mini"

INSTRUCTIONS = """You are the Drafter for a fantasy baseball draft.

You are given:
- A ranked list of candidates from the Researcher (highest rank first)
- The team's current roster (already drafted players)
- The team's strategy

Choose exactly one candidate to draft. The pick must:
- Fill a position not already on the roster.
- Use a player_id from the supplied candidate list (do not invent ids).
- Have a 2-3 sentence rationale that names the strategy and cites at least
  one concrete stat from the candidate.

Return a DraftPick.
"""


def _build_input(
    candidates: list[Candidate],
    current_roster: list[dict[str, Any]],
    strategy_name: str,
) -> str:
    return (
        f"Strategy: {strategy_name}\n\n"
        f"Candidates from the Researcher (ranked):\n"
        f"{json.dumps([c.model_dump() for c in candidates])}\n\n"
        f"Current roster ({len(current_roster)} picks):\n"
        f"{json.dumps(current_roster)}\n"
    )


def _build_agent() -> Agent:
    return Agent(
        name="Drafter",
        instructions=INSTRUCTIONS,
        tools=[],
        model=MODEL,
        output_type=DraftPick,
    )


async def run_drafter(
    candidates: list[Candidate],
    current_roster: list[dict[str, Any]],
    strategy_name: str,
) -> DraftPick:
    """Call the Drafter and return its chosen pick."""
    agent = _build_agent()
    user_input = _build_input(candidates, current_roster, strategy_name)
    result = await Runner.run(agent, input=user_input, max_turns=MAX_TURNS)
    return result.final_output
