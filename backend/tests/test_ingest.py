"""Tests for the player-pool ingestion module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app import ingest as ingest_module
from app.ingest import (
    HITTING_CATEGORIES,
    PITCHING_CATEGORIES,
    _parse_value,
    fetch_leaders,
    ingest_season,
    map_position,
    merge_records,
)
from app.repositories.player import list_all_players


def _leader(pid: int, name: str, pos: str, team: str, value: Any) -> dict[str, Any]:
    """Build a synthetic leader entry shaped like the MLB Stats API response."""
    return {
        "person": {
            "id": pid,
            "fullName": name,
            "primaryPosition": {"abbreviation": pos},
        },
        "team": {"name": team},
        "value": value,
    }


class TestMapPosition:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("C", "C"),
            ("1B", "1B"),
            ("3B", "1B"),
            ("DH", "1B"),
            ("LF", "OF"),
            ("CF", "OF"),
            ("RF", "OF"),
            ("OF", "OF"),
            ("P", "P"),
            ("SP", "P"),
            ("RP", "P"),
            ("LHP", "P"),
            ("RHP", "P"),
            ("2B", None),
            ("SS", None),
            ("UT", None),
            ("", None),
            (None, None),
            ("  c  ", "C"),
            ("lf", "OF"),
        ],
    )
    def test_position_mapping(self, raw: str | None, expected: str | None) -> None:
        assert map_position(raw) == expected


class TestParseValue:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("42", 42),
            ("0.295", 0.295),
            (42, 42),
            (0.295, 0.295),
            (None, 0),
            ("abc", "abc"),
        ],
    )
    def test_value_parsing(self, raw: Any, expected: Any) -> None:
        assert _parse_value(raw) == expected


class TestMergeRecords:
    def test_single_category(self) -> None:
        leaders = {"homeRuns": [_leader(1, "Judge", "RF", "NYY", "62")]}
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert 1 in result
        assert result[1]["name"] == "Judge"
        assert result[1]["team"] == "NYY"
        assert result[1]["position"] == "RF"
        assert result[1]["stats"] == {"HR": 62}

    def test_multiple_categories_same_player(self) -> None:
        leaders = {
            "homeRuns": [_leader(1, "Judge", "RF", "NYY", "62")],
            "runsBattedIn": [_leader(1, "Judge", "RF", "NYY", "144")],
            "battingAverage": [_leader(1, "Judge", "RF", "NYY", "0.295")],
        }
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert result[1]["stats"] == {"HR": 62, "RBI": 144, "AVG": 0.295}

    def test_different_players_in_different_categories(self) -> None:
        leaders = {
            "homeRuns": [_leader(1, "Judge", "RF", "NYY", "62")],
            "stolenBases": [_leader(2, "Acuña", "RF", "ATL", "73")],
        }
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert set(result.keys()) == {1, 2}
        assert result[1]["stats"] == {"HR": 62}
        assert result[2]["stats"] == {"SB": 73}

    def test_skips_missing_id(self) -> None:
        leaders = {"homeRuns": [{"person": {"fullName": "Anon"}, "value": "1"}]}
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert result == {}


class TestFetchLeaders:
    def test_uses_cache_when_present(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        cached = [_leader(99, "Cached", "C", "NYY", "5")]
        (tmp_path / "leaders_hitting_homeRuns_2025_l75.json").write_text(json.dumps(cached))

        with patch("app.ingest.statsapi.get") as mock_get:
            result = fetch_leaders("homeRuns", 2025, "hitting", 75)

        mock_get.assert_not_called()
        assert result == cached

    def test_writes_cache_on_miss(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        response = {
            "leagueLeaders": [{"leaders": [_leader(1, "X", "C", "NYY", "10")]}]
        }

        with patch("app.ingest.statsapi.get", return_value=response) as mock_get:
            result = fetch_leaders("homeRuns", 2025, "hitting", 75)

        mock_get.assert_called_once_with(
            "stats_leaders",
            {
                "leaderCategories": "homeRuns",
                "season": 2025,
                "limit": 75,
                "statGroup": "hitting",
                "sportId": 1,
            },
        )
        assert len(result) == 1
        assert (tmp_path / "leaders_hitting_homeRuns_2025_l75.json").exists()

    def test_handles_empty_response(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        with patch("app.ingest.statsapi.get", return_value={}):
            result = fetch_leaders("homeRuns", 2025, "hitting", 75)
        assert result == []


class TestIngestSeason:
    def test_persists_players_with_mapped_positions(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        def fake_get(_endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
            group = params["statGroup"]
            if group == "hitting":
                leaders = [
                    _leader(100, "Judge", "RF", "NYY", "62"),
                    _leader(101, "Olson", "1B", "ATL", "54"),
                    _leader(103, "Realmuto", "C", "PHI", "25"),
                    _leader(104, "Albies", "2B", "ATL", "30"),  # excluded
                ]
                return {"leagueLeaders": [{"leaders": leaders}]}
            if group == "pitching":
                leaders = [
                    _leader(200, "deGrom", "SP", "NYM", "210"),
                    _leader(201, "Hader", "RP", "HOU", "45"),
                ]
                return {"leagueLeaders": [{"leaders": leaders}]}
            return {"leagueLeaders": [{"leaders": []}]}

        with patch("app.ingest.statsapi.get", side_effect=fake_get):
            count = ingest_season(session, season=2025, limit=10)

        all_players = list_all_players(session)
        assert count == 5  # Albies (2B) excluded; rest kept
        assert len(all_players) == 5
        names = {p.name for p in all_players}
        assert "Albies" not in names
        assert {"Judge", "Olson", "Realmuto", "deGrom", "Hader"} == names

    def test_stats_blob_contains_fantasy_keys(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        def fake_get(_endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
            if params["statGroup"] == "hitting":
                return {
                    "leagueLeaders": [
                        {"leaders": [_leader(100, "Judge", "RF", "NYY", "62")]}
                    ]
                }
            return {"leagueLeaders": [{"leaders": []}]}

        with patch("app.ingest.statsapi.get", side_effect=fake_get):
            ingest_season(session, season=2025, limit=10)

        players = list_all_players(session)
        assert len(players) == 1
        for fantasy_key in HITTING_CATEGORIES.values():
            assert fantasy_key in players[0].stats, f"missing {fantasy_key}"

    def test_position_collapses_correctly(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        def fake_get(_endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
            if params["statGroup"] == "hitting":
                return {
                    "leagueLeaders": [
                        {
                            "leaders": [
                                _leader(1, "A", "LF", "NYY", "10"),  # → OF
                                _leader(2, "B", "3B", "BOS", "20"),  # → 1B
                                _leader(3, "C", "DH", "TEX", "30"),  # → 1B
                            ]
                        }
                    ]
                }
            if params["statGroup"] == "pitching":
                return {
                    "leagueLeaders": [
                        {"leaders": [_leader(4, "D", "RHP", "NYY", "200")]}  # → P
                    ]
                }
            return {"leagueLeaders": [{"leaders": []}]}

        with patch("app.ingest.statsapi.get", side_effect=fake_get):
            ingest_season(session, season=2025, limit=10)

        players = {p.name: p.position for p in list_all_players(session)}
        assert players == {"A": "OF", "B": "1B", "C": "1B", "D": "P"}

    def test_idempotent_via_cache(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        def fake_get(_endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
            if params["statGroup"] == "hitting":
                return {
                    "leagueLeaders": [{"leaders": [_leader(1, "X", "C", "NYY", "5")]}]
                }
            return {"leagueLeaders": [{"leaders": []}]}

        with patch("app.ingest.statsapi.get", side_effect=fake_get) as mock_get:
            ingest_season(session, season=2025, limit=10)
            first_call_count = mock_get.call_count
            ingest_season(session, season=2025, limit=10)
            assert mock_get.call_count == first_call_count

        assert len(list_all_players(session)) == 1

    def test_unmappable_player_skipped(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        def fake_get(_endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
            if params["statGroup"] == "hitting":
                return {
                    "leagueLeaders": [
                        {
                            "leaders": [
                                _leader(1, "SS Guy", "SS", "NYY", "10"),
                                _leader(2, "C Guy", "C", "BOS", "20"),
                            ]
                        }
                    ]
                }
            return {"leagueLeaders": [{"leaders": []}]}

        with patch("app.ingest.statsapi.get", side_effect=fake_get):
            count = ingest_season(session, season=2025, limit=10)

        assert count == 1
        assert {p.name for p in list_all_players(session)} == {"C Guy"}
