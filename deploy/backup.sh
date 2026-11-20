#!/usr/bin/env bash
# Nightly DuckDB backup. DuckDB allows one writer, so the api pauses for a few
# seconds while the data volume is copied. Keeps the last 7 backups.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/mit}"
DEST="${BACKUP_DIR:-/var/backups/mit}"
mkdir -p "$DEST"
cd "$APP_DIR/deploy"
STAMP="$(date +%Y%m%d-%H%M%S)"
docker compose stop api
docker run --rm -v mit_mit_data:/data:ro -v "$DEST":/backup alpine \
  tar czf "/backup/mit-data-$STAMP.tgz" -C /data . || true
docker compose start api
ls -1t "$DEST"/mit-data-*.tgz | tail -n +8 | xargs -r rm -f
echo "backup ok: $DEST/mit-data-$STAMP.tgz"
