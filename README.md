# MLB Draft Oracle

An autonomous AI fantasy baseball draft simulator. Two AI-powered teams, each assigned a distinct strategy (Power Hitting vs. Speed & Defense, Ace Pitching vs. Closer-Heavy, etc.), draft against each other and produce written rationales for every pick. A deterministic 0–100 alignment score plus an LLM-narrated letter grade evaluate how well each team executed its strategy.

## Stack

Backend: Python 3.12+, FastAPI, SQLite (SQLAlchemy 2.x), OpenAI Agents SDK (`gpt-4o-mini`), `sentence-transformers/all-MiniLM-L6-v2` for local embeddings, `ddgs` for web search, `mlb-statsapi` for the 2025 player pool.

Frontend: React 19, Vite 6, Tailwind 4, react-router 7, recharts, lucide-react.

Packaging: One Docker container serves both the FastAPI API and the statically built React SPA on port 8000.

## Screenshots

### Jira board

The full 12-ticket roadmap delivered through the Atlassian MCP server.

![Jira board](docs/images/jira-board.png)

### Draft Room

Two team panels fed live by Server-Sent Events while the AI engine drafts. The center column is the streaming pick feed; the right side shows remaining available players filtered by position.

![Draft Room](docs/images/draft-room.png)

### Grade

Each team's deterministic alignment score, narrated letter grade, and rationale, with a recharts bar chart comparing the two.

![Grade](docs/images/grade-page.png)

## How this was built with Claude Code

The project was developed end-to-end inside Claude Code, with MCP servers handling the workflow:

- **Atlassian MCP** read the ticket spec for each MLB-N issue from `https://aacister.atlassian.net`, then transitioned the issue to Done once the corresponding PR merged.
- **GitHub MCP** (with local `git` as fallback when the MCP session was unavailable) created branches, opened pull requests, and merged to `main`.
- **Filesystem MCP** edited project files inside the repo.
- **SQLite MCP** queried `./data/mlbdraftoracle.db` during development.

Per ticket, Claude Code followed a fixed feature-dev process:

1. Read the Jira ticket via the Atlassian MCP.
2. Plan, then implement on a feature branch (`mlb-<N>-<slug>`).
3. Run the full test suite (`uv run pytest` and `npm test`).
4. Open a PR via the GitHub MCP and merge to `main` once green.
5. Append the completed work and design notes to `docs/feature_insturctions.md`.
6. Transition the Jira ticket to Done.

### Decision process

For each ticket Claude Code went through the same sequence:

1. **Discovery.** Read the Jira spec plus `CLAUDE.md`, the custom skills, and `docs/decisions.md` to understand constraints.
2. **Codebase exploration.** Inspect existing modules and patterns; in larger tickets, launch `code-explorer` sub-agents in parallel for different aspects.
3. **Clarifying questions.** Surface ambiguities and ask the operator before designing — for example, the strategy threshold values, the catcher-supplement approach, the engine fallback behavior on hallucinated player IDs.
4. **Architecture.** Sketch one or more approaches, name trade-offs, pick the simplest viable one consistent with `docs/decisions.md`.
5. **Implementation.** Small, incremental commits; tests written alongside or first when the ticket called for TDD.
6. **Quality review.** Run the test suite end-to-end; for non-trivial changes, audit the diff before push.
7. **Summary.** Record what was built, why, and any deferred follow-ups in `docs/feature_insturctions.md`.

## Feature timeline

Each row corresponds to one Jira issue and one merged PR. See `docs/feature_insturctions.md` for full per-ticket detail.

| Ticket | Outcome |
|---|---|
| MLB-1  | Read `CLAUDE.md`; established project understanding |
| MLB-2  | Verified required MCP servers (atlassian, github, brave-search, ide) |
| MLB-3  | Scaffolded five custom Claude Code skills in `.claude/skills/` |
| MLB-4  | Wrote `docs/decisions.md` — single-page summary of all design choices |
| MLB-5  | Project scaffold: `pyproject.toml`, `package.json`, `.env.example`, `.mcp.json` |
| MLB-6  | SQLite layer: SQLAlchemy models + function-style repositories + 19 tests |
| MLB-7  | 2025 player-pool ingestion via `mlb-statsapi` with file-based response cache; 414 players ingested across C/1B/OF/P |
| MLB-8  | Vector store (JSON + NumPy cosine), embeddings, deterministic grading algorithm; 146 tests |
| MLB-9  | Researcher, Drafter, Grader agents + snake-draft engine + SSE event log; 174 tests |
| MLB-10 | FastAPI app with all `/v1` endpoints and the SSE streaming endpoint; 217 tests |
| MLB-11 | React 19 frontend: Home, Draft Room, Grade, Leaderboard, ADP Trends |
| MLB-12 | Canonical end-to-end test exercising the full HTTP-to-engine-to-disk flow |
| Follow-up | Docker packaging: multi-stage build, single-container deployment, OS-specific start/stop scripts |

Several live-test bugs were also fixed in follow-up branches: position lookup gap in `mlb-statsapi`, catcher coverage supplement, Researcher max-turns budget, frontend SSE gating, ADP Trends tab type confusion, and Drafter/Researcher player-ID hallucination filtering.

## Run it

Prerequisites: Docker Desktop, an OpenAI API key.

```bash
git clone https://github.com/aacister/MLB_Draft_Oracle_Vibe_Claude.git
cd MLB_Draft_Oracle_Vibe_Claude
cp .env.example .env                # add OPENAI_API_KEY
scripts/start-windows.ps1           # or scripts/start-mac.sh / start-linux.sh
```

The container builds on first run (a few minutes), ingests the 2025 player pool (cached after the first run), and serves the full app at:

**http://localhost:8000**

Stop with `scripts/stop-windows.ps1` (or the OS equivalent).

To run the suite locally without Docker, see the per-stack quick-starts in `docs/decisions.md`.

## License

See `LICENSE`.
