#!/usr/bin/env bash
# Pull the latest code from GitHub and rebuild. Data in the mit_data volume is kept.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/mit}"
BRANCH="${BRANCH:-main}"
cd "$APP_DIR"
git fetch --depth 1 origin "$BRANCH"
git reset --hard "origin/$BRANCH"
cd deploy
docker compose up -d --build
docker image prune -f >/dev/null
docker compose ps
