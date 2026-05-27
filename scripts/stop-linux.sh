#!/usr/bin/env bash
# Stop MLB Draft Oracle (Linux).
set -euo pipefail

cd "$(dirname "$0")/.."
docker compose down
