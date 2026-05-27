"""FastAPI entry point for the MLB Draft Oracle backend.

Run via: ``uv run uvicorn app.main:app --reload --port 8000``

If ``FRONTEND_DIST`` is set (e.g., in the Docker image) or
``../frontend/dist`` exists, the built React SPA is served from the same
origin so a single container delivers the whole app.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, analytics, drafts, players
from app.db import create_db_engine, init_schema, make_session_factory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the DB engine + session factory once when the app boots."""
    load_dotenv()
    if not hasattr(app.state, "session_factory") or app.state.session_factory is None:
        engine = create_db_engine()
        init_schema(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        logger.info("Database initialized")
    if not hasattr(app.state, "running_drafts"):
        app.state.running_drafts = set()
    yield


app = FastAPI(title="MLB Draft Oracle", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drafts.router, prefix="/v1")
app.include_router(players.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


def _resolve_frontend_dist() -> Path | None:
    """Locate the built frontend, preferring FRONTEND_DIST env."""
    override = os.environ.get("FRONTEND_DIST")
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    local = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    return local if local.is_dir() else None


_FRONTEND_DIST = _resolve_frontend_dist()
if _FRONTEND_DIST is not None:
    logger.info("Serving frontend from %s", _FRONTEND_DIST)
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve index.html for any non-API path so client-side routing works."""
        # API and health routes are matched earlier; this catches everything else.
        if full_path.startswith("v1/"):
            raise HTTPException(status_code=404, detail="not found")
        index = _FRONTEND_DIST / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="frontend not built")
        return FileResponse(index)
