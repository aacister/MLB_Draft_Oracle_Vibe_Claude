# Design Decisions

The choices below are already made. Build to them. If one looks wrong as you implement, **stop and ask** before swapping it — do not silently deviate.

---

## Hard Constraints (non-negotiable)

1. **Backend language:** Python 3.12+.
2. **Backend framework:** FastAPI for all HTTP APIs.
3. **Database:** SQLite, one file on disk, no other engine.
4. **Frontend:** React with TailwindCSS.
5. **Runs entirely locally.** The only external network calls are the LLM provider, a web search provider, and the MLB stats data source.
6. **Non-relational memory** (snapshots, vector embeddings, agent scratch) lives as JSON files under `./memory/`.

---

## Design Decisions (cost target: $0/month except LLM tokens)

1. **Agent framework — OpenAI Agents SDK (`openai-agents`).** Maps cleanly to the Researcher / Drafter / Grader pattern with first-class tool calling.

2. **LLM for agent reasoning — `gpt-4o-mini`.** Used for all three agents; keep max-tokens conservative and constrain turns aggressively so a full draft stays well under $1.

3. **Embedding model — `sentence-transformers/all-MiniLM-L6-v2`, local on CPU.** Free 90 MB one-time download, 384-dim vectors. Do **not** use OpenAI's `text-embedding-3-small` — that is a paid per-vector API call.

4. **Web search — DuckDuckGo via the `ddgs` Python package.** No API key, no card. Cache results under `./memory/search_cache/` for ≥24 h. Fallback if it breaks: Tavily.

5. **MLB stats — `MLB-StatsAPI` (toddrob99).** Free, no key. Ingest the 2025 season once at setup, persist to SQLite, never call at runtime. Cache raw responses to `./memory/ingestion/`.

6. **Vector store — JSON files + NumPy cosine similarity.** Low-thousands of vectors at most; no FAISS, no Chroma, no embedded server. Cache loaded vectors keyed on file mtime.

7. **Streaming to the UI — Server-Sent Events (SSE).** One-way, plain HTTP, native `EventSource` in React. No WebSockets — there is no user input during a draft.

8. **Concurrency model — FastAPI background task per draft, SSE re-subscribes from persisted state.** `asyncio.create_task(...)` only. The engine writes every event to a per-draft event log so reconnects and reloads work. No Celery, no RQ, no external workers.

9. **Frontend build tool — Vite + React 19 + Tailwind 4.** SPA at `http://localhost:5173`. Icons via `lucide-react`, charts via `recharts`. No Next.js — no SEO or SSR need.

10. **Database & migrations — SQLite + SQLAlchemy 2.x with `Base.metadata.create_all` at boot.** No Alembic at v1. String UUIDs everywhere except `players.id` (use the natural MLB Stats API id).

---

## Environment Variables

Only these belong in `.env.example`:

```
OPENAI_API_KEY=           # required — only paid line item
TAVILY_API_KEY=           # optional fallback if DuckDuckGo fails
SEASON=2025
EMBEDDING_MODEL=all-MiniLM-L6-v2
AGENT_MODEL=gpt-4o-mini
```

No keys needed for embeddings, MLB stats, or DuckDuckGo.
