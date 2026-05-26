# Feature Instructions Log

Completed Jira features with implementation details. Updated after each PR merge.

---

## MLB-1: Read this CLAUDE.md file completely

**Status:** Done

Read the full CLAUDE.MD to understand the project: MLB Draft Oracle is an autonomous AI fantasy baseball draft simulator. Key decisions recorded: Python/FastAPI backend, React/Tailwind frontend, SQLite database, OpenAI Agents SDK with gpt-4o-mini, local-only architecture, uv as package manager.

---

## MLB-2: Confirm the dev MCPs are configured

**Status:** Done

Verified all required MCPs are active in the session: `atlassian` (Jira workflow), `github` (PR creation), `brave-search` (web research), `ide` (code execution). No missing MCPs; no changes required.

---

## MLB-3: Use skill-creator to scaffold the five custom skills from CLAUDE.md

**Status:** Done — merged to `main` via branch `mlb-3-custom-skills`

Created five custom Claude Code skills in `.claude/skills/`:

| Skill file | Purpose |
|---|---|
| `domain-vocab.md` | Fantasy-baseball vocabulary: draft mechanics, positions, strategies, stat categories, ADP, grading terms |
| `sqlite-conventions.md` | Table naming, UUID v4 format, JSON-column patterns, SQLAlchemy 2.x model/repository patterns, required tables and indexes |
| `agent-prompts.md` | House style for Researcher/Drafter/Grader agents: input shapes, Pydantic Structured Output schemas, max-turn limits (6/4/3), retry logic |
| `vector-store.md` | Embedding model (`all-MiniLM-L6-v2`, local CPU, 384-dim), pick/ADP JSON file schemas, NumPy cosine-search, mtime-keyed in-process cache |
| `local-only.md` | Hard constraint checklist: no cloud services, no external workers, SQLite+JSON-on-disk only, permitted external calls (OpenAI, ddgs, mlb-statsapi) |
