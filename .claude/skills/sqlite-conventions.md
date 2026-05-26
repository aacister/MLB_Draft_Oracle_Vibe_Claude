---
name: sqlite-conventions
description: SQLite and SQLAlchemy conventions for MLB Draft Oracle. Use when adding tables, writing repository code, defining models, writing queries, or touching anything in the database layer.
---

# SQLite Conventions: MLB Draft Oracle

## Engine & Session

- SQLite only. One file: `./data/mlbdraftoracle.db`.
- SQLAlchemy 2.x (`sqlalchemy>=2.0`).
- All I/O is synchronous SQLAlchemy inside `run_in_threadpool` — do not use async SQLAlchemy.
- Session factory: `sessionmaker(bind=engine, autoflush=False, autocommit=False)`.
- Yield sessions via a FastAPI dependency; always close on exit.

## Migrations

- v1: `Base.metadata.create_all(engine)` at application startup. No Alembic.
- If Alembic is added later, document it in `docs/decisions.md` first.

## Table Names

Use singular snake_case: `draft`, `team`, `player`, `pick`, `grade`, `adp_record`.

## Primary Keys & IDs

| Table | PK type | Source |
|-------|---------|--------|
| `player` | integer (MLB Stats API natural id) | statsapi response |
| all others | `String(36)`, UUID v4, lowercase | `str(uuid.uuid4())` at creation |

Never use `UUID` column type — store as plain `VARCHAR(36)`. Always lowercase.

```python
import uuid
id: str = Field(default_factory=lambda: str(uuid.uuid4()))
```

## JSON Columns

Use `JSON` column type for any genuinely shape-variable data rather than inventing sub-tables:

- `player.stats` — HR, RBI, R, SB, AVG, OBP, SLG, K, W, S, ERA, WHIP, IP, AB blob.
- `draft.config` — optional extra config (round count, custom team names, etc.).

```python
from sqlalchemy import JSON
stats: Mapped[dict] = mapped_column(JSON, nullable=False)
```

## Required Tables (minimum)

```
draft       id, name, created_at, status, config(JSON)
team        id, draft_id(FK), name, strategy_name
player      id(MLB int), name, mlb_team, position, stats(JSON)
pick        id, draft_id(FK), team_id(FK), player_id(FK), round, pick_number, rationale, created_at
grade       id, team_id(FK), draft_id(FK), alignment_score, letter, rationale, created_at
adp_record  id, draft_id(FK), player_id(FK), pick_number, season, created_at
```

## Indexes

Add only the indexes the actual queries need:

```python
Index("ix_pick_draft_id", Pick.draft_id)
Index("ix_pick_team_id", Pick.team_id)
Index("ix_adp_record_player_id", AdpRecord.player_id)
Index("ix_grade_team_id", Grade.team_id)
```

## Model Pattern

```python
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime
import datetime, uuid

class Base(DeclarativeBase):
    pass

class Draft(Base):
    __tablename__ = "draft"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
```

## Repository Pattern

Each table gets a thin repository module (`backend/repositories/<table>.py`) with functions, not a class hierarchy. Keep functions short and focused.

```python
def get_draft(session: Session, draft_id: str) -> Draft | None:
    return session.get(Draft, draft_id)

def list_drafts(session: Session) -> list[Draft]:
    return session.scalars(select(Draft).order_by(Draft.created_at.desc())).all()
```
