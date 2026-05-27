"""Tests for the witty name generator."""

from __future__ import annotations

import random

from app.names import DEFAULT_TEAM_NAMES, generate_draft_name, generate_team_name


class TestDraftName:
    def test_returns_non_empty_string(self) -> None:
        name = generate_draft_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_deterministic_with_seeded_rng(self) -> None:
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        assert generate_draft_name(rng=rng_a) == generate_draft_name(rng=rng_b)

    def test_includes_year_when_template_uses_it(self) -> None:
        """At least some of the 5 templates include {year}; force enough samples to hit one."""
        rng = random.Random(0)
        names = [generate_draft_name(rng=rng, year=2030) for _ in range(40)]
        # With 40 draws across 5 templates, statistically at least one uses the year template
        assert any("2030" in n for n in names)


class TestTeamName:
    def test_returns_one_of_strategy_pool(self) -> None:
        name = generate_team_name("Power Hitting")
        assert name in DEFAULT_TEAM_NAMES["Power Hitting"]

    def test_unknown_strategy_returns_fallback(self) -> None:
        name = generate_team_name("Nonexistent Strategy")
        assert name == "The Roster"

    def test_all_strategies_have_pools(self) -> None:
        expected = {
            "Power Hitting",
            "Speed & Defense",
            "Balanced",
            "Ace Pitching",
            "Closer-Heavy",
            "Contrarian Value",
        }
        assert expected.issubset(DEFAULT_TEAM_NAMES.keys())
        for pool in DEFAULT_TEAM_NAMES.values():
            assert len(pool) >= 1
