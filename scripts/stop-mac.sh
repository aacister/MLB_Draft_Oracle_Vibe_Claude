#!/usr/bin/env bash
# Stop MLB Draft Oracle (macOS).
set -euo pipefail

cd "$(dirname "$0")/.."
docker compose down
