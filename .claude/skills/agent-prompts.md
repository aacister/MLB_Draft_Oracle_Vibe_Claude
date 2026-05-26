---
name: agent-prompts
description: House style for MLB Draft Oracle agent prompts and agent configuration. Use when writing or editing Researcher, Drafter, or Grader prompts, defining agent tools, setting max-turn limits, or authoring any agent-related code.
---

# Agent Prompts: MLB Draft Oracle

## Framework

OpenAI Agents SDK (`openai-agents`). Model: `gpt-4o-mini` for all three agents.

```python
from agents import Agent, Runner, tool
```

## Max-Turn Constraints

Every agent **must** have a bounded max-turns. No agent can loop indefinitely.

| Agent | Max turns |
|-------|-----------|
| Researcher | 6 |
| Drafter | 4 |
| Grader | 3 |

Set via the SDK's `max_turns` parameter (or equivalent). If an agent hits its limit without completing, raise a recoverable exception — do not silently return a partial result.

## Agent: Researcher

**Purpose**: Given the current team's strategy, remaining roster needs, and the available player pool, recommend 3–5 still-available candidates ranked by fit.

**Inputs** (injected into the system prompt or as context):
- `strategy_name` + `strategy_description` + `tag_list`
- `roster_needs`: list of positions still unfilled
- `available_players`: player pool (id, name, position, stats)
- `draft_history`: picks already made in this draft (for context)

**Tools the Researcher may call**:
1. `web_search(query: str) -> list[SearchResult]` — DuckDuckGo via `ddgs`. Cache results.
2. `adp_lookup(player_id: int) -> AdpSummary` — returns mean pick number and appearance count.

**Output format** (Structured Output):
```python
class Candidate(BaseModel):
    player_id: int
    player_name: str
    position: str
    rank: int          # 1 = top pick
    rationale: str     # 1–2 sentences citing stats and/or web evidence
    citations: list[str]  # URLs or "MLB Stats API"

class ResearchResult(BaseModel):
    candidates: list[Candidate]  # 3–5 items, ordered by rank
```

**Prompt style**:
- Be concise. Cite evidence (stat values or search snippets), not opinions.
- Always respect position needs — do not recommend a catcher if the roster already has one and the quota is met.
- Reference ADP where available to flag value picks.

## Agent: Drafter

**Purpose**: Read the Researcher's ranked candidates, pick one that fills an open roster slot, and commit the pick with a rationale.

**Inputs**:
- `candidates`: ResearchResult from the Researcher
- `current_roster`: picks already made by this team
- `strategy_name` + `strategy_description`

**Retry logic**: If the top candidate fails validation (player already drafted, position quota already met), try the next candidate. Maximum 3 retry attempts; raise after exhausting the list.

**Output format** (Structured Output):
```python
class DraftPick(BaseModel):
    player_id: int
    player_name: str
    position: str
    rationale: str   # 2–3 sentences explaining the pick relative to the strategy
```

**Prompt style**:
- Pick must fill an open position slot.
- Rationale must reference the strategy by name and cite at least one stat.
- Keep it punchy — 2–3 sentences only.

## Agent: Grader

**Purpose**: Given the deterministic `alignment_score` (0–100) and the team's picks, produce a letter grade and a 2–3 sentence rationale. The Grader **never re-computes the score** — it only narrates.

**Inputs**:
- `team_name`, `strategy_name`, `strategy_description`
- `picks`: list of DraftPick with player names, positions, and stats
- `alignment_score`: integer 0–100 (pre-computed, passed in)
- `cohort_fit`: float, for context
- `tag_fit`: float, for context

**Output format** (Structured Output):
```python
class GradeResult(BaseModel):
    letter: Literal["A", "B", "C", "D", "F"]
    rationale: str   # 2–3 sentences referencing alignment_score and specific picks
```

**Letter scale**:
| Score | Letter |
|-------|--------|
| 90–100 | A |
| 75–89 | B |
| 55–74 | C |
| 35–54 | D |
| 0–34 | F |

**Prompt style**:
- Reference the alignment_score explicitly in the rationale.
- Call out standout picks (best fit) and any misses.
- Never invent a different score or override the provided one.

## General Prompt Discipline

- System prompts: terse. State the agent's role, inputs, and output contract. No filler.
- Avoid open-ended instructions ("do your best") — be specific about what constitutes a valid response.
- All agent outputs use Pydantic Structured Outputs so downstream code can access fields reliably.
- Log agent turn counts and tool calls at DEBUG level for observability.
