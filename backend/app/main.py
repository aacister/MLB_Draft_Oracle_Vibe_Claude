"""FastAPI entry point for the MLB Draft Oracle backend.

Run via: ``uv run uvicorn app.main:app --reload --port 8000``
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
