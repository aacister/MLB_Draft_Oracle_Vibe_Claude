# MLB Draft Oracle

Autonomous AI draft simulator for fantasy baseball. Two AI-powered teams with distinct strategies (Power Hitting vs Speed & Defense, etc.) draft against each other, with full rationales for every pick.

## Stack

- **Backend**: Python 3.12+, FastAPI, SQLite, OpenAI Agents SDK (`gpt-4o-mini`)
- **Frontend**: React 19, Vite, Tailwind 4
- **Embedding**: `sentence-transformers/all-MiniLM-L6-v2` (local CPU)
- **Search**: DuckDuckGo via `ddgs`
- **Stats**: `MLB-StatsAPI`

See [docs/decisions.md](docs/decisions.md) for the rationale behind each choice.

## Quick Start (Docker — recommended)

The whole stack runs in one container.

```bash
cp .env.example .env                # add your OPENAI_API_KEY

# macOS
scripts/start-mac.sh                # builds image on first run; http://localhost:8000
scripts/stop-mac.sh

# Linux
scripts/start-linux.sh
scripts/stop-linux.sh

# Windows
scripts\start-windows.ps1
scripts\stop-windows.ps1
```

The frontend is built as static assets and served by FastAPI on the same port,
so `http://localhost:8000` serves both the SPA and the `/v1/*` API.

## Quick Start (local dev, no Docker)

```bash
# from project root:
cp .env.example .env                           # add your OPENAI_API_KEY
mkdir -p data memory/{drafts,vectors/picks,vectors/adp,agents,search_cache,ingestion}

# backend: setup, ingest the 2025 pool, then serve
cd backend
uv sync
uv run python -m app.ingest                    # populates 2025 player pool (once)
uv run uvicorn app.main:app --reload --port 8000   # http://localhost:8000

# frontend (in a separate terminal, from project root)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## MCP Servers (Claude Code)

Three project-scoped MCPs are declared in `.mcp.json`. To register them:

```bash
claude mcp add filesystem npx -y @modelcontextprotocol/server-filesystem ./
claude mcp add sqlite uvx mcp-server-sqlite --db-path ./data/mlbdraftoracle.db
claude mcp add github npx -y @modelcontextprotocol/server-github
```

## Layout

```
backend/                FastAPI app, agents, repositories, embeddings
frontend/               React 19 + Vite + Tailwind 4 SPA
scripts/                start/stop scripts (per OS)
data/                   SQLite database file (gitignored, volume-mounted by compose)
memory/                 JSON snapshots, vector embeddings (gitignored, volume-mounted)
docs/                   decisions.md, feature_insturctions.md
.claude/skills/         custom Claude Code skills
Dockerfile              multi-stage: builds frontend then bakes it into the backend image
docker-compose.yml      mounts data/ and memory/ for persistence across restarts
```

## Testing

```bash
# backend
cd backend && uv run pytest

# frontend
cd frontend && npm test
```

## License

See [LICENSE](LICENSE).
