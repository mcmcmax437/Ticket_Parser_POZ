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

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ticket-parser.service" <<UNIT
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
WantedBy=default.target
UNIT

uid="$(id -u)"
export XDG_RUNTIME_DIR="/run/user/${uid}"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

if [[ ! -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  echo "User systemd is not running. On the server, once: sudo loginctl enable-linger $(id -un)" >&2
  exit 1
fi

systemctl --user daemon-reload
systemctl --user enable ticket-parser
systemctl --user restart ticket-parser
sleep 3
systemctl --user --no-pager --full status ticket-parser || true
systemctl --user is-active --quiet ticket-parser
echo "ticket-parser is running in ${APP_DIR}"
