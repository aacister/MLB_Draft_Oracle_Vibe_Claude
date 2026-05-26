"""2025 MLB player-pool ingestion via MLB-StatsAPI.

Run via: ``uv run python -m app.ingest --season 2025``

Strategy:
- Fetch league leaders for a fixed set of hitting and pitching categories.
- Merge entries by player id so each player owns a single stats blob.
- Collapse raw MLB positions into the four-bucket scheme (C / 1B / OF / P).
- Upsert players into SQLite. Idempotent: re-running re-uses cached responses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import statsapi
from sqlalchemy.orm import Session

from app.db import create_db_engine, init_schema, make_session_factory
from app.paths import INGESTION_DIR
from app.repositories.player import upsert_player

logger = logging.getLogger(__name__)

PEOPLE_BATCH_SIZE = 100
STATS_BATCH_SIZE = 100

STAT_FIELD_TO_FANTASY: dict[str, str] = {
    "homeRuns": "HR",
    "rbi": "RBI",
    "runs": "R",
    "stolenBases": "SB",
    "avg": "AVG",
    "obp": "OBP",
    "slg": "SLG",
    "atBats": "AB",
}


HITTING_CATEGORIES: dict[str, str] = {
    "homeRuns": "HR",
    "runsBattedIn": "RBI",
    "runs": "R",
    "stolenBases": "SB",
    "battingAverage": "AVG",
    "onBasePercentage": "OBP",
    "sluggingPercentage": "SLG",
    "atBats": "AB",
}

PITCHING_CATEGORIES: dict[str, str] = {
    "strikeouts": "K",
    "wins": "W",
    "saves": "S",
    "earnedRunAverage": "ERA",
    "walksAndHitsPerInningPitched": "WHIP",
    "inningsPitched": "IP",
}

POSITION_MAP: dict[str, str] = {
    "C": "C",
    "1B": "1B",
    "3B": "1B",
    "DH": "1B",
    "LF": "OF",
    "CF": "OF",
    "RF": "OF",
    "OF": "OF",
    "P": "P",
    "SP": "P",
    "RP": "P",
    "LHP": "P",
    "RHP": "P",
}


def map_position(raw: str | None) -> str | None:
    """Collapse a raw MLB position abbreviation to one of C / 1B / OF / P.

    Returns None for positions outside the draft scope (2B, SS, IF, UT, etc.).
    """
    if not raw:
        return None
    return POSITION_MAP.get(raw.strip().upper())


def _cache_file(category: str, season: int, stat_group: str, limit: int) -> Path:
    return INGESTION_DIR / f"leaders_{stat_group}_{category}_{season}_l{limit}.json"


def fetch_leaders(
    category: str,
    season: int,
    stat_group: str,
    limit: int = 75,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Fetch league leaders for one stat category. Caches to memory/ingestion/.

    Returns the inner ``leaders`` array from the stats_leaders API response.
    """
    path = _cache_file(category, season, stat_group, limit)
    if use_cache and path.exists():
        return json.loads(path.read_text())

    response = statsapi.get(
        "stats_leaders",
        {
            "leaderCategories": category,
            "season": season,
            "limit": limit,
            "statGroup": stat_group,
            "sportId": 1,
        },
    )
    leagues = response.get("leagueLeaders") or [{}]
    leaders = leagues[0].get("leaders", []) if leagues else []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(leaders))
    return leaders


def _parse_value(raw: Any) -> Any:
    """Coerce string stat values to int or float; pass through everything else."""
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return raw
    s = str(raw)
    try:
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return raw


def _seed_from_leader(leader: dict[str, Any]) -> dict[str, Any] | None:
    """Build the base player record from one leader entry, or None if id is missing.

    The stats_leaders endpoint does not include primaryPosition; positions are
    fetched separately via fetch_people() and applied in ingest_season().
    """
    person = leader.get("person") or {}
    player_id = person.get("id")
    if player_id is None:
        return None
    return {
        "id": int(player_id),
        "name": person.get("fullName", "Unknown"),
        "team": (leader.get("team") or {}).get("name", "Unknown"),
        "stats": {},
    }


def _people_cache_file(player_ids: list[int]) -> Path:
    key = ",".join(str(x) for x in sorted(player_ids))
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return INGESTION_DIR / f"people_{digest}.json"


