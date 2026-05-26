"""OpenAI Agents SDK function tools available to the Researcher."""

from __future__ import annotations

from agents import function_tool

from app.search import web_search as _web_search


@function_tool
def web_search(query: str) -> list[dict]:
    """Search DuckDuckGo for recent news or analysis about a player or stat.

    Args:
        query: The search query. Be specific: "Aaron Judge 2025 home runs" not "Judge".

    Returns:
        A list of up to 5 results, each a dict with ``title``, ``href``, ``body``.
    """
    return _web_search(query, max_results=5)
