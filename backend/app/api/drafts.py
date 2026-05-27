"""Draft API routes: create, list, get, run, stream."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.schemas import (
    CreateDraftRequest,
    DraftSummary,
    RunResponse,
    TeamSummary,
)
from app.engine import run_draft
from app.events import read_events
from app.names import generate_draft_name, generate_team_name
from app.repositories import draft as draft_repo
from app.repositories import team as team_repo
from app.snapshots import build_snapshot, write_snapshot
from app.strategies import STRATEGIES

router = APIRouter(tags=["drafts"])
logger = logging.getLogger(__name__)

STREAM_POLL_SECONDS = 0.25


def _draft_summary(draft: Any, teams: list[Any]) -> DraftSummary:
    return DraftSummary(
        id=draft.id,
        name=draft.name,
        status=draft.status,
        created_at=draft.created_at,
        config=draft.config or {},
        teams=[
            TeamSummary(id=t.id, name=t.name, strategy=t.strategy_name) for t in teams
        ],
    )


def _pick_strategies(req: CreateDraftRequest) -> tuple[str, str]:
    """Resolve the two strategy names, choosing random distinct ones for any that are None."""
    available = list(STRATEGIES.keys())
    a = req.strategy_a or random.choice(available)
    pool_for_b = [s for s in available if s != a]
    b = req.strategy_b or random.choice(pool_for_b)
    if a == b:
        raise HTTPException(400, "strategies must be distinct")
    if a not in STRATEGIES or b not in STRATEGIES:
        raise HTTPException(400, f"unknown strategy: {a if a not in STRATEGIES else b}")
    return a, b


@router.post("/drafts", response_model=DraftSummary)
def create_draft(
    req: CreateDraftRequest, session: Session = Depends(get_session)
) -> DraftSummary:
    """Create a draft with a witty name and two teams using the chosen strategies."""
    strategy_a, strategy_b = _pick_strategies(req)

    draft = draft_repo.create_draft(
        session, name=generate_draft_name(), config={"num_rounds": req.num_rounds}
    )
    team_a = team_repo.create_team(
        session,
        draft_id=draft.id,
        name=generate_team_name(strategy_a),
        strategy_name=strategy_a,
    )
    team_b = team_repo.create_team(
        session,
        draft_id=draft.id,
        name=generate_team_name(strategy_b),
        strategy_name=strategy_b,
    )
    session.commit()
    write_snapshot(session, draft.id)
    return _draft_summary(draft, [team_a, team_b])


@router.get("/drafts", response_model=list[DraftSummary])
def list_drafts(session: Session = Depends(get_session)) -> list[DraftSummary]:
    """List every draft, newest first."""
    return [
        _draft_summary(d, team_repo.list_teams_for_draft(session, d.id))
        for d in draft_repo.list_drafts(session)
    ]


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Return the full draft snapshot (teams, picks, status, config).

    Always built fresh from the DB so callers see the latest status. The on-disk
    snapshot file at ./memory/drafts/<id>.json is for the Grader and future
    Researcher runs (per CLAUDE.MD §3); it isn't the source of truth for the API.
    """
    snapshot = build_snapshot(session, draft_id)
    if snapshot is None:
        raise HTTPException(404, f"draft {draft_id} not found")
    return snapshot


async def _run_in_background(draft_id: str, factory: Any) -> None:
    """Background task: open a fresh session and run the engine."""
    try:
        with factory() as session:
            await run_draft(session, draft_id)
    except Exception:
        logger.exception("Draft run failed for %s", draft_id)


@router.post("/drafts/{draft_id}/run", response_model=RunResponse)
async def run_draft_endpoint(draft_id: str, request: Request) -> RunResponse:
    """Start the engine for a draft. Idempotent: returns current status if already running/done."""
    factory = request.app.state.session_factory
    running: set[str] = request.app.state.running_drafts

    with factory() as session:
        draft = draft_repo.get_draft(session, draft_id)
        if draft is None:
            raise HTTPException(404, f"draft {draft_id} not found")
        status = draft.status

    if status == "completed":
        return RunResponse(status="completed", draft_id=draft_id)
    if draft_id in running:
        return RunResponse(status="running", draft_id=draft_id)

    running.add(draft_id)
    background_tasks: set = request.app.state.background_tasks

    async def _wrapper() -> None:
        try:
            await _run_in_background(draft_id, factory)
        finally:
            running.discard(draft_id)

    # Hold a strong reference to the Task so it isn't garbage-collected
    # mid-execution. asyncio only keeps a weak ref otherwise.
    task = asyncio.create_task(_wrapper())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return RunResponse(status="running", draft_id=draft_id)


def _format_sse(event: dict[str, Any]) -> str:
    """Render one event as an SSE message."""
    parts: list[str] = []
    if "id" in event:
        parts.append(f"id: {event['id']}")
    if "type" in event:
        parts.append(f"event: {event['type']}")
    parts.append(f"data: {json.dumps(event)}")
    return "\n".join(parts) + "\n\n"


async def event_stream(
    draft_id: str,
    factory: Any,
    *,
    last_event_id: str | None = None,
    poll_seconds: float = STREAM_POLL_SECONDS,
):
    """Async generator yielding SSE strings for a draft's event log.

    Closes the stream once the draft reaches a terminal status.
    """
    seen = last_event_id
    while True:
        for event in read_events(draft_id, since_id=seen):
            seen = event["id"]
            yield _format_sse(event)

        with factory() as session:
            draft = draft_repo.get_draft(session, draft_id)
            if draft is None:
                yield _format_sse({"type": "error", "id": "err", "message": "draft not found"})
                return
            if draft.status == "completed":
                yield _format_sse({"type": "stream_end", "id": "end"})
                return

        await asyncio.sleep(poll_seconds)


@router.get("/drafts/{draft_id}/stream")
async def stream_endpoint(draft_id: str, request: Request) -> StreamingResponse:
    """Stream draft events as Server-Sent Events. Resumable via Last-Event-ID header."""
    factory = request.app.state.session_factory
    last_event_id = request.headers.get("last-event-id")
    return StreamingResponse(
        event_stream(draft_id, factory, last_event_id=last_event_id),
        media_type="text/event-stream",
    )
