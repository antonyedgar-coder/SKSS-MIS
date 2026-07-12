#!/bin/bash
# Run on the DigitalOcean droplet as root (after code is on GitHub):
#   curl -fsSL https://raw.githubusercontent.com/antonyedgar-coder/SKSS-MIS/main/deploy/server-fresh-install.sh | bash
# Or after cloning:
#   bash /var/www/skss-mis/deploy/server-fresh-install.sh 143.110.190.244
set -e

APP_DIR="/var/www/skss-mis"
APP_USER="skss"
REPO="https://github.com/antonyedgar-coder/SKSS-MIS.git"
SERVER_NAME="${1:-_}"

echo "=== SKSS-MIS fresh install ==="

apt update
apt install -y python3 python3-venv python3-pip git nginx ufw python3-full

id -u "$APP_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$APP_USER"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

if [ ! -f "$APP_DIR/run.py" ]; then
  echo "Cloning repository..."
  sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
fi

bash "$APP_DIR/deploy/server-setup.sh" "$SERVER_NAME"
