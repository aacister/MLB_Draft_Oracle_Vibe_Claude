---
name: local-only
description: Hard constraints for MLB Draft Oracle's local-only, zero-cloud architecture. Use when adding a new dependency, new persistence mechanism, new background worker, or any infrastructure-shaped task. Stop and verify against these constraints before proceeding.
---

# Local-Only Constraints: MLB Draft Oracle

This app runs **entirely on the developer's machine**. Before adding any dependency or mechanism, check it against this list.

## The Core Rule

**No cloud services for state or compute.** The only permitted external network calls are:

| Allowed call | Library | Notes |
|---|---|---|
| LLM reasoning | OpenAI API (`openai-agents`, `gpt-4o-mini`) | Only paid line item |
| Web search | `ddgs` (DuckDuckGo) | Free, no key, no card |
| MLB stats ingestion | `mlb-statsapi` (toddrob99) | Free, no key; ingest once at setup |

Everything else runs locally. If you find yourself reaching for a managed service, stop and ask.

## Persistence Rules

| Data type | Where it lives | NOT allowed |
|---|---|---|
| Relational truth | SQLite, `./data/mlbdraftoracle.db` | Postgres, MySQL, Redis, etc. |
| Draft snapshots | `./memory/drafts/<id>.json` | S3, GCS, any object store |
| Vector embeddings | `./memory/vectors/{picks,adp}/*.json` | Pinecone, Weaviate, Chroma, FAISS server |
| Agent scratch | `./memory/agents/<draft_id>/*.json` | Any cloud KV or blob store |
| Search cache | `./memory/search_cache/<sha256>.json` | Any external cache service |

All filesystem paths must go through the `paths` module. No hard-coded strings elsewhere.

## Embedding: Local Model Only

Use `sentence-transformers/all-MiniLM-L6-v2` on CPU. **Do not** use `text-embedding-3-small` or any OpenAI embedding endpoint — that is a paid per-vector API call.

## Vector Search: NumPy Only

Load vectors from JSON files and compute cosine similarity with NumPy. **Do not** introduce FAISS, Chroma, Qdrant, Weaviate, or any embedded/external vector server. At v1 scale (low thousands of vectors) NumPy in milliseconds is more than sufficient.

## Background Workers: asyncio Only

**Do not** introduce Celery, RQ, Dramatiq, or any external task queue. One Python process, `asyncio` only. Draft execution runs as `asyncio.create_task(...)` inside the FastAPI process.

## Database: No Alembic at v1

`Base.metadata.create_all(engine)` at boot. If migrations are needed later, add Alembic then — document the decision first in `docs/decisions.md`.

## Frontend Build: Vite Only

Vite + React 19 + Tailwind 4. **No** Next.js (no SSR, no server components needed — single-user local app with no SEO requirements).

## Streaming: SSE Only

Server-Sent Events for draft streaming. **No** WebSockets — there is no user input during a draft run. FastAPI `StreamingResponse` with `text/event-stream`.

## Cost Target: $0/month (except LLM tokens)

Every dependency must be free, locally-hosted, or already covered by OpenAI spend. If a new tool has a cloud pricing tier, check whether the free tier is sufficient and document it. Default: do not add paid dependencies.

## Checklist Before Adding Any New Dependency

1. Does it require a cloud account or credit card? → **Stop. Find a local alternative.**
2. Does it add a background server process (worker, DB daemon, cache server)? → **Stop. Use asyncio or file-based alternatives.**
3. Does it store state outside `./data/` or `./memory/`? → **Stop. Route through the `paths` module.**
4. Does it make network calls beyond the three allowed ones above? → **Stop. Get explicit approval first.**
