"""Draft strategies, their descriptions, and the stat-threshold tags used for grading.

Each strategy declares one or more ``StrategyTag`` thresholds. A pick is a "hit"
for the strategy if its stats clear *any* one of the tags. The thresholds here
are the single source of truth: change them here, nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyTag:
    """One stat threshold check, e.g., ``HR >= 25`` or ``ERA <= 3.50``."""

    stat: str
    op: str  # ">=" or "<="
    threshold: float

    def matches(self, stats: dict[str, Any]) -> bool:
        """True iff the value at ``stats[self.stat]`` satisfies the comparison."""
        raw = stats.get(self.stat)
        if raw is None:
            return False
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return False
        if self.op == ">=":
            return value >= self.threshold
        if self.op == "<=":
            return value <= self.threshold
        return False


@dataclass(frozen=True)
class Strategy:
    """A named draft strategy with a description and its grading tag list."""

    name: str
    description: str
    tags: tuple[StrategyTag, ...]

    def stat_clears_any_tag(self, stats: dict[str, Any]) -> bool:
        """True iff the stats blob clears at least one of this strategy's tags."""
        return any(tag.matches(stats) for tag in self.tags)


STRATEGIES: dict[str, Strategy] = {
    "Power Hitting": Strategy(
        name="Power Hitting",
        description="Target sluggers who drive in runs; accept the strikeouts that come with the swing.",
        tags=(
            StrategyTag("HR", ">=", 25),
            StrategyTag("SLG", ">=", 0.500),
            StrategyTag("RBI", ">=", 80),
        ),
    ),
    "Speed & Defense": Strategy(
        name="Speed & Defense",
        description="Prioritize stolen bases, runs scored, and contact hitting over raw power.",
        tags=(
            StrategyTag("SB", ">=", 20),
            StrategyTag("R", ">=", 80),
            StrategyTag("AVG", ">=", 0.270),
        ),
    ),
    "Balanced": Strategy(
        name="Balanced",
        description="No single focus. Favor a high floor over raw ceiling: good average, on-base, and mixed contributions.",
        tags=(
            StrategyTag("AVG", ">=", 0.275),
            StrategyTag("OBP", ">=", 0.340),
        ),
    ),
    "Ace Pitching": Strategy(
        name="Ace Pitching",
        description="Build the rotation around dominant starting pitching: strikeouts, ERA, and WHIP.",
        tags=(
            StrategyTag("K", ">=", 150),
            StrategyTag("ERA", "<=", 3.50),
            StrategyTag("WHIP", "<=", 1.20),
        ),
    ),
    "Closer-Heavy": Strategy(
        name="Closer-Heavy",
        description="Specialize in relief: target saves and elite back-end ERAs.",
        tags=(
            StrategyTag("S", ">=", 20),
            StrategyTag("ERA", "<=", 3.00),
        ),
    ),
    "Contrarian Value": Strategy(
        name="Contrarian Value",
        description="High on-base contributors and undervalued players the field will pass on.",
        tags=(
            StrategyTag("OBP", ">=", 0.350),
        ),
    ),
}


def get_strategy(name: str) -> Strategy:
    """Look up a strategy by exact name."""
    return STRATEGIES[name]


def list_strategies() -> list[Strategy]:
    """All strategies, in insertion order."""
    return list(STRATEGIES.values())
