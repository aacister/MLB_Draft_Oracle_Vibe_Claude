"""Tests for strategy definitions and the tag-matching helper."""

from __future__ import annotations

import pytest

from app.strategies import STRATEGIES, Strategy, StrategyTag, get_strategy, list_strategies


class TestStrategyTag:
    @pytest.mark.parametrize(
        ("op", "threshold", "value", "expected"),
        [
            (">=", 25, 30, True),
            (">=", 25, 25, True),
            (">=", 25, 24, False),
            ("<=", 3.50, 3.20, True),
            ("<=", 3.50, 3.50, True),
            ("<=", 3.50, 3.60, False),
        ],
    )
    def test_comparison_ops(self, op: str, threshold: float, value: float, expected: bool) -> None:
        tag = StrategyTag("HR", op, threshold)
        assert tag.matches({"HR": value}) is expected

    def test_missing_stat_returns_false(self) -> None:
        tag = StrategyTag("HR", ">=", 25)
        assert tag.matches({}) is False
        assert tag.matches({"RBI": 100}) is False

    def test_none_value_returns_false(self) -> None:
        tag = StrategyTag("HR", ">=", 25)
        assert tag.matches({"HR": None}) is False

    def test_non_numeric_value_returns_false(self) -> None:
        tag = StrategyTag("HR", ">=", 25)
        assert tag.matches({"HR": "n/a"}) is False

    def test_string_numeric_value_is_coerced(self) -> None:
        tag = StrategyTag("HR", ">=", 25)
        assert tag.matches({"HR": "30"}) is True

    def test_unknown_op_returns_false(self) -> None:
        tag = StrategyTag("HR", "!=", 25)
        assert tag.matches({"HR": 30}) is False


class TestStrategy:
    def test_stat_clears_any_tag_when_multiple_tags(self) -> None:
        strategy = Strategy(
            name="X",
            description="",
            tags=(StrategyTag("HR", ">=", 25), StrategyTag("RBI", ">=", 80)),
        )
        # Matches first tag only
        assert strategy.stat_clears_any_tag({"HR": 30, "RBI": 50}) is True
        # Matches second tag only
        assert strategy.stat_clears_any_tag({"HR": 10, "RBI": 100}) is True
        # No matches
        assert strategy.stat_clears_any_tag({"HR": 10, "RBI": 50}) is False

    def test_stat_clears_no_tags_strategy_returns_false(self) -> None:
        strategy = Strategy(name="X", description="", tags=())
        assert strategy.stat_clears_any_tag({"HR": 100}) is False


class TestStrategiesRegistry:
    def test_all_six_strategies_present(self) -> None:
        expected = {
            "Power Hitting",
            "Speed & Defense",
            "Balanced",
            "Ace Pitching",
            "Closer-Heavy",
            "Contrarian Value",
        }
        assert set(STRATEGIES.keys()) == expected
        assert len(list_strategies()) == 6

    def test_get_strategy_returns_named(self) -> None:
        s = get_strategy("Power Hitting")
        assert s.name == "Power Hitting"
        assert len(s.tags) == 3

    def test_get_strategy_unknown_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            get_strategy("Nonexistent")


class TestStrategyThresholds:
    """Verify each strategy's tag thresholds with concrete representative stats."""

    @pytest.mark.parametrize(
        ("strategy", "stats", "expected"),
        [
            # Power Hitting
            ("Power Hitting", {"HR": 30}, True),
            ("Power Hitting", {"SLG": 0.520}, True),
            ("Power Hitting", {"RBI": 85}, True),
            ("Power Hitting", {"HR": 10, "RBI": 50, "SLG": 0.400}, False),
            # Speed & Defense
            ("Speed & Defense", {"SB": 25}, True),
            ("Speed & Defense", {"R": 85}, True),
            ("Speed & Defense", {"AVG": 0.280}, True),
            ("Speed & Defense", {"SB": 5, "R": 50, "AVG": 0.250}, False),
            # Balanced
            ("Balanced", {"AVG": 0.280}, True),
            ("Balanced", {"OBP": 0.350}, True),
            ("Balanced", {"AVG": 0.260, "OBP": 0.330}, False),
            # Ace Pitching
            ("Ace Pitching", {"K": 200}, True),
            ("Ace Pitching", {"ERA": 3.10}, True),
            ("Ace Pitching", {"WHIP": 1.10}, True),
            ("Ace Pitching", {"K": 100, "ERA": 4.50, "WHIP": 1.40}, False),
            # Closer-Heavy
            ("Closer-Heavy", {"S": 25}, True),
            ("Closer-Heavy", {"ERA": 2.80}, True),
            ("Closer-Heavy", {"S": 10, "ERA": 3.50}, False),
            # Contrarian Value
            ("Contrarian Value", {"OBP": 0.360}, True),
            ("Contrarian Value", {"OBP": 0.330}, False),
        ],
    )
    def test_clears_tags(self, strategy: str, stats: dict, expected: bool) -> None:
        assert get_strategy(strategy).stat_clears_any_tag(stats) is expected