def fetch_people(
    player_ids: list[int], *, use_cache: bool = True
) -> dict[int, str | None]:
    """Look up primary positions for the given player ids via the /people endpoint.

    Returns a mapping of player_id to raw position abbreviation (e.g., 'C', 'RF', 'SP').
    Calls are batched at PEOPLE_BATCH_SIZE; the whole result set is cached as one file
    keyed by the sha256 of the sorted id list.
    """
    if not player_ids:
        return {}

    path = _people_cache_file(player_ids)
    if use_cache and path.exists():
        return {int(k): v for k, v in json.loads(path.read_text()).items()}

    sorted_ids = sorted(set(player_ids))
    positions: dict[int, str | None] = {}
    for i in range(0, len(sorted_ids), PEOPLE_BATCH_SIZE):
        batch = sorted_ids[i : i + PEOPLE_BATCH_SIZE]
        response = statsapi.get("people", {"personIds": ",".join(str(x) for x in batch)})
        for person in response.get("people", []):
            pid = person.get("id")
            if pid is None:
                continue
            abbr = (person.get("primaryPosition") or {}).get("abbreviation")
            positions[int(pid)] = abbr

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({str(k): v for k, v in positions.items()}))
    return positions


def merge_records(
    leaders_by_category: dict[str, list[dict[str, Any]]],
    category_map: dict[str, str],
) -> dict[int, dict[str, Any]]:
    """Merge leader entries across categories into one record per player.

    The resulting record's ``stats`` blob is keyed by fantasy stat key (HR, RBI, ...).
    """
    players: dict[int, dict[str, Any]] = {}
    for api_cat, fantasy_key in category_map.items():
        for leader in leaders_by_category.get(api_cat, []):
            seed = _seed_from_leader(leader)
            if seed is None:
                continue
            pid = seed["id"]
            if pid not in players:
                players[pid] = seed
            players[pid]["stats"][fantasy_key] = _parse_value(leader.get("value"))
    return players


def _merge_player_dicts(
    a: dict[int, dict[str, Any]], b: dict[int, dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    """Combine two per-player dicts; on key collision merge the stats blobs."""
    out = {pid: {**rec, "stats": dict(rec["stats"])} for pid, rec in a.items()}
    for pid, rec in b.items():
        if pid in out:
            out[pid]["stats"].update(rec["stats"])
        else:
            out[pid] = {**rec, "stats": dict(rec["stats"])}
    return out


def fetch_teams(season: int, *, use_cache: bool = True) -> list[int]:
    """Return all MLB team ids for the given season, cached as one JSON file."""
    path = INGESTION_DIR / f"teams_{season}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())

    response = statsapi.get("teams", {"sportId": 1, "season": season})
    team_ids = [int(t["id"]) for t in response.get("teams", []) if "id" in t]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(team_ids))
    return team_ids


def fetch_team_roster(team_id: int, season: int, *, use_cache: bool = True) -> list[dict[str, Any]]:
    """Return a team's active roster for the season, cached as one JSON file per team."""
    path = INGESTION_DIR / f"roster_{team_id}_{season}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())

    response = statsapi.get(
        "team_roster", {"teamId": team_id, "season": season, "rosterType": "active"}
    )
    roster = response.get("roster", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(roster))
    return roster


def collect_position_ids(season: int, position_abbr: str) -> set[int]:
    """Walk every team's roster and collect player ids whose roster position matches.

    Useful for ensuring positional coverage that league-wide leaders miss
    (e.g., catchers rarely appear in top 75 of HR/RBI/AVG).
    """
    ids: set[int] = set()
    for team_id in fetch_teams(season):
        for entry in fetch_team_roster(team_id, season):
            roster_pos = (entry.get("position") or {}).get("abbreviation")
            if roster_pos == position_abbr:
                pid = (entry.get("person") or {}).get("id")
                if pid is not None:
                    ids.add(int(pid))
    return ids


def _stats_cache_file(player_ids: list[int], season: int, group: str) -> Path:
    key = f"{group}_{season}_" + ",".join(str(x) for x in sorted(player_ids))
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return INGESTION_DIR / f"stats_{group}_{digest}.json"


def fetch_hitting_stats_batch(
    player_ids: list[int], season: int, *, use_cache: bool = True
) -> dict[int, dict[str, Any]]:
    """Batch-fetch season hitting stats for a list of players.

    Uses ``/api/v1/people?personIds=...&hydrate=stats(...)`` which correctly
    filters by id (the plain ``/stats`` endpoint ignores ``personIds`` and just
    returns league-wide leaders).

    Returns ``{player_id: {"name", "team", "stats": {<fantasy key>: value, ...}}}``.
    """
    if not player_ids:
        return {}

    path = _stats_cache_file(player_ids, season, "hitting")
    if use_cache and path.exists():
        return {int(k): v for k, v in json.loads(path.read_text()).items()}

    sorted_ids = sorted(set(player_ids))
    out: dict[int, dict[str, Any]] = {}
    for i in range(0, len(sorted_ids), STATS_BATCH_SIZE):
        batch = sorted_ids[i : i + STATS_BATCH_SIZE]
        response = statsapi.get(
            "people",
            {
                "personIds": ",".join(str(x) for x in batch),
                "hydrate": f"stats(group=[hitting],type=[season],season={season})",
            },
        )
        for person in response.get("people", []):
            pid = person.get("id")
            if pid is None:
                continue
            fantasy_stats: dict[str, Any] = {}
            team_name = "Unknown"
            for section in person.get("stats", []):
                for split in section.get("splits", []):
                    raw = split.get("stat", {})
                    for api_key, fkey in STAT_FIELD_TO_FANTASY.items():
                        if api_key in raw:
                            fantasy_stats[fkey] = _parse_value(raw[api_key])
                    team_name = (split.get("team") or {}).get("name", team_name)
            if fantasy_stats:
                out[int(pid)] = {
                    "name": person.get("fullName", "Unknown"),
                    "team": team_name,
                    "stats": fantasy_stats,
                }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({str(k): v for k, v in out.items()}))
    return out


