"""Shared pytest fixtures: in-memory SQLite engine, session, and FastAPI TestClient."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import create_db_engine, init_schema, make_session_factory


@pytest.fixture
def engine() -> Engine:
    """A fresh in-memory SQLite engine with the schema created."""
    eng = create_db_engine("sqlite:///:memory:")
    init_schema(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A SQLAlchemy session bound to the in-memory engine. Auto-closed."""
    factory = make_session_factory(engine)
    with factory() as s:
        yield s


@pytest.fixture
def isolated_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point every module-level path constant at a tmp_path subdirectory.

    Each consumer module imported ``from app.paths import X``, so we monkeypatch the
    consumer references — patching ``app.paths.X`` would not propagate.
    """
    import app.events
    import app.ingest
    import app.search
    import app.snapshots
    import app.vectors

    drafts = tmp_path / "memory" / "drafts"
    picks = tmp_path / "memory" / "vectors" / "picks"
    adp = tmp_path / "memory" / "vectors" / "adp"
    search_cache = tmp_path / "memory" / "search_cache"
    ingestion = tmp_path / "memory" / "ingestion"

    monkeypatch.setattr(app.events, "DRAFTS_DIR", drafts)
    monkeypatch.setattr(app.snapshots, "DRAFTS_DIR", drafts)
    monkeypatch.setattr(app.vectors, "VECTORS_PICKS_DIR", picks)
    monkeypatch.setattr(app.vectors, "VECTORS_ADP_DIR", adp)
    monkeypatch.setattr(app.search, "SEARCH_CACHE_DIR", search_cache)
    monkeypatch.setattr(app.ingest, "INGESTION_DIR", ingestion)
    app.vectors._clear_cache()
    return tmp_path


@pytest.fixture
def client(engine: Engine, isolated_paths: Path) -> Iterator[TestClient]:
    """FastAPI TestClient wired to the in-memory engine and tmp paths.

    Pre-sets ``app.state.session_factory`` so the app lifespan's DB init is skipped.
    """
    from app.main import app

    factory = make_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.running_drafts = set()
    app.state.background_tasks = set()

    with TestClient(app) as c:
        yield c

    # Clear so other tests using `client` get fresh state
    app.state.engine = None
    app.state.session_factory = None
    app.state.running_drafts = set()
    app.state.background_tasks = set()
