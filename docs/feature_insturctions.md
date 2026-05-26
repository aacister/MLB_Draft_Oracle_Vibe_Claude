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

---

## MLB-4: Write docs/decisions.md restating the choices in one-or-two-sentence form

**Status:** Done — merged to `main` via branch `mlb-4-decisions-doc`

Created `docs/decisions.md` as a single-page summary for contributors. Restates the 6 hard constraints (Python 3.12+, FastAPI, SQLite, React+Tailwind, local-only, JSON-on-disk) and the 10 design decisions (OpenAI Agents SDK with gpt-4o-mini, sentence-transformers MiniLM-L6-v2 local embeddings, DuckDuckGo via ddgs, MLB-StatsAPI, NumPy vector store, SSE streaming, asyncio-only concurrency, Vite+React 19+Tailwind 4, SQLAlchemy 2.x create_all). Documents the contract: do not deviate without asking. Also lists the required `.env.example` variables.

---

## MLB-5: Generate the project layout, pyproject.toml, package.json, .env.example, .mcp.json, .gitignore, and a README skeleton

**Status:** Done — merged to `main` via branch `mlb-5-project-scaffold`

Scaffolded the project structure per CLAUDE.MD + decisions.md:

| File / dir | What it provides |
|---|---|
| `backend/pyproject.toml` | uv project (Python 3.12+): fastapi, sqlalchemy 2, openai-agents, sentence-transformers, ddgs, mlb-statsapi, numpy, pydantic 2; dev: ruff, pytest, pytest-asyncio, httpx |
| `frontend/package.json` | React 19, Vite 6, Tailwind 4 (`@tailwindcss/vite`), lucide-react, recharts; dev: vitest, @testing-library/react, eslint, prettier |
| `.env.example` | OPENAI_API_KEY, TAVILY_API_KEY (optional), SEASON, EMBEDDING_MODEL, AGENT_MODEL |
| `.mcp.json` | Three project-scoped MCP servers: filesystem, sqlite, github |
| `README.md` | Concise skeleton: stack summary, quick-start, MCP setup, layout, testing |
| `scripts/.gitkeep` | Placeholder for future OS-specific start/stop scripts |
| `.gitignore` | Added `data/` and `memory/` (created locally per README mkdir step) |

Deferred to later tickets: start/stop scripts, backend source code (MLB-6+), frontend source + vite.config.ts + tsconfig.json (MLB-11).
