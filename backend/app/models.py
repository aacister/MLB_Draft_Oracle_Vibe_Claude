"""SQLAlchemy 2.x ORM models for the MLB Draft Oracle database."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Draft(Base):
    """A single draft session between two AI-strategy teams."""

    __tablename__ = "draft"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    teams: Mapped[list[Team]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )
    picks: Mapped[list[Pick]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class Team(Base):
    """A team within a draft, assigned a single strategy."""

    __tablename__ = "team"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("draft.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)

    draft: Mapped[Draft] = relationship(back_populates="teams")
    picks: Mapped[list[Pick]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class Player(Base):
    """An MLB player with stats. Primary key is the MLB Stats API natural id."""

    __tablename__ = "player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    mlb_team: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[str] = mapped_column(String(4), nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class Pick(Base):
    """A single draft pick — a player selected by a team in a given round."""

    __tablename__ = "pick"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("draft.id"), nullable=False)
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("team.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("player.id"), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    pick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    draft: Mapped[Draft] = relationship(back_populates="picks")
    team: Mapped[Team] = relationship(back_populates="picks")
    player: Mapped[Player] = relationship()


class Grade(Base):
    """Post-draft grade for a team: deterministic score plus narrated letter and rationale."""

    __tablename__ = "grade"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("team.id"), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("draft.id"), nullable=False)
    alignment_score: Mapped[int] = mapped_column(Integer, nullable=False)
    letter: Mapped[str] = mapped_column(String(1), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )


class AdpRecord(Base):
    """One average-draft-position datapoint: a player's pick number in a specific draft."""

    __tablename__ = "adp_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("draft.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("player.id"), nullable=False)
    pick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )


Index("ix_pick_draft_id", Pick.draft_id)
Index("ix_pick_team_id", Pick.team_id)
Index("ix_adp_record_player_id", AdpRecord.player_id)
Index("ix_grade_team_id", Grade.team_id)
