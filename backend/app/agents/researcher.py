"""Researcher agent: given strategy + roster needs + available pool, returns 3-5 ranked candidates."""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

from app.agents.models import ResearchResult
from app.agents.tools import web_search

MAX_TURNS = 6
MODEL = "gpt-4o-mini"

INSTRUCTIONS = """You are the Researcher for a fantasy baseball draft.

Given the team's strategy, the positions still unfilled on the roster, and the
list of available players with their season stats, recommend 3-5 candidates
ranked by best fit for the strategy.

Rules:
- Only recommend players from the supplied available pool (use their exact player_id).
- Respect roster needs: do not recommend a position that is already filled.
- Cite evidence — stat values from the input, and recent web results when relevant.
- Be concise. Each candidate rationale is 1-2 sentences citing concrete numbers.
- Rank 1 is the top pick; ranks must start at 1 and be sequential.

Return a ResearchResult with the candidate list ordered by rank ascending.
"""


def _build_input(
    strategy_name: str,
    roster_needs: list[str],
    available_players: list[dict[str, Any]],
    draft_history: list[dict[str, Any]],
) -> str:
    """Render the structured input passed to the agent."""
    return (
        f"Strategy: {strategy_name}\n"
        f"Roster positions still needed: {', '.join(roster_needs) or 'none'}\n\n"
        f"Available players ({len(available_players)} total — first 80 shown):\n"
        f"{json.dumps(available_players[:80])}\n\n"
        f"Draft history so far ({len(draft_history)} picks):\n"
        f"{json.dumps(draft_history)}\n"
    )


def _build_agent() -> Agent:
    return Agent(
        name="Researcher",
        instructions=INSTRUCTIONS,
        tools=[web_search],
        model=MODEL,
        output_type=ResearchResult,
    )


async def run_researcher(
    strategy_name: str,
    roster_needs: list[str],
    available_players: list[dict[str, Any]],
    draft_history: list[dict[str, Any]],
) -> ResearchResult:
    """Call the Researcher and return the structured candidate list."""
    agent = _build_agent()
    user_input = _build_input(strategy_name, roster_needs, available_players, draft_history)
    result = await Runner.run(agent, input=user_input, max_turns=MAX_TURNS)
    return result.final_output
