# MLB Draft Oracle Project

## VERY IMPORTANT
-Be simple.  Approach tasks in a simple, incremental way.
-Mark incrementally ALWAYS. Small, simple steps.  Validate and check each increment before moving on.
- Use LATEST apis as of NOW

## MANDATORY Code Style
- Do not overengineer.  Do not program defensively.  Use exception managers only when needed.
- Identify root cause before fixing issues.  Prove with evidence, then fix.
- Work incrementally with small steps.  Validate each increment.
- Use latest library APIs.
- Use 'uv' as Python package manager.  Always 'uv run xxx' never 'python3 xxx', always 'uv add xxx' never 'pip install xxx'
- Favor clear, concise docstring comments.  Be sparing with comments outside docstrings.
- Favor short modules, short methods and functions.  Name things clearly.
- Never use emojis in code or in print statements or logging
- Keep README.md concise.

## Important - debugging and fixing
- When troubleshooting problems, ALWAYS identify root cause BEFORE fixing.
- Reproduce consistently.
- PROVE THE PROBLEM FIRST - don't guess.
- Try on test at a time.  Be methodical.
- Don't jump to conclusions.  Don't apply workarounds.


## Overview

MLB Draft Oracle is an autonomous AI draft simulator that pits AI-powered teams against each other in a fantasy baseball draft. Each team is assigned a unique strategy (e.g., "Power Hitting" vs "Speed & Defense") and uses intelligent agents to research players, analyze statistics, and make strategic picks — complete with detailed rationales for every selection.

This is a SaaS product to allow users to draft legal agreements based on templates in the templates directory.
The user can carry out AI chat in order to establish what document they want and how to fill in the fields.
The available documents are covered in the catalog.json file in the project root, included here:

@catalog.json

The current implementation supports all 11 document types via AI chat with full user authentication and document persistence.

## Development process

When instructed to build a feature:
1. Use your Atlassian tools to read the feature instructions from Jira
2. Develop the feature - do not skip any step from the feature-dev 7 step process
3. Thoroughly test the feature with unit tests and integration tests and fix any issues
4. Submit a PR using your github tools
5. Record Jira feature instructions in docs/feature_insturctions.md on completion of github PR merge. Additionally, add concise details on what has been implemented for that feature instruction.  This will provide a dynamic list of completed features with implementation details.
6. Change anything that is no longer accurate in CLAUDE.MD

## AI design

When writing code to make calls to LLMs, use the OpenAI Agent SDK utilizing the `GPT-4o-mini` model. You should use Structured Outputs so that you can interpret the results and populate fields for the database, or in code.

There is an OPENAI_API_KEY in the .env file in the project root.

## Technical design

The entire project should be packaged into a Docker container.  
The backend should be in backend/ and be a uv project, using FastAPI.  
The frontend should be in frontend/  
The database should use SQLLite and be created from scratch each time the Docker container is brought up.  
Consider statically building the frontend and serving it via FastAPI, if that will work.  

There should be scripts in scripts/ for:  
```bash
# Mac
scripts/start-mac.sh    # Start
scripts/stop-mac.sh     # Stop

# Linux
scripts/start-linux.sh
scripts/stop-linux.sh

# Windows
scripts/start-windows.ps1
scripts/stop-windows.ps1
```
Backend available at http://localhost:8000

## Hard Constraints
 
These are the only non-negotiables. Everything else is your call.
 
- **Backend language:** Python (3.12+).
- **Backend framework:** FastAPI for any HTTP API.
- **Database:** SQLite. One file, on disk. No other database engine.
- **Frontend:** React with TailwindCSS.
- **Runs entirely locally.** No cloud services for state or compute. The only external network calls are:
  - the LLM provider
  - a web search provider
  - the MLB stats data source 
- **Any persisted "memory" that isn't relational** (snapshots, vector embeddings, agent scratch) lives as JSON files under a top-level `./memory/` directory.
 
---
 
## Design Decisions (Recommended Defaults)
 
These decisions are made already. Record them in `docs/decisions.md` so contributors can find the rationale, and only revisit one of them if you hit a wall — in which case stop and ask. The shape of the app assumes these choices.
 
