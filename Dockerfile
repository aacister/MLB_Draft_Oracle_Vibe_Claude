# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the React frontend ----
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Install deps first for caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Then source + build
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend with static frontend ----
FROM python:3.12-slim AS runtime
WORKDIR /app

# uv for dependency resolution
RUN pip install --no-cache-dir uv==0.5.*

# Install backend deps with lockfile (cached unless pyproject/uv.lock change)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Backend source
COPY backend/app ./app

# Built frontend assets — main.py looks for $FRONTEND_DIST
COPY --from=frontend-builder /build/dist /frontend-dist
ENV FRONTEND_DIST=/frontend-dist

# Runtime directories (CLAUDE.MD §Persistence)
RUN mkdir -p /app/data \
    /app/memory/drafts \
    /app/memory/vectors/picks \
    /app/memory/vectors/adp \
    /app/memory/agents \
    /app/memory/search_cache \
    /app/memory/ingestion

# Entrypoint: re-ingest (cache makes this nearly free on subsequent runs)
# then serve. The DB is recreated by Base.metadata.create_all at boot.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "uv run python -m app.ingest --season 2025 && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
