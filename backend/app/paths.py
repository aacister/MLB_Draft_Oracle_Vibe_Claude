"""Single source of truth for filesystem paths used by the backend."""

from __future__ import annotations

import os
from pathlib import Path

# In local dev (backend/app/paths.py), three parents up lands on the repo root.
# In Docker the layout is /app/app/paths.py — three parents up is `/`, which is
# wrong. Honour APP_ROOT when set so the container can point at /app explicitly.
_root_env = os.environ.get("APP_ROOT")
ROOT = Path(_root_env) if _root_env else Path(__file__).resolve().parent.parent.parent

DATA_DIR = ROOT / "data"
MEMORY_DIR = ROOT / "memory"

DB_PATH = DATA_DIR / "mlbdraftoracle.db"

DRAFTS_DIR = MEMORY_DIR / "drafts"
VECTORS_PICKS_DIR = MEMORY_DIR / "vectors" / "picks"
VECTORS_ADP_DIR = MEMORY_DIR / "vectors" / "adp"
AGENTS_DIR = MEMORY_DIR / "agents"
SEARCH_CACHE_DIR = MEMORY_DIR / "search_cache"
INGESTION_DIR = MEMORY_DIR / "ingestion"

ALL_DIRS = (
    DATA_DIR,
    MEMORY_DIR,
    DRAFTS_DIR,
    VECTORS_PICKS_DIR,
    VECTORS_ADP_DIR,
    AGENTS_DIR,
    SEARCH_CACHE_DIR,
    INGESTION_DIR,
)


def ensure_dirs() -> None:
    """Create every data and memory directory if it does not already exist."""
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def db_url() -> str:
    """SQLAlchemy URL for the on-disk SQLite database."""
    return f"sqlite:///{DB_PATH}"