**The cost target is $0/month.** Every recommendation below is either free, locally hosted, or already covered by the OpenAI spend that GPT-4o-mini introduces. The only paid line item is GPT-4o-mini token usage, which is the agent reasoning budget you've already accepted.
 
### 1. Agent framework → **OpenAI Agents SDK** (`openai-agents`)
 
Decided. It maps cleanly to the Researcher / Drafter / Grader pattern, has first-class tool calling, and works with `gpt-4o-mini` out of the box.
 
### 2. LLM for agent reasoning → **`gpt-4o-mini`**
 
Decided. Use it for all three agents. Set max-tokens conservatively and constrain turns aggressively (see §5.4) so a full draft stays well under a dollar in tokens.
 
### 3. Embedding model → **`sentence-transformers/all-MiniLM-L6-v2`, local, on CPU**
 
Free, ~90 MB one-time download from Hugging Face, runs on CPU, produces 384-dim vectors. Plenty for the cohort-similarity and ADP-trend work this app does. **Do not** use OpenAI's `text-embedding-3-small` — that's a paid API call per vector, and you'll be writing dozens of vectors per draft.
 
```python
# install
uv add sentence-transformers
# usage
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")
embedding = _model.encode(text, normalize_embeddings=True).tolist()
```
 
Cache the loaded model at module import so you pay the load cost once per process.
 
### 4. Web search → **DuckDuckGo via the `ddgs` Python package** (no API key, no card)
 
The Brave Search free tier was removed in February 2026; new users get $5/month credit (~1,000 queries) with a credit card on file. `ddgs` (the maintained successor to `duckduckgo-search`) is genuinely free, no key, no signup. Expose it to the Researcher as a single tool function:
 
```python
# install
uv add ddgs
# usage
from ddgs import DDGS
results = DDGS().text(query, max_results=5, region="us-en")
```
 
Cache results in `./memory/search_cache/<sha256(query)>.json` for at least 24 hours so repeated drafts don't re-hit DuckDuckGo for the same player names. DuckDuckGo will rate-limit aggressively if you don't.
 
**Fallback plan** if `ddgs` starts failing locally (the Cloudflare TLS handshake changes once or twice a year): switch to **Tavily** (1,000 free searches/month with key, no card required) by swapping the implementation behind the Researcher's `web_search(query)` tool. The tool surface stays identical.
 
### 5. MLB stats → **`MLB-StatsAPI`** by toddrob99 (no API key)
 
Wraps the same public `statsapi.mlb.com` endpoints MLB.com itself uses. Free, no key, well-maintained. Ingest the 2025 season once at setup via leader-board endpoints, persist to SQLite, and never call it again at runtime. Cache the raw responses to `./memory/ingestion/<endpoint>.json` so you can re-seed a clean DB without re-hitting the API.
 
```python
# install
uv add mlb-statsapi
# usage
import statsapi
leaders = statsapi.league_leader_data("homeRuns", season=2025, limit=75)
```
 
### 6. Vector store → **roll your own, JSON files + NumPy cosine similarity**
 
At v1 scale (≈ 8 pick vectors per draft, plus 8 ADP vectors, times however many drafts you ever run) you'll be in the low thousands of vectors at most. Loading them all from `./memory/vectors/{picks,adp}/*.json` and computing cosine similarity with NumPy fits in milliseconds. No FAISS, no Chroma, no embedded server — those are dependency weight you don't need.
 
Keep one in-process cache keyed on file mtime so repeated grade lookups don't re-read disk.
 
### 7. Streaming to the UI → **Server-Sent Events (SSE)**
 
One-way (server → browser), works over plain HTTP, no extra dependencies, native `EventSource` support in React. WebSockets would be overkill for this app — there's no user input during a draft. FastAPI handles SSE with a streaming `Response` returning `text/event-stream`.
 
### 8. Concurrency model → **FastAPI background task per draft, SSE re-subscribes from persisted state**
 
