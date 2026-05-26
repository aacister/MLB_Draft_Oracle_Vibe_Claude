"""Verify model schema, default values, foreign keys, and relationships."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AdpRecord, Draft, Grade, Pick, Player, Team


def _make_player(session: Session, player_id: int = 12345) -> Player:
    player = Player(
        id=player_id,
        name="Aaron Judge",
        mlb_team="NYY",
        position="OF",
        stats={"HR": 58, "RBI": 144, "AVG": 0.267},
    )
    session.add(player)
    session.flush()
    return player


def test_draft_defaults(session: Session) -> None:
    draft = Draft(name="Witty Draft Name")
    session.add(draft)
    session.commit()

    assert len(draft.id) == 36
    assert draft.id == draft.id.lower()
    assert draft.status == "pending"
    assert draft.config == {}
    assert draft.created_at is not None


def test_draft_to_team_relationship(session: Session) -> None:
    draft = Draft(name="D")
    team_a = Team(name="Bombers", strategy_name="Power Hitting", draft=draft)
    team_b = Team(name="Speedsters", strategy_name="Speed & Defense", draft=draft)
    session.add(draft)
    session.commit()

    assert team_a.draft_id == draft.id
    assert {t.name for t in draft.teams} == {"Bombers", "Speedsters"}


def test_pick_relationships(session: Session) -> None:
    draft = Draft(name="D")
    team = Team(name="Bombers", strategy_name="Power Hitting", draft=draft)
    session.add(draft)
    session.flush()
    player = _make_player(session)

    pick = Pick(
        draft_id=draft.id,
        team_id=team.id,
        player_id=player.id,
        round=1,
        pick_number=1,
        rationale="Top slugger on the board.",
    )
    session.add(pick)
    session.commit()

    assert pick.player.name == "Aaron Judge"
    assert pick.team.strategy_name == "Power Hitting"
    assert draft.picks == [pick]


def test_grade_round_trip(session: Session) -> None:
    draft = Draft(name="D")
    team = Team(name="Bombers", strategy_name="Power Hitting", draft=draft)
    session.add(draft)
    session.flush()

    grade = Grade(
        team_id=team.id,
        draft_id=draft.id,
        alignment_score=88,
        letter="B",
        rationale="Strong power core; one miss at catcher.",
    )
    session.add(grade)
    session.commit()

    assert grade.id and len(grade.id) == 36
    assert grade.alignment_score == 88
    assert grade.letter == "B"


def test_adp_record_round_trip(session: Session) -> None:
    draft = Draft(name="D")
    session.add(draft)
    session.flush()
    player = _make_player(session)

    record = AdpRecord(draft_id=draft.id, player_id=player.id, pick_number=3, season=2025)
    session.add(record)
    session.commit()

    assert record.id and len(record.id) == 36
    assert record.pick_number == 3
    assert record.season == 2025


def test_player_natural_id_preserved(session: Session) -> None:
    """Player primary key must be the MLB Stats API integer, not auto-generated."""
    player = _make_player(session, player_id=592450)
    session.commit()

    assert player.id == 592450


def test_draft_cascade_delete_picks(session: Session) -> None:
    draft = Draft(name="D")
    team = Team(name="Bombers", strategy_name="Power Hitting", draft=draft)
    session.add(draft)
    session.flush()
    player = _make_player(session)
    session.add(
        Pick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=player.id,
            round=1,
            pick_number=1,
            rationale="r",
        )
    )
    session.commit()

    session.delete(draft)
    session.commit()

    assert session.query(Pick).count() == 0
    assert session.query(Team).count() == 0