def ingest_season(session: Session, season: int = 2025, limit: int = 75) -> int:
    """Fetch all categories, merge by player, and upsert into SQLite.

    Returns the number of players persisted (after position filtering).
    """
    logger.info("Fetching hitting leaders for season %d (limit=%d)", season, limit)
    hitting = {
        cat: fetch_leaders(cat, season, "hitting", limit) for cat in HITTING_CATEGORIES
    }
    logger.info("Fetching pitching leaders for season %d (limit=%d)", season, limit)
    pitching = {
        cat: fetch_leaders(cat, season, "pitching", limit) for cat in PITCHING_CATEGORIES
    }

    hitters = merge_records(hitting, HITTING_CATEGORIES)
    pitchers = merge_records(pitching, PITCHING_CATEGORIES)
    all_players = _merge_player_dicts(hitters, pitchers)
    logger.info("Merged %d unique players across all categories", len(all_players))

    logger.info("Supplementing catcher pool from team rosters")
    catcher_ids = collect_position_ids(season, "C")
    new_catcher_ids = [pid for pid in catcher_ids if pid not in all_players]
    logger.info(
        "Found %d catcher ids on rosters; %d not in leader pool",
        len(catcher_ids),
        len(new_catcher_ids),
    )
    if new_catcher_ids:
        catcher_stats = fetch_hitting_stats_batch(new_catcher_ids, season)
        for pid, data in catcher_stats.items():
            all_players[pid] = {
                "id": pid,
                "name": data["name"],
                "team": data["team"],
                "stats": dict(data["stats"]),
            }

    logger.info("Fetching primary positions for %d players", len(all_players))
    positions = fetch_people(list(all_players.keys()))

    written = 0
    for pid, record in all_players.items():
        position = map_position(positions.get(pid))
        if position is None:
            continue
        upsert_player(
            session,
            player_id=pid,
            name=record["name"],
            mlb_team=record["team"],
            position=position,
            stats=record["stats"],
        )
        written += 1
    session.commit()
    logger.info("Persisted %d players (positions in scope)", written)
    return written


def main() -> None:
    """CLI entry point: initialize the DB and ingest a season."""
    parser = argparse.ArgumentParser(description="Ingest the MLB season player pool")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--limit", type=int, default=75)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    engine = create_db_engine()
    init_schema(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        count = ingest_season(session, season=args.season, limit=args.limit)
    print(f"Ingested {count} players for season {args.season}")


if __name__ == "__main__":
    main()
