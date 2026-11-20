#!/usr/bin/env bash
# One-command setup for an Oracle Cloud Always Free Ubuntu VM (ARM or x86).
# Run on the server:
#   curl -fsSL https://raw.githubusercontent.com/subham1902/Marketing-Intelligence-Tracker/main/deploy/install.sh | sudo bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/subham1902/Marketing-Intelligence-Tracker.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/mit}"

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo."; exit 1; fi
. /etc/os-release
echo "==> OS: $PRETTY_NAME ($(uname -m))"

echo "==> Installing Docker, git and firewall tools"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git iptables-persistent netfilter-persistent
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
SUDO_USER_NAME="${SUDO_USER:-ubuntu}"
usermod -aG docker "$SUDO_USER_NAME" || true

echo "==> Opening ports 80 and 443 in the VM firewall (Oracle images block them by default)"
for p in 80 443; do
  iptables -C INPUT -p tcp --dport "$p" -m state --state NEW -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 6 -p tcp --dport "$p" -m state --state NEW -j ACCEPT
done
iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p udp --dport 443 -j ACCEPT
netfilter-persistent save

echo "==> Adding 4 GB swap (safety margin for the frontend build)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Fetching the app into $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH" && git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
chown -R "$SUDO_USER_NAME":"$SUDO_USER_NAME" "$APP_DIR"

ENV_FILE="$APP_DIR/deploy/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "==> First-time configuration"
  DOMAIN="${DOMAIN:-}"; ACME_EMAIL="${ACME_EMAIL:-}"
  [ -z "$DOMAIN" ] && read -rp "Your domain (e.g. example.com, no www): " DOMAIN </dev/tty
  [ -z "$ACME_EMAIL" ] && read -rp "Your email (for HTTPS certificate notices): " ACME_EMAIL </dev/tty
  DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#www.}"; DOMAIN="${DOMAIN%/}"
  cp "$APP_DIR/deploy/.env.example" "$ENV_FILE"
  sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|; s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|; s|^COMPETE_ADMIN_TOKEN=.*|COMPETE_ADMIN_TOKEN=$(openssl rand -hex 24)|" "$ENV_FILE"
  chmod 600 "$ENV_FILE"; chown "$SUDO_USER_NAME":"$SUDO_USER_NAME" "$ENV_FILE"
fi
DOMAIN="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2)"

echo "==> Building and starting (first build takes about 10-20 minutes)"
cd "$APP_DIR/deploy"
docker compose up -d --build

echo "==> Installing nightly backup (03:30 server time, keeps 7 days)"
chmod +x "$APP_DIR/deploy/"*.sh
echo "30 3 * * * root $APP_DIR/deploy/backup.sh >> /var/log/mit-backup.log 2>&1" > /etc/cron.d/mit-backup

PUBLIC_IP="$(curl -fsS https://api.ipify.org || echo '<server-ip>')"
cat <<MSG

==================================================================
 Done. The app is starting (first boot seeds data: allow ~5 min).

 1. In GoDaddy DNS, set these records to this server's IP:
      Type A   Name @     Value $PUBLIC_IP
      Type A   Name www   Value $PUBLIC_IP
 2. Wait for DNS, then open https://$DOMAIN
    (Caddy gets the HTTPS certificate automatically once DNS points here.)

 Status:   cd $APP_DIR/deploy && docker compose ps
 Logs:     cd $APP_DIR/deploy && docker compose logs -f --tail=100
 Update:   sudo $APP_DIR/deploy/update.sh
 Admin token (keep private): grep ADMIN_TOKEN $ENV_FILE
==================================================================
MSG
