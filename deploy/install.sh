#!/usr/bin/env bash
# One-command setup for an Oracle Cloud Always Free Ubuntu 22.04/24.04 VM (ARM or x86).
# No Docker: the API and the website run as systemd services, Caddy serves HTTPS.
#
# Run on the server:
#   curl -fsSL https://raw.githubusercontent.com/subham1902/Marketing-Intelligence-Tracker/main/deploy/install.sh | sudo bash
#
# Re-running is safe: it updates the code, rebuilds and restarts.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/subham1902/Marketing-Intelligence-Tracker.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/mit}"
DATA_DIR="${DATA_DIR:-/var/lib/mit}"
ENV_FILE="/etc/mit/mit.env"
APP_USER="mit"

if [ "$(id -u)" -ne 0 ]; then echo "Please run with sudo."; exit 1; fi
. /etc/os-release
echo "==> OS: $PRETTY_NAME ($(uname -m))"
export DEBIAN_FRONTEND=noninteractive

echo "==> 1/8 System packages"
apt-get update -y
apt-get install -y ca-certificates curl git gnupg build-essential \
  python3 python3-venv python3-dev iptables-persistent netfilter-persistent \
  debian-keyring debian-archive-keyring apt-transport-https openssl

echo "==> 2/8 Node.js 20"
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "==> 3/8 Caddy (automatic HTTPS)"
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

echo "==> 4/8 Firewall: open 80/443 (Oracle images block them by default) and add swap"
for p in 80 443; do
  iptables -C INPUT -p tcp --dport "$p" -m state --state NEW -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 6 -p tcp --dport "$p" -m state --state NEW -j ACCEPT
done
iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p udp --dport 443 -j ACCEPT
netfilter-persistent save
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 5/8 App user, code and settings"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH" && git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
mkdir -p "$DATA_DIR" /etc/mit
if [ ! -f "$ENV_FILE" ]; then
  DOMAIN="${DOMAIN:-}"; ACME_EMAIL="${ACME_EMAIL:-}"
  [ -z "$DOMAIN" ] && read -rp "Your domain (e.g. example.com, no www): " DOMAIN </dev/tty
  [ -z "$ACME_EMAIL" ] && read -rp "Your email (for HTTPS certificate notices): " ACME_EMAIL </dev/tty
  DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#www.}"; DOMAIN="${DOMAIN%/}"
  sed -e "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" \
      -e "s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|" \
      -e "s|^COMPETE_ADMIN_TOKEN=.*|COMPETE_ADMIN_TOKEN=$(openssl rand -hex 24)|" \
      -e "s|^COMPETE_DATA_DIR=.*|COMPETE_DATA_DIR=$DATA_DIR|" \
      -e "s|^COMPETE_DUCKDB_PATH=.*|COMPETE_DUCKDB_PATH=$DATA_DIR/compete.duckdb|" \
      -e "s|^COMPETE_CORS_ORIGINS=.*|COMPETE_CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN|" \
      "$APP_DIR/deploy/mit.env.example" > "$ENV_FILE"
fi
chmod 640 "$ENV_FILE"; chown root:"$APP_USER" "$ENV_FILE"
DOMAIN="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2)"
ACME_EMAIL="$(grep '^ACME_EMAIL=' "$ENV_FILE" | cut -d= -f2)"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR" "$DATA_DIR"

echo "==> 6/8 Backend (Python virtualenv)"
sudo -u "$APP_USER" bash -c "cd $APP_DIR && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt"
# DuckDB extensions used by the first-boot dbt build, installed now so boot never downloads them.
sudo -u "$APP_USER" HOME="/home/$APP_USER" "$APP_DIR/.venv/bin/python" -c \
  "import duckdb; c = duckdb.connect(); [c.install_extension(e) for e in ('httpfs', 'json')]" || true

echo "==> 7/8 Website build (a few minutes)"
sudo -u "$APP_USER" bash -c "cd $APP_DIR/web && npm ci --no-audit --no-fund && \
  NEXT_PUBLIC_STATIC_DATA=0 NEXT_TELEMETRY_DISABLED=1 API_PROXY_TARGET=http://127.0.0.1:8000 \
  NEXT_PUBLIC_SITE_URL=https://$DOMAIN npm run build"

echo "==> 8/8 Services and HTTPS"
install -m 644 "$APP_DIR/deploy/mit-api.service" /etc/systemd/system/mit-api.service
install -m 644 "$APP_DIR/deploy/mit-web.service" /etc/systemd/system/mit-web.service
sed -e "s|{\$DOMAIN}|$DOMAIN|g" -e "s|{\$ACME_EMAIL}|$ACME_EMAIL|g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable mit-api mit-web caddy >/dev/null
systemctl restart mit-api mit-web
systemctl reload caddy 2>/dev/null || systemctl restart caddy
chmod +x "$APP_DIR/deploy/"*.sh
echo "30 3 * * * root $APP_DIR/deploy/backup.sh >> /var/log/mit-backup.log 2>&1" > /etc/cron.d/mit-backup

PUBLIC_IP="$(curl -fsS https://api.ipify.org || echo '<server-ip>')"
cat <<MSG

==================================================================
 Done. First boot seeds the demo data (allow about 5 minutes).

 1. GoDaddy DNS for $DOMAIN:
      Type A   Name @     Value $PUBLIC_IP
      Type A   Name www   Value $PUBLIC_IP   (or keep CNAME www -> @)
 2. Open https://$DOMAIN once DNS has updated. Caddy gets the
    HTTPS certificate automatically.

 Status:   systemctl status mit-api mit-web caddy
 Logs:     journalctl -u mit-api -f      (or mit-web, caddy)
 Health:   curl -s http://127.0.0.1:8000/api/health
 Update:   sudo $APP_DIR/deploy/update.sh
 Settings: sudo nano $ENV_FILE   then: sudo systemctl restart mit-api
 Admin token (keep private): sudo grep ADMIN_TOKEN $ENV_FILE
==================================================================
MSG
