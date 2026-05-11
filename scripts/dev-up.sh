#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "→ .env created from .env.example — edit secrets before next boot."
fi

docker compose up -d --build
echo
echo "  Web:        http://localhost:8080"
echo "  QGIS:       http://localhost:8080/qgisserver"
echo "  Tiles:      http://localhost:8080/tiles"
echo "  whoami:     http://localhost:8080/whoami"
