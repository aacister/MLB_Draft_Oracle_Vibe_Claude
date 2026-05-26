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

---

## MLB-6: Build the SQLite layer (models + repository) and add tests

**Status:** Done — merged to `main` via branch `mlb-6-sqlite-layer`

First substantive backend code. SQLAlchemy 2.x ORM layer plus function-style repositories, all conforming to the `sqlite-conventions` skill.

| Module | Contents |
|---|---|
| `backend/app/paths.py` | Single source of truth for `./data/` and `./memory/{drafts,vectors/{picks,adp},agents,search_cache,ingestion}/` paths; `ensure_dirs()`, `db_url()` |
| `backend/app/db.py` | `create_db_engine(url)` (param URL for tests), `init_schema(engine)`, `make_session_factory(engine)` |
| `backend/app/models.py` | `Draft`, `Team`, `Player`, `Pick`, `Grade`, `AdpRecord` with relationships, cascade-delete (`Draft → Team/Pick`), the 4 indexes from the skill, and `Player.id` as MLB natural integer |
| `backend/app/repositories/*.py` | One file per table, function-style CRUD (no class hierarchies) |
| `backend/tests/conftest.py` | Fresh in-memory SQLite engine + session per test |
| `backend/tests/test_models.py` | 7 tests: defaults, FK relationships, cascade delete, natural id |
| `backend/tests/test_repositories.py` | 12 tests covering every repository function |

`uv sync` resolved 115 packages; `uv run pytest` → **19/19 passing in 0.26s**. Also committed `uv.lock` for reproducibility and added `pythonpath = ["."]` to `pyproject.toml`'s pytest config.

Used `datetime.UTC` (Python 3.12+) per CLAUDE.MD's "latest APIs" rule.

---

## MLB-7: Build the 2025 player-pool ingestion and verify it populates the table

**Status:** Done — merged to `main` via branch `mlb-7-player-pool-ingestion`

First end-to-end backend feature. Ingests 2025 MLB season league leaders into SQLite via `mlb-statsapi`, with file-based response caching so a fresh DB can be re-seeded offline.

| Component | Detail |
|---|---|
| `backend/app/ingest.py` | Single module (~230 LoC). Hitting categories: HR, RBI, R, SB, AVG, OBP, SLG, AB. Pitching categories: K, W, S, ERA, WHIP, IP. Position collapse: `C→C`; `1B/3B/DH→1B`; `LF/CF/RF/OF→OF`; `P/SP/RP/LHP/RHP→P`; `2B/SS/UT→skipped`. |
| `fetch_leaders()` | Wraps `statsapi.get('stats_leaders', ...)`. Caches per (category, season, group, limit) to `memory/ingestion/leaders_<group>_<category>_<season>_l<limit>.json`. |
| `ingest_season()` | Fetches all 14 categories, merges by player id, calls `upsert_player` for each player whose position maps successfully. |
| `main()` | argparse CLI; runs via `uv run python -m app.ingest --season 2025 [--limit 75]` from `backend/`. |
| `backend/tests/test_ingest.py` | 38 new tests covering position mapping (parametrized), value parsing, record merging, cache hit/miss, full ingestion with mocked `statsapi.get`, idempotency via cache, position-based exclusion. |

`uv run pytest` → **57/57 passing in 3.57s**.

Also fixed the README quick-start: module paths use `app.ingest` and `app.main` (not `backend.app.*`), with `cd backend` made explicit before `uv` commands.

### MLB-7 follow-up fix: position lookup + catcher supplement

Merged to `main` via `mlb-7-fix-position-and-catchers` after live-API testing revealed two root causes:

1. **Position lookup bug.** `/api/v1/stats/leaders` does NOT include `primaryPosition` — the original code's `person.primaryPosition.abbreviation` was always `None`, dropping all 366 merged players. Added `fetch_people()` that batch-calls `/api/v1/people?personIds=...` (cached per sorted-id-batch hash) to resolve positions.
2. **Catcher coverage.** Catchers rarely appear in offensive top-75, so the leader-only pool yielded 11 catchers vs the ~40–60 target. Added a roster-walk supplement: `fetch_teams()` + `fetch_team_roster()` + `collect_position_ids("C")` + `fetch_hitting_stats_batch()` (which uses `/api/v1/people?personIds=...&hydrate=stats(...)` — discovered the plain `/stats` endpoint silently ignores `personIds`).

Per-position counts after fix: **C=103, 1B=46, OF=71, P=194** (414 total). All positions meet or exceed target. 66/66 tests passing.

---

## MLB-8: Build the vector store, embeddings, and grading algorithm with unit tests

**Status:** Done — merged to `main` via branch `mlb-8-vector-store-grading`

Pure-function math layer, implemented and TDD'd before any agent work (per ticket guidance).

