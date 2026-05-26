"""Per-draft snapshot files at ``./memory/drafts/<draft_id>.json``.

Rewritten after every pick so the Grader and future Researcher runs can read a
consistent view without re-querying SQLite.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.paths import DRAFTS_DIR
from app.repositories import draft as draft_repo
from app.repositories import pick as pick_repo
from app.repositories import team as team_repo


def _pick_dict(pick: Any) -> dict[str, Any]:
    return {
        "id": pick.id,
        "round": pick.round,
        "pick_number": pick.pick_number,
        "player_id": pick.player_id,
        "player_name": pick.player.name,
        "position": pick.player.position,
        "rationale": pick.rationale,
    }


def build_snapshot(session: Session, draft_id: str) -> dict[str, Any] | None:
    """Compose the current snapshot dict for a draft, or None if it doesn't exist."""
    draft = draft_repo.get_draft(session, draft_id)
    if draft is None:
        return None
    teams = team_repo.list_teams_for_draft(session, draft_id)
    return {
        "draft_id": draft.id,
        "name": draft.name,
        "status": draft.status,
        "config": draft.config,
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "strategy": team.strategy_name,
                "picks": [
                    _pick_dict(p)
                    for p in pick_repo.list_picks_for_team(session, team.id)
                ],
            }
            for team in teams
        ],
    }


def write_snapshot(session: Session, draft_id: str) -> dict[str, Any] | None:
    """Build the snapshot and write it to disk. Returns the snapshot or None."""
    snapshot = build_snapshot(session, draft_id)
    if snapshot is None:
        return None
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    (DRAFTS_DIR / f"{draft_id}.json").write_text(json.dumps(snapshot, indent=2))
    return snapshot


def read_snapshot(draft_id: str) -> dict[str, Any] | None:
    """Return the on-disk snapshot for a draft, or None if not present."""
    path = DRAFTS_DIR / f"{draft_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
