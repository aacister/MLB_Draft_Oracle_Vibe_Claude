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
    collect_position_ids,
    fetch_hitting_stats_batch,
    fetch_leaders,
    fetch_people,
    fetch_team_roster,
    fetch_teams,
    ingest_season,
    map_position,
    merge_records,
)
from app.repositories.player import list_all_players, list_players_by_position


def _people_response(id_to_pos: dict[int, str]) -> dict[str, Any]:
    """Build a /people endpoint response with primaryPosition for each id."""
    return {
        "people": [
            {"id": pid, "primaryPosition": {"abbreviation": pos}}
            for pid, pos in id_to_pos.items()
        ]
    }


def _leader(pid: int, name: str, team: str, value: Any) -> dict[str, Any]:
    """Build a synthetic leader entry shaped like the MLB Stats API response.

    Note: the real stats_leaders endpoint does NOT include primaryPosition in the
    person object; positions come from a separate /people call. Tests reflect that.
    """
    return {
        "person": {"id": pid, "fullName": name},
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
        leaders = {"homeRuns": [_leader(1, "Judge", "NYY", "62")]}
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert 1 in result
        assert result[1]["name"] == "Judge"
        assert result[1]["team"] == "NYY"
        assert result[1]["stats"] == {"HR": 62}

    def test_multiple_categories_same_player(self) -> None:
        leaders = {
            "homeRuns": [_leader(1, "Judge", "NYY", "62")],
            "runsBattedIn": [_leader(1, "Judge", "NYY", "144")],
            "battingAverage": [_leader(1, "Judge", "NYY", "0.295")],
        }
        result = merge_records(leaders, HITTING_CATEGORIES)
        assert result[1]["stats"] == {"HR": 62, "RBI": 144, "AVG": 0.295}

    def test_different_players_in_different_categories(self) -> None:
        leaders = {
            "homeRuns": [_leader(1, "Judge", "NYY", "62")],
            "stolenBases": [_leader(2, "Acuña", "ATL", "73")],
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
        cached = [_leader(99, "Cached", "NYY", "5")]
        (tmp_path / "leaders_hitting_homeRuns_2025_l75.json").write_text(json.dumps(cached))

        with patch("app.ingest.statsapi.get") as mock_get:
            result = fetch_leaders("homeRuns", 2025, "hitting", 75)

        mock_get.assert_not_called()
        assert result == cached

    def test_writes_cache_on_miss(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        response = {"leagueLeaders": [{"leaders": [_leader(1, "X", "NYY", "10")]}]}

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


class TestFetchPeople:
    def test_returns_empty_for_empty_input(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        with patch("app.ingest.statsapi.get") as mock_get:
            assert fetch_people([]) == {}
        mock_get.assert_not_called()

    def test_calls_people_endpoint_and_caches(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        response = _people_response({1: "C", 2: "RF"})
        with patch("app.ingest.statsapi.get", return_value=response) as mock_get:
            positions = fetch_people([2, 1])

        assert positions == {1: "C", 2: "RF"}
        mock_get.assert_called_once_with("people", {"personIds": "1,2"})

        # second call hits cache → no new API call
        with patch("app.ingest.statsapi.get") as mock_get2:
            positions_again = fetch_people([1, 2])
        assert positions_again == {1: "C", 2: "RF"}
        mock_get2.assert_not_called()

    def test_batches_large_id_lists(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        monkeypatch.setattr(ingest_module, "PEOPLE_BATCH_SIZE", 3)

        responses = [
            _people_response({1: "C", 2: "C", 3: "RF"}),
            _people_response({4: "SP", 5: "RP"}),
        ]
        with patch("app.ingest.statsapi.get", side_effect=responses) as mock_get:
            positions = fetch_people([1, 2, 3, 4, 5])

        assert positions == {1: "C", 2: "C", 3: "RF", 4: "SP", 5: "RP"}
        assert mock_get.call_count == 2


def _make_fake_get(
    hitting_leaders: list[dict[str, Any]],
    pitching_leaders: list[dict[str, Any]],
    id_to_position: dict[int, str],
    teams: list[int] | None = None,
    rosters: dict[int, list[dict[str, Any]]] | None = None,
    hitting_stats: dict[int, dict[str, Any]] | None = None,
) -> Any:
    """Build a fake statsapi.get that dispatches on endpoint and request shape.

    Parameters with None default to empty so existing tests don't need updates.
    """
    teams = teams or []
    rosters = rosters or {}
    hitting_stats = hitting_stats or {}

    def fake_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        if endpoint == "stats_leaders":
            group = params["statGroup"]
            if group == "hitting":
                return {"leagueLeaders": [{"leaders": hitting_leaders}]}
            if group == "pitching":
                return {"leagueLeaders": [{"leaders": pitching_leaders}]}
            return {"leagueLeaders": [{"leaders": []}]}
        if endpoint == "people" and "hydrate" not in params:
            ids = [int(x) for x in params["personIds"].split(",")]
            return {
                "people": [
                    {
                        "id": pid,
                        "primaryPosition": {"abbreviation": id_to_position.get(pid)},
                    }
                    for pid in ids
                ]
            }
        if endpoint == "teams":
            return {"teams": [{"id": tid} for tid in teams]}
        if endpoint == "team_roster":
            return {"roster": rosters.get(int(params["teamId"]), [])}
        if endpoint == "people" and "hydrate" in params:
            # hydrate=stats request — for batch hitting-stat lookups
            ids = [int(x) for x in params["personIds"].split(",")]
            people = []
            for pid in ids:
                if pid not in hitting_stats:
                    continue
                data = hitting_stats[pid]
                people.append(
                    {
                        "id": pid,
                        "fullName": data["name"],
                        "stats": [
                            {
                                "splits": [
                                    {
                                        "team": {"name": data["team"]},
                                        "stat": data["api_stats"],
                                    }
                                ]
                            }
                        ],
                    }
                )
            return {"people": people}
        return {}

    return fake_get


def _roster_entry(pid: int, name: str, pos_abbr: str) -> dict[str, Any]:
    return {
        "person": {"id": pid, "fullName": name},
        "position": {"abbreviation": pos_abbr},
    }


class TestFetchTeams:
    def test_returns_ids_and_caches(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        response = {"teams": [{"id": 110}, {"id": 111}, {"id": 112}]}

        with patch("app.ingest.statsapi.get", return_value=response) as mock_get:
            ids = fetch_teams(2025)
        assert ids == [110, 111, 112]
        mock_get.assert_called_once_with("teams", {"sportId": 1, "season": 2025})

        with patch("app.ingest.statsapi.get") as mock_get2:
            fetch_teams(2025)
        mock_get2.assert_not_called()


class TestFetchTeamRoster:
    def test_returns_roster_and_caches(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        roster = [_roster_entry(1, "A", "C"), _roster_entry(2, "B", "RF")]
        response = {"roster": roster}

        with patch("app.ingest.statsapi.get", return_value=response) as mock_get:
            result = fetch_team_roster(110, 2025)
        assert result == roster
        mock_get.assert_called_once_with(
            "team_roster", {"teamId": 110, "season": 2025, "rosterType": "active"}
        )

        with patch("app.ingest.statsapi.get") as mock_get2:
            fetch_team_roster(110, 2025)
        mock_get2.assert_not_called()


class TestCollectPositionIds:
    def test_walks_all_team_rosters(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        rosters = {
            110: [_roster_entry(1, "C1", "C"), _roster_entry(2, "OF1", "RF")],
            111: [_roster_entry(3, "C2", "C"), _roster_entry(4, "1B1", "1B")],
        }
        fake = _make_fake_get([], [], {}, teams=[110, 111], rosters=rosters)

        with patch("app.ingest.statsapi.get", side_effect=fake):
            catchers = collect_position_ids(2025, "C")

        assert catchers == {1, 3}


class TestFetchHittingStatsBatch:
    def test_returns_fantasy_stats_and_caches(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        stats = {
            7: {
                "name": "Backup C",
                "team": "ATL",
                "api_stats": {"homeRuns": 5, "rbi": 22, "avg": ".240", "atBats": 180},
            }
        }
        fake = _make_fake_get([], [], {}, hitting_stats=stats)

        with patch("app.ingest.statsapi.get", side_effect=fake) as mock_get:
            result = fetch_hitting_stats_batch([7], 2025)

        assert 7 in result
        assert result[7]["name"] == "Backup C"
        assert result[7]["team"] == "ATL"
        assert result[7]["stats"] == {"HR": 5, "RBI": 22, "AVG": 0.240, "AB": 180}

        with patch("app.ingest.statsapi.get") as mock_get2:
            fetch_hitting_stats_batch([7], 2025)
        mock_get2.assert_not_called()

    def test_empty_input_returns_empty(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)
        with patch("app.ingest.statsapi.get") as mock_get:
            assert fetch_hitting_stats_batch([], 2025) == {}
        mock_get.assert_not_called()


class TestIngestSeason:
    def test_persists_players_with_mapped_positions(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        hitting = [
            _leader(100, "Judge", "NYY", "62"),
            _leader(101, "Olson", "ATL", "54"),
            _leader(103, "Realmuto", "PHI", "25"),
            _leader(104, "Albies", "ATL", "30"),  # 2B → excluded
        ]
        pitching = [
            _leader(200, "deGrom", "NYM", "210"),
            _leader(201, "Hader", "HOU", "45"),
        ]
        positions = {
            100: "RF",
            101: "1B",
            103: "C",
            104: "2B",
            200: "SP",
            201: "RP",
        }

        with patch(
            "app.ingest.statsapi.get",
            side_effect=_make_fake_get(hitting, pitching, positions),
        ):
            count = ingest_season(session, season=2025, limit=10)

        all_players = list_all_players(session)
        assert count == 5
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

        with patch(
            "app.ingest.statsapi.get",
            side_effect=_make_fake_get(
                [_leader(100, "Judge", "NYY", "62")], [], {100: "RF"}
            ),
        ):
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

        hitting = [
            _leader(1, "A", "NYY", "10"),
            _leader(2, "B", "BOS", "20"),
            _leader(3, "C", "TEX", "30"),
        ]
        pitching = [_leader(4, "D", "NYY", "200")]
        positions = {1: "LF", 2: "3B", 3: "DH", 4: "RHP"}

        with patch(
            "app.ingest.statsapi.get",
            side_effect=_make_fake_get(hitting, pitching, positions),
        ):
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

        fake_get = _make_fake_get(
            [_leader(1, "X", "NYY", "5")], [], {1: "C"}
        )
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

        hitting = [
            _leader(1, "SS Guy", "NYY", "10"),
            _leader(2, "C Guy", "BOS", "20"),
        ]
        positions = {1: "SS", 2: "C"}

        with patch(
            "app.ingest.statsapi.get",
            side_effect=_make_fake_get(hitting, [], positions),
        ):
            count = ingest_season(session, season=2025, limit=10)

        assert count == 1
        assert {p.name for p in list_all_players(session)} == {"C Guy"}

    def test_supplements_catchers_from_team_rosters(
        self,
        session: Session,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Catchers found on team rosters but not in leader pool are fetched and added."""
        monkeypatch.setattr(ingest_module, "INGESTION_DIR", tmp_path)

        hitting_leaders = [_leader(100, "Slugger", "NYY", "40")]
        rosters = {
            110: [_roster_entry(100, "Slugger", "RF"), _roster_entry(200, "Backup C", "C")],
            111: [_roster_entry(201, "Starter C", "C")],
        }
        # Positions for everyone
        positions = {100: "RF", 200: "C", 201: "C"}
        # Hitting stats for the new catchers (not already in leader pool)
        stats = {
            200: {
                "name": "Backup C",
                "team": "Detroit Tigers",
                "api_stats": {"homeRuns": 5, "rbi": 22, "atBats": 180, "avg": ".240"},
            },
            201: {
                "name": "Starter C",
                "team": "Houston Astros",
                "api_stats": {"homeRuns": 18, "rbi": 60, "atBats": 410, "avg": ".265"},
            },
        }
        fake = _make_fake_get(
            hitting_leaders,
            [],
            positions,
            teams=[110, 111],
            rosters=rosters,
            hitting_stats=stats,
        )

        with patch("app.ingest.statsapi.get", side_effect=fake):
            count = ingest_season(session, season=2025, limit=10)

        # 1 slugger (RF) + 2 catchers supplemented = 3
        assert count == 3
        catchers = list_players_by_position(session, "C")
        assert {c.name for c in catchers} == {"Backup C", "Starter C"}
        backup = next(c for c in catchers if c.name == "Backup C")
        assert backup.stats == {"HR": 5, "RBI": 22, "AB": 180, "AVG": 0.240}
