#!/usr/bin/env bash
# Pull the latest code from GitHub, rebuild and restart. Data in /var/lib/mit is kept.
#   sudo /opt/mit/deploy/update.sh
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/mit}"
BRANCH="${BRANCH:-main}"
if [ "$(id -u)" -ne 0 ]; then echo "Please run with sudo."; exit 1; fi
DOMAIN="$(grep '^DOMAIN=' /etc/mit/mit.env | cut -d= -f2)"

git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
git -C "$APP_DIR" reset --hard "origin/$BRANCH"
chown -R mit:mit "$APP_DIR"
sudo -u mit bash -c "cd $APP_DIR && .venv/bin/pip install -q -r requirements.txt"
sudo -u mit bash -c "cd $APP_DIR/web && npm ci --no-audit --no-fund && \
  NEXT_PUBLIC_STATIC_DATA=0 NEXT_TELEMETRY_DISABLED=1 API_PROXY_TARGET=http://127.0.0.1:8000 \
  NEXT_PUBLIC_SITE_URL=https://$DOMAIN npm run build"
install -m 644 "$APP_DIR/deploy/mit-api.service" /etc/systemd/system/mit-api.service
install -m 644 "$APP_DIR/deploy/mit-web.service" /etc/systemd/system/mit-web.service
systemctl daemon-reload
systemctl restart mit-api mit-web
sleep 3
systemctl --no-pager --lines=0 status mit-api mit-web caddy | grep -E "●|Active:"
echo "Updated to $(git -C "$APP_DIR" log -1 --format='%h %s')"
