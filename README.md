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
sudo apt update && sudo apt install -y python3 python3.10-venv
mkdir -p ~/ticket-parser
```

`python3-venv` is a package Ubuntu often leaves out, and without it `python3 -m venv` fails with "ensurepip is not available". The bot runs as a **system** service, so `VPS_USER` must be root.

Put `.env` in that directory (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Deploys leave `.env`, `user_config.json`, and `state.json` in place. Each restart brings the bot back and sends the menu. An in-progress search does not resume; press **Start search** again.

## Car search (otomoto.pl)

Separate section in the bot menu (`🚗 Car search`). It watches otomoto.pl and notifies about:

- **new listings** matching your filters
- **price drops** on listings you have already seen

Filters: make, model, region/city, year range, price range, max mileage, fuel type, gearbox, check interval (default 15 min).

Values are otomoto.pl URL slugs, lowercase, hyphens:

| Filter | Example |
|--------|---------|
| Make | `volkswagen` |
| Model | `golf`, `seria-3` |
| Region / city | `mazowieckie`, `warszawa` |
| Fuel | petrol · diesel · hybrid · hybrid (plug-in) · electric · petrol+LPG |
| Gearbox | manual · automatic |

State is kept in `car_state.json`, one entry per filter combination. Several car searches can run at once (start one, change filters, start another). **🔄 Clear tracked listings** forgets what was seen, so the next check reports everything as new.

Limits: the scraper reads at most **8 pages** (33 listings each) per check, sorted by `created_at:desc`. Make and model are checked against the listing URL slug — otomoto silently falls back to other makes/models when a slug does not exist, so a bogus model returns 0 listings. A bogus region slug is silently ignored by the site and cannot be detected.

## Telegram widgets (Bot API 10.4)

Alerts and a live status card are drawn as [HTML widgets](https://core.telegram.org/bots/widgets) instead of plain text.

- **Alert widgets** — one per hit: `🚌 New free slots` and `🚗 Car hits`. Data is baked into the widget, it does not change after sending. Listing links are in the caption, so they stay clickable.
- **Status card** — a single widget message that shows what is running now (badge + one line per active search, cap 6 then `+N more`, plus the last check time). The bot writes its state with `editMessageWidgetData` only when the drawn state actually changed; the card is created on the first change and redrawn to the idle badge when everything stops.

If a widget does not fit the API limits (`html` ≤ 32768 bytes and ≤ 4096 bytes compressed with zlib, `chat_data` ≤ 1024 bytes) or the call fails, the bot falls back to the normal text alert.

python-telegram-bot 22.8 covers Bot API 10.0 only, so widgets are sent with raw `do_api_request` calls (`sendWidget`, `editMessageWidgetData`). In production Telegram allows widgets only in the private chat with the bot; groups and inline mode work on the test server only.

## Notes

- Search runs only while **Start search** is active
- On start, current slots are recorded — you get notified only about **new** slots that appear after that
- Supports **English** and **Ukrainian**
