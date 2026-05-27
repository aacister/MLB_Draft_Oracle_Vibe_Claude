# Start MLB Draft Oracle (Windows). Builds the image on first run.
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".env")) {
    Write-Error "ERROR: .env not found. Run: cp .env.example .env  and add OPENAI_API_KEY"
    exit 1
}

docker compose up -d --build
Write-Output "MLB Draft Oracle is starting at http://localhost:8000"
