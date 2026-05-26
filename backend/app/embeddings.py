"""Local sentence-transformers embedding and the canonical text recipes.

The model is cached at module level via ``functools.cache`` so the ~90 MB
load happens at most once per process. ``embed`` returns L2-normalized
384-dim vectors so cosine similarity reduces to a dot product.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Canonical, stable order of stat keys used in pick embedding text. Must not
# change without re-embedding every persisted pick vector.
PICK_STAT_KEYS: tuple[str, ...] = (
    "HR", "RBI", "R", "SB", "AVG", "OBP", "SLG", "K", "W", "S", "ERA", "WHIP",
)


@cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    """Return a 384-dim L2-normalized embedding for the given text."""
    vector = _get_model().encode(text, normalize_embeddings=True)
    return vector.tolist()


def pick_text(
    player_name: str,
    position: str,
    strategy_name: str,
    rationale: str,
    stats: dict[str, Any],
) -> str:
    """Canonical embedding text for a pick. Order of stats is fixed by PICK_STAT_KEYS."""
    stat_str = " ".join(f"{k}:{stats.get(k, 0)}" for k in PICK_STAT_KEYS)
    return f"{player_name} | {position} | {strategy_name} | {rationale} | {stat_str}"


def adp_text(player_name: str, position: str, pick_number: int, season: int) -> str:
    """Canonical embedding text for an ADP datapoint."""
    return f"{player_name} | {position} | pick:{pick_number} | season:{season}"
