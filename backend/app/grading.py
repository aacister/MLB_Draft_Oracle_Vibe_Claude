"""Deterministic 0-100 alignment scoring.

Two halves, weighted equally:

* ``tag_fit``    — fraction of a team's picks that clear at least one strategy tag.
* ``cohort_fit`` — mean cosine similarity of the team's pick embeddings to the
                   centroid of all matching-strategy picks from *other* drafts,
                   mapped from cosine's [-1, 1] range to [0, 1].

The Grader agent layers a narrated letter grade on top — it never re-computes
this score.
"""

from __future__ import annotations

from typing import Any

from app.strategies import get_strategy
from app.vectors import cosine_similarity, find_cohort_centroid, load_pick_vectors

COHORT_WEIGHT = 0.5
TAG_WEIGHT = 0.5


def tag_fit(picks: list[dict[str, Any]], strategy_name: str) -> float:
    """Fraction of picks whose ``stats_snapshot`` clears at least one of the strategy's tags."""
    if not picks:
        return 0.0
    strategy = get_strategy(strategy_name)
    hits = sum(
        1 for p in picks if strategy.stat_clears_any_tag(p.get("stats_snapshot", {}))
    )
    return hits / len(picks)


def cohort_fit(
    team_embeddings: list[list[float]],
    strategy_name: str,
    *,
    current_draft_id: str | None = None,
    all_vectors: list[dict[str, Any]] | None = None,
) -> float:
    """Mean cosine similarity of team picks to the strategy cohort centroid, in [0, 1].

    Vectors from ``current_draft_id`` are excluded so a team is never compared
    against its own picks. Returns 0.0 if no centroid can be computed.
    """
    if not team_embeddings:
        return 0.0
    if all_vectors is None:
        all_vectors = load_pick_vectors()
    other_vectors = [
        v for v in all_vectors if v.get("draft_id") != current_draft_id
    ] if current_draft_id is not None else list(all_vectors)
    centroid = find_cohort_centroid(strategy_name, other_vectors)
    if centroid is None:
        return 0.0
    sims = [cosine_similarity(e, centroid) for e in team_embeddings]
    mean_sim = sum(sims) / len(sims)
    return (mean_sim + 1.0) / 2.0


def alignment_score(
    picks: list[dict[str, Any]],
    team_embeddings: list[list[float]],
    strategy_name: str,
    *,
    current_draft_id: str | None = None,
    all_vectors: list[dict[str, Any]] | None = None,
) -> int:
    """Deterministic 0-100 alignment score for a team in a draft.

    ``picks`` carry ``stats_snapshot`` for the tag check.
    ``team_embeddings`` are the embeddings of those same picks for cosine search.
    """
    t = tag_fit(picks, strategy_name)
    c = cohort_fit(
        team_embeddings,
        strategy_name,
        current_draft_id=current_draft_id,
        all_vectors=all_vectors,
    )
    return round(100 * (TAG_WEIGHT * t + COHORT_WEIGHT * c))
