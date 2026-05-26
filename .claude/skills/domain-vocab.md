---
name: domain-vocab
description: Fantasy-baseball and draft domain vocabulary for MLB Draft Oracle. Use when working on teams, picks, strategies, agent prompts, roster logic, or any code that references draft mechanics or stat categories.
---

# Domain Vocabulary: MLB Draft Oracle

## Draft Mechanics

- **Snake draft**: pick order reverses each round (round 1: team A then B; round 2: team B then A).
- **Round**: one full cycle of picks (both teams pick once). Default is 4 rounds → 4 picks per team.
- **Pick number**: global 1-based counter across all rounds and teams.
- **Slot**: a (round, team) pair; each slot must be filled by exactly one player.
- **Available pool**: players not yet drafted in the current draft.
- **Roster**: the set of picks a team has made so far.

## Positions

Only four positions are used (collapsed from MLB reality):

| Code | Full name | Notes |
|------|-----------|-------|
| `C`  | Catcher   |       |
| `1B` | First baseman | includes corner infielders collapsed to 1B |
| `OF` | Outfielder | all outfield variants (LF, CF, RF) → `OF` |
| `P`  | Pitcher   | starters and relievers both map to `P` |

Roster quotas are defined per strategy config, not globally. Typical default: at least 1 of each position across 4 picks.

## Strategies

Each draft assigns one distinct strategy to each team.

| Strategy name | Primary stat tags | Description |
|---|---|---|
| Power Hitting | HR, SLG, RBI | Target sluggers; accept K risk |
| Speed & Defense | SB, R, AVG | Prioritize speed and contact |
| Balanced | AVG, OBP, mixed | No single focus; floor > ceiling |
| Ace Pitching | K, ERA, WHIP | Dominant starting pitching |
| Closer-Heavy | S, ERA | Relief specialist; target saves |
| Contrarian Value | OBP, late-round | High OBP or undervalued players |

A draft picks **two distinct** strategies, one per team.

## Fantasy Stat Categories

### Hitting
- `HR` — home runs
- `RBI` — runs batted in
- `R` — runs scored
- `SB` — stolen bases
- `AVG` — batting average
- `OBP` — on-base percentage
- `SLG` — slugging percentage
- `AB` — at-bats

### Pitching
- `K` — strikeouts
- `W` — wins
- `S` — saves
- `ERA` — earned run average
- `WHIP` — walks + hits per inning pitched
- `IP` — innings pitched

## Agents

| Agent | Role |
|-------|------|
| **Researcher** | Given strategy + roster needs + available pool → recommends 3–5 candidates with citations |
| **Drafter** | Reads Researcher output, picks one player, produces 2–3 sentence rationale |
| **Grader** | Post-draft only; given deterministic score → letter grade + 2–3 sentence rationale |

## ADP (Average Draft Position)

- **ADP record**: (player_id, pick_number, season, draft_id) — one row per pick.
- **ADP vector**: embedding of an ADP data point, stored in `./memory/vectors/adp/<id>.json`.
- **Overdrafted**: player picked earlier (lower pick number) than their performance rank justifies.
- **Ignored position**: a position whose mean pick number sits above the global median.
- **Season shift**: sliding-window mean pick number over draft-creation order (surfacing rising/falling trends).

## Grading Terminology

- **alignment_score**: deterministic 0–100 score. Formula: `round(100 * (0.5 * cohort_fit + 0.5 * tag_fit))`.
- **cohort_fit**: mean cosine similarity of team pick embeddings to the strategy cohort centroid, mapped to [0, 1].
- **tag_fit**: fraction of picks whose stats clear the strategy's threshold (e.g., Power Hitting → `HR ≥ 25`).
- **Letter grade**: A/B/C/D/F produced by the Grader agent narrating the alignment_score.
