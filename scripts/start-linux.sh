#!/usr/bin/env bash
# Start MLB Draft Oracle (Linux). Builds the image on first run.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run: cp .env.example .env  and add OPENAI_API_KEY"
  exit 1
fi

docker compose up -d --build
echo "MLB Draft Oracle is starting at http://localhost:8000"
