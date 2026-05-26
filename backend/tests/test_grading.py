"""Tests for the grading algorithm (tag_fit, cohort_fit, alignment_score).

Uses synthetic 384-d embeddings — no real model load. The grading math is
fully unit-testable without sentence-transformers.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.grading import (
    COHORT_WEIGHT,
    TAG_WEIGHT,
    alignment_score,
    cohort_fit,
    tag_fit,
)


def _pick(stats: dict[str, Any]) -> dict[str, Any]:
    return {"stats_snapshot": stats}


def _vec(*values: float) -> list[float]:
    """Pad/extend a short test vector to be reasonably-length for cosine work."""
    return list(values)


def _vector(strategy: str, embedding: list[float], draft_id: str = "other") -> dict[str, Any]:
    return {"strategy": strategy, "embedding": embedding, "draft_id": draft_id}


class TestTagFit:
    def test_empty_picks_returns_zero(self) -> None:
        assert tag_fit([], "Power Hitting") == 0.0

    def test_all_hits_returns_one(self) -> None:
        picks = [_pick({"HR": 30}), _pick({"HR": 40}), _pick({"SLG": 0.550})]
        assert tag_fit(picks, "Power Hitting") == 1.0

    def test_no_hits_returns_zero(self) -> None:
        picks = [_pick({"HR": 5}), _pick({"HR": 10, "RBI": 30})]
        assert tag_fit(picks, "Power Hitting") == 0.0

    def test_half_hits_returns_half(self) -> None:
        picks = [_pick({"HR": 30}), _pick({"HR": 5}), _pick({"HR": 30}), _pick({"HR": 5})]
        assert tag_fit(picks, "Power Hitting") == 0.5

    def test_missing_stats_blob_is_not_a_hit(self) -> None:
        picks = [{"stats_snapshot": {"HR": 30}}, {}]  # second pick has no stats_snapshot
        assert tag_fit(picks, "Power Hitting") == 0.5


class TestCohortFit:
    def test_empty_team_returns_zero(self) -> None:
        assert cohort_fit([], "Power Hitting", all_vectors=[]) == 0.0

    def test_no_vectors_returns_zero(self) -> None:
        team_emb = [_vec(1.0, 0.0)]
        assert cohort_fit(team_emb, "Power Hitting", all_vectors=[]) == 0.0

    def test_perfect_match_returns_one(self) -> None:
        """If team picks point in the same direction as the centroid → cosine 1 → fit 1."""
        # Build 5 cohort vectors all = [1.0, 0.0] → centroid = [1.0, 0.0]
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        team_emb = [_vec(1.0, 0.0), _vec(1.0, 0.0)]
        assert cohort_fit(team_emb, "Power Hitting", all_vectors=cohort) == pytest.approx(1.0)

    def test_opposite_direction_returns_zero(self) -> None:
        """Team vectors opposite the centroid → cosine -1 → fit 0."""
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        team_emb = [_vec(-1.0, 0.0)]
        assert cohort_fit(team_emb, "Power Hitting", all_vectors=cohort) == pytest.approx(0.0)

    def test_orthogonal_returns_half(self) -> None:
        """Cosine 0 → fit 0.5."""
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        team_emb = [_vec(0.0, 1.0)]
        assert cohort_fit(team_emb, "Power Hitting", all_vectors=cohort) == pytest.approx(0.5)

    def test_excludes_current_draft(self) -> None:
        """Vectors belonging to current_draft_id must not influence the centroid."""
        # If the only Power Hitting vectors are from the current draft, after filtering
        # we have nothing; cohort_fit must fall back to the empty case.
        current = "draft-X"
        cohort = [
            _vector("Power Hitting", [1.0, 0.0], draft_id=current) for _ in range(3)
        ]
        team_emb = [_vec(1.0, 0.0)]
        # With current_draft_id supplied → these are excluded → no centroid → 0.0
        assert (
            cohort_fit(
                team_emb,
                "Power Hitting",
                current_draft_id=current,
                all_vectors=cohort,
            )
            == 0.0
        )

    def test_uses_cold_start_centroid(self) -> None:
        """If <5 vectors match the strategy, centroid is computed over all vectors."""
        cohort = [
            _vector("Power Hitting", [1.0, 0.0]),  # 1 match
            _vector("Other", [1.0, 0.0]),
            _vector("Other", [1.0, 0.0]),
            _vector("Other", [1.0, 0.0]),
        ]
        team_emb = [_vec(1.0, 0.0)]
        # Cold-start: centroid = mean of all = [1.0, 0.0]; cosine with team [1,0] = 1
        assert cohort_fit(team_emb, "Power Hitting", all_vectors=cohort) == pytest.approx(1.0)


class TestAlignmentScore:
    def test_returns_int(self) -> None:
        result = alignment_score([], [], "Power Hitting", all_vectors=[])
        assert isinstance(result, int)
        assert result == 0

    def test_perfect_score(self) -> None:
        """All picks hit tags AND embeddings perfectly match centroid → 100."""
        picks = [_pick({"HR": 30}), _pick({"HR": 35})]
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        team_emb = [_vec(1.0, 0.0), _vec(1.0, 0.0)]
        assert (
            alignment_score(picks, team_emb, "Power Hitting", all_vectors=cohort)
            == 100
        )

    def test_zero_when_no_hits_and_no_cohort_match(self) -> None:
        picks = [_pick({"HR": 5})]
        team_emb = [_vec(-1.0, 0.0)]
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        # tag_fit = 0; cohort_fit = 0 (opposite vectors); score = 0
        assert alignment_score(picks, team_emb, "Power Hitting", all_vectors=cohort) == 0

    def test_weighted_formula(self) -> None:
        """alignment_score = round(100 * (0.5 * cohort_fit + 0.5 * tag_fit))."""
        # All picks hit (tag_fit = 1), embeddings orthogonal to centroid (cohort_fit = 0.5)
        picks = [_pick({"HR": 30}), _pick({"HR": 30})]
        cohort = [_vector("Power Hitting", [1.0, 0.0]) for _ in range(5)]
        team_emb = [_vec(0.0, 1.0), _vec(0.0, 1.0)]
        # expected = round(100 * (0.5 * 0.5 + 0.5 * 1.0)) = round(75) = 75
        assert alignment_score(picks, team_emb, "Power Hitting", all_vectors=cohort) == 75

    def test_weights_sum_to_one(self) -> None:
        assert COHORT_WEIGHT + TAG_WEIGHT == pytest.approx(1.0)
