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
    """Build the base player record from one leader entry, or None if id is missing."""
    person = leader.get("person") or {}
    player_id = person.get("id")
    if player_id is None:
        return None
    return {
        "id": int(player_id),
        "name": person.get("fullName", "Unknown"),
        "team": (leader.get("team") or {}).get("name", "Unknown"),
        "position": (person.get("primaryPosition") or {}).get("abbreviation"),
        "stats": {},
    }


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

    written = 0
    for record in all_players.values():
        position = map_position(record["position"])
        if position is None:
            continue
        upsert_player(
            session,
            player_id=record["id"],
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
