"""Analytical queries used by the leaderboard and ADP trends endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdpRecord, Grade, Player, Team


def avg_score_by_strategy(
    session: Session, strategy: str | None = None
) -> list[dict[str, Any]]:
    """Mean alignment_score per strategy, with the count of grades."""
    q = (
        select(
            Team.strategy_name.label("strategy"),
            func.avg(Grade.alignment_score).label("avg_score"),
            func.count(Grade.id).label("drafts"),
        )
        .join(Grade, Grade.team_id == Team.id)
        .group_by(Team.strategy_name)
        .order_by(func.avg(Grade.alignment_score).desc())
    )
    if strategy is not None:
        q = q.where(Team.strategy_name == strategy)
    return [
        {"strategy": row.strategy, "avg_score": float(row.avg_score), "drafts": int(row.drafts)}
        for row in session.execute(q)
    ]


def overdrafted_players(
    session: Session, min_appearances: int = 3
) -> list[dict[str, Any]]:
    """Players picked at least ``min_appearances`` times, ranked by earliest mean pick.

    A naive "performance rank" is included as the player's HR total (descending);
    callers can derive gap = performance_rank - mean_pick as needed.
    """
    q = (
        select(
            AdpRecord.player_id.label("player_id"),
            func.avg(AdpRecord.pick_number).label("mean_pick"),
            func.count(AdpRecord.id).label("appearances"),
        )
        .group_by(AdpRecord.player_id)
        .having(func.count(AdpRecord.id) >= min_appearances)
        .order_by(func.avg(AdpRecord.pick_number).asc())
    )
    out: list[dict[str, Any]] = []
    for row in session.execute(q):
        player = session.get(Player, row.player_id)
        if player is None:
            continue
        out.append(
            {
                "player_id": row.player_id,
                "player_name": player.name,
                "position": player.position,
                "mean_pick": float(row.mean_pick),
                "appearances": int(row.appearances),
                "hr": player.stats.get("HR", 0),
            }
        )
    return out


def ignored_positions(session: Session) -> list[dict[str, Any]]:
    """Positions whose mean pick number sits above the median across all positions."""
    q = (
        select(
            Player.position.label("position"),
            func.avg(AdpRecord.pick_number).label("mean_pick"),
        )
        .join(AdpRecord, AdpRecord.player_id == Player.id)
        .group_by(Player.position)
    )
    rows = list(session.execute(q))
    if not rows:
        return []
    means = sorted([float(r.mean_pick) for r in rows])
    median = means[len(means) // 2]
    return [
        {
            "position": r.position,
            "mean_pick": float(r.mean_pick),
            "above_median": float(r.mean_pick) > median,
        }
        for r in rows
    ]


def season_shift(session: Session, window: int = 5) -> list[dict[str, Any]]:
    """Sliding-window mean pick number over draft creation order.

    Returns one dict per draft (oldest first) with the rolling-mean pick number
    across the window of the most recent N drafts ending at that point.
    """
    # Aggregate mean pick per draft, in creation order
    from app.models import Draft

    q = (
        select(
            Draft.id.label("draft_id"),
            Draft.created_at.label("created_at"),
            func.avg(AdpRecord.pick_number).label("avg_pick"),
        )
        .join(AdpRecord, AdpRecord.draft_id == Draft.id)
        .group_by(Draft.id)
        .order_by(Draft.created_at.asc())
    )
    rows = list(session.execute(q))
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        window_rows = rows[max(0, i - window + 1) : i + 1]
        rolling = sum(float(w.avg_pick) for w in window_rows) / len(window_rows)
        out.append(
            {
                "draft_id": row.draft_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "rolling_mean_pick": rolling,
            }
        )
    return out
