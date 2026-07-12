#!/bin/bash
set -e

APP_DIR="/var/www/skss-mis"
APP_USER="skss"

echo "=== SKSS-MIS server setup ==="

apt update
apt install -y python3 python3-venv python3-pip git nginx ufw python3-full

id -u "$APP_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$APP_USER"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

if [ ! -f "$APP_DIR/run.py" ]; then
  echo "ERROR: App code not found in $APP_DIR"
  echo "Clone your repo first, e.g.:"
  echo "  su - skss"
  echo "  cd /var/www/skss-mis"
  echo "  git clone https://github.com/antonyedgar-coder/SKSS-MIS.git ."
  exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > "$APP_DIR/.env" <<EOF
SKSS_SECRET_KEY=$SECRET
DATABASE_URL=sqlite:////$APP_DIR/skss_mis.db
FLASK_ENV=production
EOF
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env with a random secret key."
fi

sudo -u "$APP_USER" bash -lc "
  cd '$APP_DIR'
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
"

cp "$APP_DIR/deploy/skss-mis.service" /etc/systemd/system/skss-mis.service
systemctl daemon-reload
systemctl enable skss-mis
systemctl restart skss-mis

SERVER_NAME="${1:-_}"
sed "s/DROPLET_IP_OR_DOMAIN/$SERVER_NAME/" "$APP_DIR/deploy/nginx-skss-mis.conf" > /etc/nginx/sites-available/skss-mis
ln -sf /etc/nginx/sites-available/skss-mis /etc/nginx/sites-enabled/skss-mis
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

cp "$APP_DIR/deploy/backup-skss-mis.sh" /usr/local/bin/backup-skss-mis.sh
chmod +x /usr/local/bin/backup-skss-mis.sh

ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
ufw --force enable || true

echo ""
echo "=== Done ==="
echo "Check app:  systemctl status skss-mis"
echo "Open site:  http://$SERVER_NAME"
echo "Default login: admin / admin123  (change immediately)"