When `POST /v1/drafts/{id}/run` lands, kick off the engine as an `asyncio.create_task(...)`. The engine writes every event to a per-draft event log (a `draft_events` table or an append-only JSONL at `./memory/drafts/<id>.events.jsonl` — pick one, document it). The SSE endpoint reads from that log starting at the last event id the client supplies via `Last-Event-ID`, then tails. This way reconnects, restarts, and "open the draft room hours later" all just work.
 
Do **not** introduce Celery, RQ, or any external worker. One Python process, asyncio only.
 
### 9. Frontend build tool → **Vite + React 19 + Tailwind 4**
 
Single-page app, runs at `http://localhost:5173`. No Next.js — the app has no SEO needs and no server components. Use `@tailwindcss/vite`. Icons via `lucide-react`. Charts via `recharts`.
 
### 10. Database & migrations → **SQLite + SQLAlchemy 2.x, `Base.metadata.create_all` at boot**
 
No Alembic at v1. If you later need migrations, add them then. Use string UUIDs for everything except `players.id` (use the natural MLB Stats API id).
 
---
 
### Quick env var summary
 
The `.env.example` should list exactly these:
 
```
# required — only paid line item
OPENAI_API_KEY=
 
# optional fallback if DuckDuckGo starts failing
TAVILY_API_KEY=
 
# tunables (all have sane defaults in code)
SEASON=2025
EMBEDDING_MODEL=all-MiniLM-L6-v2
AGENT_MODEL=gpt-4o-mini
```
 
No keys needed for embeddings, MLB stats, or DuckDuckGo.
 
---
 
## Required MCP Servers and Skills (for Claude Code itself)
 
These exist so Claude Code can work effectively in this repo. They are **not** part of the application.
 
### Project-scoped MCPs (commit `.mcp.json`)
 
| Server | Purpose |
|---|---|
| **filesystem** (`@modelcontextprotocol/server-filesystem`, scoped to the repo root) | Edit files, inspect `./data` and `./memory` |
| **sqlite** (`mcp-server-sqlite` against `./data/mlbdraftoracle.db`) | Query the dev database without leaving Claude Code |
| **github** | Commits, PRs, issues |
 
Document the exact `claude mcp add ...` invocations in the README so a new contributor can replicate the setup.
 
### Built-in skills to lean on
 
- **skill-creator** — author the custom skills below
- **frontend-design** — any time the React/Tailwind UI is touched
- **file-reading** — for any uploaded fixtures or sample data
- **product-self-knowledge** — for "which model / which API tier should I use" questions
### Custom skills to author with skill-creator (place in `.claude/skills/`)
 
1. **`domain-vocab`** — fantasy-baseball + draft vocabulary (snake order, position quotas, strategy names, fantasy stat categories). Triggers on any work involving teams, picks, strategies, or agent prompts.
2. **`sqlite-conventions`** — table naming, ID format (UUID v4 strings, lowercased), JSON-column patterns for flexible blobs, migration approach. Triggers when adding tables or repository code.
3. **`agent-prompts`** — house style for Researcher / Drafter / Grader prompts: required tool-call discipline, max-turn limits, how rationales are formatted. Triggers when editing prompt templates or agent definitions.
4. **`vector-store`** — embedding-text recipe, metadata shape, cosine-search interface. Triggers when working on grading, ADP analysis, or anything under the vector-store module.
5. **`local-only`** — reminders about the "runs locally, SQLite-only, JSON-on-disk for memory" constraints. Triggers on infra-shaped tasks (new dependency, new persistence layer, new background mechanism) so you stop and reconsider before reaching for cloud services.
### Plugins
 
None required.
 
---
 
## Functional Requirements
 
These are what the app must do. *How* is up to you.
 
### 1. Player pool
 
- Ingest the **2025 MLB season**. At least ~40–60 players per position (C, 1B, OF, P) covering league leaders across the major fantasy-relevant categories.
- Each player has: id, name, MLB team, position (one of C / 1B / OF / P — collapse outfield variants into `OF`), and a stats blob covering at minimum: HR, RBI, R, SB, AVG, OBP, SLG, K, W, S, ERA, WHIP, innings pitched, at-bats.
- The pool is ingested **once** at setup. A dev-only re-ingest endpoint or CLI command is fine.
### 2. Strategies
 
