"""Tests for the embedding model wrapper and text recipes.

The real sentence-transformers model is used here (loaded once via ``cache``).
Other test modules pass synthetic 384-dim vectors so the model load isn't repeated.
"""

from __future__ import annotations

import math

import pytest

from app.embeddings import EMBEDDING_DIM, PICK_STAT_KEYS, adp_text, embed, pick_text


class TestPickText:
    def test_contains_all_components(self) -> None:
        text = pick_text(
            "Aaron Judge", "OF", "Power Hitting", "Top slugger.", {"HR": 58, "RBI": 144}
        )
        assert "Aaron Judge" in text
        assert "OF" in text
        assert "Power Hitting" in text
        assert "Top slugger." in text
        assert "HR:58" in text
        assert "RBI:144" in text

    def test_uses_canonical_stat_order(self) -> None:
        """All PICK_STAT_KEYS appear in the recipe order regardless of dict order."""
        text = pick_text(
            "X", "OF", "P", "r",
            {"AVG": 0.300, "HR": 30, "RBI": 95},
        )
        # Search for " <stat>:" with a leading space so e.g. "R:" doesn't match inside "RBI:"
        positions = [text.index(f" {k}:") for k in PICK_STAT_KEYS]
        assert positions == sorted(positions)

    def test_missing_stats_default_to_zero(self) -> None:
        text = pick_text("X", "OF", "P", "r", {"HR": 10})
        assert "HR:10" in text
        assert "RBI:0" in text  # not present in stats dict


class TestAdpText:
    def test_exact_format(self) -> None:
        assert adp_text("Aaron Judge", "OF", 3, 2025) == "Aaron Judge | OF | pick:3 | season:2025"


class TestEmbed:
    def test_returns_384_dim(self) -> None:
        vec = embed("test")
        assert len(vec) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in vec)

    def test_l2_normalized(self) -> None:
        vec = embed("a normal sentence")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-4

    def test_deterministic(self) -> None:
        assert embed("same text") == embed("same text")

    def test_different_inputs_produce_different_embeddings(self) -> None:
        a = embed("apples")
        b = embed("orbital mechanics")
        assert a != b

    @pytest.mark.parametrize("text", ["", "a", "one two three"])
    def test_handles_short_strings(self, text: str) -> None:
        vec = embed(text)
        assert len(vec) == EMBEDDING_DIM
