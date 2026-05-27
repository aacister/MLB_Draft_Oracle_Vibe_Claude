"""Witty draft and team name generators.

Pure functions over a small set of templates. Deterministic when an explicit
``rng`` is supplied (used in tests), random otherwise.
"""

from __future__ import annotations

import random

DRAFT_NAME_TEMPLATES = (
    "The {adj} {noun}",
    "{year} {adj} {noun}",
    "{adj} {noun} Showdown",
    "Battle of the {adj} {noun}",
    "{noun}: A {adj} Rivalry",
)

DRAFT_ADJECTIVES = (
    "Mighty", "Cosmic", "Rowdy", "Crimson", "Iron", "Wily",
    "Storied", "Brazen", "Lonesome", "Twilight", "Howling", "Stoic",
)

DRAFT_NOUNS = (
    "Showdown", "Reckoning", "Gambit", "Crusade", "Pennant",
    "Diamond Duel", "Bullpen Brawl", "Cage Match", "Outfield Frontier",
)

DEFAULT_TEAM_NAMES: dict[str, tuple[str, ...]] = {
    "Power Hitting": ("Bombers", "Sluggers", "Long Ball Crew", "Mashers", "Big Sticks"),
    "Speed & Defense": ("Speedsters", "Burners", "Glove Crew", "Wheels", "Dash"),
    "Balanced": ("Allrounders", "The Steady", "Equilibrium", "Pivot", "Centerline"),
    "Ace Pitching": ("Aces", "Rotation Kings", "Strike Zone", "Heaters", "Flamethrowers"),
    "Closer-Heavy": ("Closers", "Lockdown", "9th Inning Crew", "Save Squad", "Hammer Time"),
    "Contrarian Value": ("Contrarians", "Off-Script", "Late Round Heroes", "Patient Mob", "Hidden Gems"),
}


def generate_draft_name(*, rng: random.Random | None = None, year: int = 2025) -> str:
    """Return a witty draft name. Deterministic when ``rng`` is provided."""
    r = rng or random
    template = r.choice(DRAFT_NAME_TEMPLATES)
    return template.format(
        adj=r.choice(DRAFT_ADJECTIVES),
        noun=r.choice(DRAFT_NOUNS),
        year=year,
    )


def generate_team_name(strategy_name: str, *, rng: random.Random | None = None) -> str:
    """Return a team name appropriate to the strategy. Deterministic when ``rng`` is provided."""
    r = rng or random
    pool = DEFAULT_TEAM_NAMES.get(strategy_name, ("The Roster",))
    return r.choice(pool)