- Ship at least these named strategies, each with a one-paragraph description and a short tag list used for grading:
  - **Power Hitting** — HR, SLG, RBI
  - **Speed & Defense** — SB, R, AVG
  - **Balanced** — AVG, OBP, mixed
  - **Ace Pitching** — K, ERA, WHIP
  - **Closer-Heavy** — S, ERA
  - **Contrarian Value** — OBP, late-round
- A draft picks two **distinct** strategies, one per team.
### 3. Draft creation and execution
 
- The user creates a draft by choosing two strategies (or accepting random ones) and an optional round count (default 4).
- The backend generates a witty draft name and two team names.
- Clicking **Start Draft** runs the draft to completion. As each pick happens the UI receives, in order: a "pick starting" event, a "research complete" event (with the Researcher's candidate list), a "pick completed" event (with the chosen player and rationale).
- Each pick is persisted immediately so the draft can be reloaded mid-flight.
- A draft snapshot is also written to `./memory/drafts/<draft_id>.json` after every pick (this is the file the Grader and future Researcher runs read from).
### 4. Agents
 
- **Researcher.** Given strategy + remaining roster needs + available player pool, recommends 3–5 still-available candidates with citations from live web search and the historical draft vector store. Returns a ranked list.
- **Drafter.** Reads the Researcher's recommendations, picks one that fills an empty roster slot, and commits the pick with a 2–3 sentence rationale. Retries with the next candidate on validation failure (position already filled, player already drafted) up to a small bounded number of attempts.
- **Grader** (post-draft only). Given the deterministic score and the comparable picks, produces a letter (A/B/C/D/F) and a 2–3 sentence rationale. Never re-computes the score; only narrates.
All agents are constrained by max-turn limits. None should be able to spin in tool calls forever.
 
### 5. Grading
 
Two phases, in this order:
 
**Phase 1 — deterministic 0–100 `alignment_score`:**
 
1. Embed each of the team's 4 picks (using your chosen embedding model and the embedding-text recipe from your `vector-store` skill).
2. Pull the cohort of all picks tagged with the same strategy **from other drafts**. If fewer than 5 exist, fall back to the centroid of all picks (cold-start case).
3. `cohort_fit` = mean cosine similarity of the team's pick embeddings to the cohort centroid, mapped to [0, 1].
4. `tag_fit` = fraction of the 4 picks whose stats clear the strategy's tag thresholds (e.g., Power Hitting → `HR ≥ 25` is a hit). Define thresholds explicitly in the strategy config.
5. `alignment_score = round(100 * (0.5 * cohort_fit + 0.5 * tag_fit))`. Weights are tunable; keep them in one place.
**Phase 2 — letter + rationale via the Grader agent**, as described in 5.4.
 
Both phases write to a `grades` table. The historical leaderboard is `AVG(alignment_score) GROUP BY strategy_name`.
 
### 6. ADP Trend Analysis
 
- Every pick produces an ADP record (player_id, pick_number, season, draft_id) **and** an ADP vector document indexed by player.
- Expose endpoints (or tabs in the UI) for:
  - **Overdrafted players** — players with the largest gap between mean pick number and their performance rank, for players with ≥3 appearances.
  - **Ignored positions** — positions whose mean pick number sits above the global median.
  - **Season shift** — sliding-window mean pick over draft-creation order; surfaces rising/falling values.
- The Researcher gets an ADP lookup tool so it can pursue value picks across drafts.
### 7. Frontend
 
Tailwind only — no component library. Use a small icon library and a small chart library; both are your call.
 
Pages / views:
 
- **Home** — list of past drafts, "Start New Draft" form.
- **Draft Room** — two team panels with live rosters, a center "pick feed" of streaming rationales, an available-players board on the side. Updates in real time as the backend streams events.
- **Grade** — appears after a draft completes: per-team grade card (score, letter, rationale) plus a small chart visualizing each pick's similarity to the strategy cohort.
- **Leaderboard** — historical strategy execution table.
- **ADP Trends** — charts and a "value picks" table backed by 5.6.
The UI should be readable on a laptop, no responsive-mobile polish required for v1.
 
---
 
## Persistence
 
### SQLite (relational truth)
 
At minimum, you'll need tables for: drafts, teams, players, picks, grades, ADP records. Use string UUID PKs for everything except players (use the natural ID from the stats source). Use JSON columns for anything genuinely shape-variable (e.g., per-player stats, league config) instead of inventing a sub-table. Add the indexes the queries in §5 actually need.
 
Migrations: Alembic is fine, but a single boot-time `Base.metadata.create_all` is acceptable for v1. Pick one and document it.
 
### JSON on disk (everything else)
 
```
./memory/
├── drafts/<draft_id>.json        snapshot rewritten after every pick
├── vectors/picks/<id>.json       1 file per embedded pick
├── vectors/adp/<id>.json         1 file per ADP datapoint
└── agents/<draft_id>/*.json      optional agent scratch
```
 
Pick-vector files must contain at least: id, kind, draft_id, team_id, strategy, round, pick_number, player_id, player_name, position, rationale, stats_snapshot, embedding, indexed_at.
 
ADP-vector files must contain at least: id, kind, draft_id, player_id, player_name, position, pick_number, season, embedding, indexed_at.
 
Path resolution must go through a single `paths` module — no hard-coded paths anywhere else.
 
---
 
## API Surface (minimum)
 
All under `/v1`:
 
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/drafts` | Create a draft (choose 2 strategies, optional `num_rounds`) |
| `GET` | `/drafts` | List drafts |
| `GET` | `/drafts/{id}` | Full draft snapshot incl. teams, picks, grades |
| `GET` | `/drafts/{id}/stream` | Live stream of draft events |
| `POST` | `/drafts/{id}/run` | Start (or resume) the engine for this draft; idempotent |
| `GET` | `/players` | Search/filter the player pool |
| `GET` | `/drafts/{id}/grade` | Grades for both teams |
| `GET` | `/leaderboard` | Historical leaderboard, optional `?strategy=` |
| `GET` | `/adp/trends` | ADP analysis with a `view` query param |
| `POST` | `/admin/ingest` | Dev-only: refresh the 2025 player pool |
 
CORS allow `http://localhost:5173` (or wherever your dev frontend lives). No auth — single-user local app.
 
---
 
## Coding Conventions
 
- `from __future__ import annotations` at the top of every Python module.
- Full type hints. Pydantic v2 for any DTO that crosses an HTTP, agent, or persistence boundary.
- Async by default for I/O; SQLAlchemy syncs can sit inside `run_in_threadpool` — fine for SQLite.
- Logging via stdlib `logging`. Consistent format. No `print` for app logging.
- If you build local MCP servers for the agents, **log only to stderr** (stdout is the JSON-RPC channel).
- All filesystem paths go through one `paths` module.
- Python lint/format: `ruff`. Frontend lint/format: `eslint` + `prettier`. Configs committed.
- Tests: `pytest` + `httpx.AsyncClient` for the backend, `vitest` + React Testing Library for the frontend.
- At least one **end-to-end test** that runs a 2-team / 2-round draft with web search and the LLM mocked, asserts both grade rows exist, and asserts the expected count of pick vectors landed on disk.
---
 
## Project Setup Requirements
 
Whatever layout you choose, the README must let a fresh developer do this in under five minutes:
 
```bash
# clone, then:
uv sync                                  # or your chosen Python manager
cp .env.example .env                     # they fill in keys
mkdir -p data memory/{drafts,vectors/picks,vectors/adp,agents}
uv run python -m <your_ingest_module>    # populate 2025 player pool
 
# backend
uv run uvicorn <app_path>:app --reload --port 8000
 
# frontend
cd frontend && npm install && npm run dev
```
 
The `.env.example` must list every variable the app reads, with a comment on each.
 
---
 

 

## Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)
- Dark Navy: `#032147` (headings)
- Gray Text: `#888888`