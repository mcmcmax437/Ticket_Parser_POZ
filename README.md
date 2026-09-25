# Ticket Parser — Poznań Qmatic Monitor

Monitors the Poznań city appointment booking system and sends Telegram notifications when new slots appear.

## Quick start

```bash
pip install -r requirements.txt
python run.py
```

On startup the bot sends you the menu. Then:

1. Set your **target date** (inline button or Settings)
2. Press **🟢 Start search**
3. Get notified when new slots appear
4. Press **🔴 Stop search** when done

## Persistent menu buttons

| Button | Action |
|--------|--------|
| 🟢 Start search | Begin continuous monitoring |
| 🔴 Stop search | Stop monitoring |
| 📋 Menu | Show main menu |
| ⚙️ Settings | Language, interval, reset |

## Commands

- `/start` or `/menu` — show menu
- `/stop` — stop search
- `/settings` — settings panel

## Configuration

Secrets in `.env`:
```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Other settings via bot UI → saved to `user_config.json`.

## Services

Two services are supported (switch in bot menu):

| Service | Description |
|---------|-------------|
| **Annotations in certificate** | Adnotacje w Dowodach rejestracyjnych |
| **Vehicle registration** | Rejestracja pojazdów |
| **Certificate pickup** | Odbiór stałego dowodu rejestracyjnego |

Each service has its own slot tracking — switching service does not mix notifications.

## Deploy

Pushes to `main` upload the code to the VPS and restart the bot. Required repository secrets:

| Secret | Value |
|--------|--------|
| `VPS_HOST` | Server hostname or IP |
| `VPS_USER` | SSH user |
| `VPS_SSH_PRIVATE_KEY` | Private key whose public half is in that user's `authorized_keys` |

Optional: `VPS_PORT` (default `22`), `VPS_APP_DIR` (default `~/ticket-parser`).

On the server, once:

```bash
sudo apt update && sudo apt install -y python3 python3-venv
sudo loginctl enable-linger "$USER"
mkdir -p ~/ticket-parser
```

Put `.env` in that directory (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Deploys leave `.env`, `user_config.json`, and `state.json` in place. Each restart brings the bot back and sends the menu. An in-progress search does not resume; press **Start search** again.

## Notes

- Search runs only while **Start search** is active
- On start, current slots are recorded — you get notified only about **new** slots that appear after that
- Supports **English** and **Ukrainian**