| Module | Contents |
|---|---|
| `backend/app/embeddings.py` | Lazy-loaded `sentence-transformers/all-MiniLM-L6-v2` wrapper (cached via `functools.cache`). `embed()` returns 384-dim L2-normalized vectors. `pick_text` / `adp_text` use the canonical text recipes from the `vector-store` skill. `PICK_STAT_KEYS` defines the fixed stat order so embeddings stay stable across runs. |
| `backend/app/strategies.py` | `StrategyTag` dataclass (stat, op, threshold) with `matches()` handling missing / None / non-numeric values; `Strategy` dataclass with `stat_clears_any_tag()`. `STRATEGIES` registers all 6 from CLAUDE.MD with explicit thresholds (e.g., Power Hitting: HR≥25 ∨ SLG≥0.500 ∨ RBI≥80; Ace Pitching: K≥150 ∨ ERA≤3.50 ∨ WHIP≤1.20). |
| `backend/app/vectors.py` | `write_pick_vector` / `write_adp_vector` emit one JSON file per record under `./memory/vectors/{picks,adp}/`. `load_*_vectors` with mtime-keyed in-process cache. `cosine_similarity` zero-norm-safe. `find_cohort_centroid` implements the cold-start fallback (use all vectors when <5 match strategy; only `None` when fully empty). |
| `backend/app/grading.py` | `tag_fit = hits / total`; `cohort_fit = (mean_cosine + 1) / 2`, excludes `current_draft_id` so a team isn't compared to its own picks; `alignment_score = round(100 * (0.5 * cohort + 0.5 * tag))`. Weights centralized as `TAG_WEIGHT` / `COHORT_WEIGHT`. |

**Tests:** 146/146 passing.

- `test_embeddings.py` (11) — recipe order, 384-dim, L2 norm ≈ 1, determinism, short-string handling. Uses real model with cached load.
- `test_strategies.py` (36) — op handling (>=, <=, !=), None/non-numeric/string-numeric coercion, all-tag scenarios, parametrized threshold verification per strategy.
- `test_vectors.py` (17) — cosine math (identical/opposite/orthogonal/scale-invariant/zero-norm), centroid mean + cold-start fallback, round-trip write/load, mtime cache hit and invalidation (with Windows ~16ms tolerance).
- `test_grading.py` (16) — tag_fit edges, cohort_fit with synthetic vectors (no model load), exclude-current-draft, formula verification, perfect-100, weighted-75 intermediate case.

---

## MLB-9: Build the agents (Researcher, Drafter, Grader) and the draft engine

**Status:** Done — merged to `main` via branch `mlb-9-agents-and-engine`

The brain of the application: 3 agents + snake-draft engine. LLM and web search fully mocked in tests.

| Component | Detail |
|---|---|
| `app/search.py` | `ddgs` wrapper with 24h file cache at `./memory/search_cache/<sha256(query)>.json` |
| `app/snapshots.py` | `write_snapshot` rewrites `./memory/drafts/<id>.json` with full draft + teams + picks |
| `app/events.py` | Append-only JSONL event log at `./memory/drafts/<id>.events.jsonl`; sequential string ids for SSE `Last-Event-ID` resumption |
| `app/agents/models.py` | Pydantic Structured Outputs: `Candidate`, `ResearchResult`, `DraftPick`, `GradeResult` (`Literal["A","B","C","D","F"]`) |
| `app/agents/tools.py` | `web_search` `@function_tool` exposed to the Researcher |
| `app/agents/researcher.py` | `gpt-4o-mini`, max_turns=6, tool=[web_search]; input includes strategy + roster needs + available pool + draft history |
| `app/agents/drafter.py` | max_turns=4, no tools; picks one candidate with 2-3 sentence rationale |
| `app/agents/grader.py` | max_turns=3, no tools; receives pre-computed alignment_score, produces letter per fixed 5-tier scale (90+=A, 75+=B, 55+=C, 35+=D, else F) |
| `app/engine.py` | `run_draft()` orchestration: snake-order picks with Researcher→Drafter→validation-retry, embed + write vectors, ADP records, snapshot rewrite, per-pick events; post-draft per-team grading with alignment_score (excludes current draft from cohort) |

**Key design decisions:**
- Pick validation: `player_id` not drafted AND `position` not already filled on team
- Drafter retry: drop rejected candidate, re-call (max 3 attempts); `DraftError` if exhausted
- Snake order: rounds 1/3/… forward, 2/4/… reversed
- Researcher tool list = `[web_search]` only (ADP lookup tool deferred — no ADP data on first draft)
- Engine emits these event types: `draft_started`, `pick_starting`, `research_complete`, `pick_completed`, `team_graded`, `draft_completed`

**Tests:** 174/174 passing in 12.24s.

- `test_search.py` (6), `test_snapshots.py` (6), `test_events.py` (8)
- `test_agents.py` (4) — mocks `agents.Runner.run` via `AsyncMock`, verifies input shape + final_output unwrap + max_turns
- `test_engine.py` (4) — end-to-end 2-team/2-round snake draft with mocked agents (real DB, real embed, real file I/O); retry-skip test; `DraftError` cases
