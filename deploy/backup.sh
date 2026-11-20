#!/usr/bin/env bash
# Nightly backup of the data folder (DuckDB + settings). DuckDB allows one
# writer, so the API pauses for a few seconds while it is copied. Keeps 7.
set -euo pipefail
DATA_DIR="${DATA_DIR:-/var/lib/mit}"
DEST="${BACKUP_DIR:-/var/backups/mit}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
systemctl stop mit-api
tar czf "$DEST/mit-data-$STAMP.tgz" -C "$DATA_DIR" . || true
systemctl start mit-api
ls -1t "$DEST"/mit-data-*.tgz | tail -n +8 | xargs -r rm -f
echo "backup ok: $DEST/mit-data-$STAMP.tgz"
