"""Tests for the vector store (file I/O, mtime cache, cosine search, centroid)."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import pytest

from app import vectors as vectors_module
from app.vectors import (
    COHORT_MIN_SAMPLES,
    _clear_cache,
    _read_with_cache,
    cosine_similarity,
    find_cohort_centroid,
    load_adp_vectors,
    load_pick_vectors,
    write_adp_vector,
    write_pick_vector,
)


@pytest.fixture
def isolated_vectors_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point VECTORS_PICKS_DIR / VECTORS_ADP_DIR at a tmp_path; clear the mtime cache."""
    picks = tmp_path / "picks"
    adp = tmp_path / "adp"
    monkeypatch.setattr(vectors_module, "VECTORS_PICKS_DIR", picks)
    monkeypatch.setattr(vectors_module, "VECTORS_ADP_DIR", adp)
    _clear_cache()
    return tmp_path


def _synthetic_embedding(seed: float, dim: int = 384) -> list[float]:
    """Build a deterministic 384-dim vector for testing cosine math.

    Uses sin(i + seed) so different seeds give different but reproducible vectors.
    Not normalized; cosine_similarity normalizes internally.
    """
    return [math.sin(i + seed) for i in range(dim)]


class TestCosineSimilarity:
    def test_identical_vectors_is_one(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_opposite_vectors_is_negative_one(self) -> None:
        v = [1.0, 2.0, 3.0]
        opposite = [-x for x in v]
        assert cosine_similarity(v, opposite) == pytest.approx(-1.0)

    def test_orthogonal_vectors_is_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_norm_returns_zero(self) -> None:
        assert cosine_similarity([0.0, 0.0, 0.0], [1.0, 2.0, 3.0]) == 0.0
        assert cosine_similarity([1.0, 2.0, 3.0], [0.0, 0.0, 0.0]) == 0.0

    def test_scale_invariant(self) -> None:
        v = [1.0, 2.0, 3.0]
        scaled = [10.0 * x for x in v]
        assert cosine_similarity(v, scaled) == pytest.approx(1.0)


class TestFindCohortCentroid:
    def test_returns_none_for_empty(self) -> None:
        assert find_cohort_centroid("Power Hitting", []) is None

    def test_returns_mean_when_enough_matches(self) -> None:
        vectors = [
            {"strategy": "Power Hitting", "embedding": [1.0, 0.0, 0.0]},
            {"strategy": "Power Hitting", "embedding": [0.0, 1.0, 0.0]},
            {"strategy": "Power Hitting", "embedding": [0.0, 0.0, 1.0]},
            {"strategy": "Power Hitting", "embedding": [1.0, 1.0, 0.0]},
            {"strategy": "Power Hitting", "embedding": [1.0, 1.0, 1.0]},
            {"strategy": "Speed & Defense", "embedding": [9.0, 9.0, 9.0]},
        ]
        centroid = find_cohort_centroid("Power Hitting", vectors)
        assert centroid is not None
        # Mean of the five Power Hitting embeddings only
        assert centroid[0] == pytest.approx(0.6)
        assert centroid[1] == pytest.approx(0.6)
        assert centroid[2] == pytest.approx(0.4)

    def test_cold_start_fallback(self) -> None:
        """With fewer than COHORT_MIN_SAMPLES matching, fall back to centroid of all vectors."""
        vectors = [
            {"strategy": "Power Hitting", "embedding": [1.0, 0.0]},  # only 1 match
            {"strategy": "Other", "embedding": [3.0, 0.0]},
            {"strategy": "Other", "embedding": [5.0, 0.0]},
        ]
        centroid = find_cohort_centroid("Power Hitting", vectors)
        assert centroid is not None
        assert centroid[0] == pytest.approx((1.0 + 3.0 + 5.0) / 3)
        assert centroid[1] == pytest.approx(0.0)

    def test_cohort_min_samples_value(self) -> None:
        """Sanity: COHORT_MIN_SAMPLES is the documented value of 5."""
        assert COHORT_MIN_SAMPLES == 5


class TestWritePickVector:
    def test_writes_file_with_required_fields(self, isolated_vectors_dirs: Path) -> None:
        record = write_pick_vector(
            draft_id="d1",
            team_id="t1",
            strategy="Power Hitting",
            round_=1,
            pick_number=1,
            player_id=12345,
            player_name="Aaron Judge",
            position="OF",
            rationale="Top slugger.",
            stats_snapshot={"HR": 58, "RBI": 144},
        )

        assert record["kind"] == "pick"
        assert record["draft_id"] == "d1"
        assert record["team_id"] == "t1"
        assert record["strategy"] == "Power Hitting"
        assert record["round"] == 1
        assert record["pick_number"] == 1
        assert record["player_id"] == 12345
        assert record["player_name"] == "Aaron Judge"
        assert record["position"] == "OF"
        assert record["rationale"] == "Top slugger."
        assert record["stats_snapshot"] == {"HR": 58, "RBI": 144}
        assert len(record["embedding"]) == 384
        assert "indexed_at" in record
        assert len(record["id"]) == 36

        on_disk = vectors_module.VECTORS_PICKS_DIR / f"{record['id']}.json"
        assert on_disk.exists()

    def test_round_trip_through_load(self, isolated_vectors_dirs: Path) -> None:
        write_pick_vector(
            "d1", "t1", "Power Hitting", 1, 1, 1, "X", "OF", "r", {"HR": 30}
        )
        loaded = load_pick_vectors()
        assert len(loaded) == 1
        assert loaded[0]["player_name"] == "X"


class TestWriteAdpVector:
    def test_writes_file_with_required_fields(self, isolated_vectors_dirs: Path) -> None:
        record = write_adp_vector(
            draft_id="d1",
            player_id=12345,
            player_name="Aaron Judge",
            position="OF",
            pick_number=3,
            season=2025,
        )

        assert record["kind"] == "adp"
        assert record["draft_id"] == "d1"
        assert record["player_id"] == 12345
        assert record["pick_number"] == 3
        assert record["season"] == 2025
        assert len(record["embedding"]) == 384

        on_disk = vectors_module.VECTORS_ADP_DIR / f"{record['id']}.json"
        assert on_disk.exists()

    def test_round_trip_through_load(self, isolated_vectors_dirs: Path) -> None:
        write_adp_vector("d1", 12345, "X", "OF", 3, 2025)
        loaded = load_adp_vectors()
        assert len(loaded) == 1
        assert loaded[0]["player_name"] == "X"


class TestLoadVectorsEmptyDir:
    def test_empty_dir_returns_empty_list(self, isolated_vectors_dirs: Path) -> None:
        assert load_pick_vectors() == []
        assert load_adp_vectors() == []


class TestMtimeCache:
    def test_unchanged_mtime_returns_cached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_cache()
        path = tmp_path / "v.json"
        path.write_text('{"x": 1}')

        first = _read_with_cache(path)
        # Mutate the file's bytes WITHOUT touching mtime (write back the original mtime)
        original_mtime = path.stat().st_mtime
        path.write_text('{"x": 999}')
        import os
        os.utime(path, (original_mtime, original_mtime))

        second = _read_with_cache(path)
        # Cache hit: same dict identity returned
        assert second is first

    def test_changed_mtime_re_reads(self, tmp_path: Path) -> None:
        _clear_cache()
        path = tmp_path / "v.json"
        path.write_text('{"x": 1}')
        first = _read_with_cache(path)
        assert first == {"x": 1}

        # Wait long enough for mtime resolution on Windows (~16ms)
        time.sleep(0.05)
        path.write_text('{"x": 2}')

        second = _read_with_cache(path)
        assert second == {"x": 2}
