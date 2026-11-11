#!/usr/bin/env bash
# Runs on the VPS after GitHub Actions syncs the repo.
set -euo pipefail

if [[ -z "${APP_DIR:-}" ]]; then
  APP_DIR="$HOME/ticket-parser"
fi
if [[ "$APP_DIR" != /* ]]; then
  APP_DIR="$HOME/$APP_DIR"
fi

cd "$APP_DIR"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "This deploy installs a system-level service, so VPS_USER must be root."
  exit 1
fi

# Debian/Ubuntu ship the venv module without ensurepip, so `python3 -m venv`
# aborts with "ensurepip is not available" unless that package is installed.
if ! python3 -c 'import ensurepip' 2>/dev/null; then
  echo "python3-venv is missing on the server. Run once: apt install -y python3.10-venv"
  exit 1
fi

# A venv left over without pip is unusable; rebuild it instead of reusing it.
if [[ ! -x .venv/bin/pip ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/ticket-parser.service <<UNIT
[Unit]
Description=Poznan Qmatic ticket monitor
After=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable ticket-parser
systemctl restart ticket-parser
sleep 3
systemctl --no-pager --full status ticket-parser || true
systemctl is-active --quiet ticket-parser
echo "ticket-parser is running in ${APP_DIR}"
