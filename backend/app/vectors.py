"""File-based vector store with NumPy cosine search.

One JSON file per embedded pick under ``./memory/vectors/picks/<id>.json`` and
one per ADP datapoint under ``./memory/vectors/adp/<id>.json``. Loads are cached
keyed on file mtime so repeated grade lookups don't re-read disk.
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from app.embeddings import adp_text, embed, pick_text
from app.paths import VECTORS_ADP_DIR, VECTORS_PICKS_DIR

COHORT_MIN_SAMPLES = 5

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _read_with_cache(path: Path) -> dict[str, Any]:
    mtime = path.stat().st_mtime
    key = path.as_posix()
    cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    data = json.loads(path.read_text())
    _cache[key] = (mtime, data)
    return data


def _clear_cache() -> None:
    """Drop the in-process mtime cache. Test-only helper."""
    _cache.clear()


def _load_dir(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [_read_with_cache(f) for f in sorted(directory.glob("*.json"))]


def write_pick_vector(
    draft_id: str,
    team_id: str,
    strategy: str,
    round_: int,
    pick_number: int,
    player_id: int,
    player_name: str,
    position: str,
    rationale: str,
    stats_snapshot: dict[str, Any],
    *,
    vid: str | None = None,
) -> dict[str, Any]:
    """Embed the pick text and write a pick vector to disk. Returns the full record."""
    text = pick_text(player_name, position, strategy, rationale, stats_snapshot)
    record = {
        "id": vid or str(uuid.uuid4()),
        "kind": "pick",
        "draft_id": draft_id,
        "team_id": team_id,
        "strategy": strategy,
        "round": round_,
        "pick_number": pick_number,
        "player_id": player_id,
        "player_name": player_name,
        "position": position,
        "rationale": rationale,
        "stats_snapshot": stats_snapshot,
        "embedding": embed(text),
        "indexed_at": _utcnow_iso(),
    }
    VECTORS_PICKS_DIR.mkdir(parents=True, exist_ok=True)
    (VECTORS_PICKS_DIR / f"{record['id']}.json").write_text(json.dumps(record))
    return record


def write_adp_vector(
    draft_id: str,
    player_id: int,
    player_name: str,
    position: str,
    pick_number: int,
    season: int,
    *,
    vid: str | None = None,
) -> dict[str, Any]:
    """Embed the ADP text and write an ADP vector to disk. Returns the full record."""
    text = adp_text(player_name, position, pick_number, season)
    record = {
        "id": vid or str(uuid.uuid4()),
        "kind": "adp",
        "draft_id": draft_id,
        "player_id": player_id,
        "player_name": player_name,
        "position": position,
        "pick_number": pick_number,
        "season": season,
        "embedding": embed(text),
        "indexed_at": _utcnow_iso(),
    }
    VECTORS_ADP_DIR.mkdir(parents=True, exist_ok=True)
    (VECTORS_ADP_DIR / f"{record['id']}.json").write_text(json.dumps(record))
    return record


def load_pick_vectors() -> list[dict[str, Any]]:
    """Return every pick vector on disk (sorted by filename, mtime-cached)."""
    return _load_dir(VECTORS_PICKS_DIR)


def load_adp_vectors() -> list[dict[str, Any]]:
    """Return every ADP vector on disk (sorted by filename, mtime-cached)."""
    return _load_dir(VECTORS_ADP_DIR)


def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns 0.0 if either has zero norm."""
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def find_cohort_centroid(
    strategy: str, vectors: list[dict[str, Any]]
) -> list[float] | None:
    """Mean embedding of pick vectors matching the strategy.

    Cold-start fallback: if fewer than COHORT_MIN_SAMPLES match, use the mean of
    all supplied vectors instead. Returns ``None`` only when no vectors exist at all.
    """
    cohort = [v["embedding"] for v in vectors if v.get("strategy") == strategy]
    if len(cohort) < COHORT_MIN_SAMPLES:
        cohort = [v["embedding"] for v in vectors]
    if not cohort:
        return None
    return np.mean(np.asarray(cohort, dtype=float), axis=0).tolist()
