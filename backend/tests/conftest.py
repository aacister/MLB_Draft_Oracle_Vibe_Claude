"""Shared pytest fixtures: in-memory SQLite engine and session per test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
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
