"""Database engine, session factory, and schema initialization."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.paths import db_url, ensure_dirs


def create_db_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine. Defaults to the on-disk project database."""
    if url is None:
        ensure_dirs()
        url = db_url()
    return create_engine(url, echo=False, future=True)


def init_schema(engine: Engine) -> None:
    """Create all tables. Safe to call repeatedly at boot."""
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
