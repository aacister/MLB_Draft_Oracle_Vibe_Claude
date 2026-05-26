# MLB Draft Oracle

Autonomous AI draft simulator for fantasy baseball. Two AI-powered teams with distinct strategies (Power Hitting vs Speed & Defense, etc.) draft against each other, with full rationales for every pick.

## Stack

- **Backend**: Python 3.12+, FastAPI, SQLite, OpenAI Agents SDK (`gpt-4o-mini`)
- **Frontend**: React 19, Vite, Tailwind 4
- **Embedding**: `sentence-transformers/all-MiniLM-L6-v2` (local CPU)
- **Search**: DuckDuckGo via `ddgs`
- **Stats**: `MLB-StatsAPI`

See [docs/decisions.md](docs/decisions.md) for the rationale behind each choice.

## Quick Start

```bash
# clone, then:
uv sync                                        # install backend deps
cp .env.example .env                           # add your OPENAI_API_KEY
mkdir -p data memory/{drafts,vectors/picks,vectors/adp,agents,search_cache,ingestion}

# ingest the 2025 player pool (once)
uv run python -m backend.app.ingest

# backend → http://localhost:8000
uv run uvicorn backend.app.main:app --reload --port 8000

# frontend → http://localhost:5173 (in another terminal)
cd frontend && npm install && npm run dev
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
data/                   SQLite database file (gitignored)
memory/                 JSON snapshots, vector embeddings (gitignored)
docs/                   decisions.md, feature_insturctions.md
.claude/skills/         custom Claude Code skills
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
