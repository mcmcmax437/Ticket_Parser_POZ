from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl

from blocket_catalog import catalog_or_fallback as blocket_catalog_or_fallback
from blocket_client import FUEL_CODES
from car_config import parse_price, parse_tolerance
from car_sources import find_option, parse_sources, search_keys
from car_monitor import CAR_STATE_FILE, clear_car_cache
from car_session import get_car_manager
from config import load_settings
from config_store import load_user_config, update_user_config
from otomoto_catalog import catalog_or_fallback
from search_config import search_state_key_from_config
from search_session import get_search_manager
from services import SERVICES
from ui_format import FUEL_LABELS, GEARBOX_LABELS

logger = logging.getLogger(__name__)

WEB_ROOT = Path(__file__).resolve().parent / "webapp"
PUBLIC_FIELDS = (
    "language",
    "service_key",
    "num_cases",
    "notify_from_date",
    "notify_before_date",
    "poll_interval_seconds",
    "car_make",
    "car_model",
    "car_region",
    "car_year_from",
    "car_year_to",
    "car_price_from",
    "car_price_to",
    "car_price_tolerance",
    "car_mileage_to",
    "car_fuel_type",
    "car_gearbox",
    "car_damaged",
    "car_source",
    "car_poll_interval_seconds",
)
SLUG_FIELDS = {"car_make", "car_model", "car_region"}
INT_FIELDS = {"car_year_from", "car_year_to", "car_mileage_to"}
PRICE_FIELDS = {"car_price_from", "car_price_to"}

_application = None
_loop: asyncio.AbstractEventLoop | None = None


def webapp_url() -> str:
    return os.getenv("WEBAPP_URL", "").strip().rstrip("/")


def _running_searches() -> tuple[bool, bool, list[dict], list[dict]]:
    config = load_user_config()
    app = _application
    if app is None:
        return False, False, [], []
    ticket_key = search_state_key_from_config(config)
    car_keys = search_keys(config)
    tickets = [
        {
            "key": item.search_key,
            "service_key": item.service_key,
            "notify_from_date": item.notify_from_date,
            "notify_before_date": item.notify_before_date,
            "num_cases": item.num_cases,
            "poll_interval_seconds": item.poll_interval_seconds,
            "current": item.search_key == ticket_key,
        }
        for item in get_search_manager(app).list_active()
    ]
    cars = [
        {
            "key": item.search_key,
            "make": item.make,
            "model": item.model,
            "region": item.region,
            "year_from": item.year_from,
            "year_to": item.year_to,
            "price_from": item.price_from,
            "price_to": item.price_to,
            "price_tolerance": item.price_tolerance,
            "mileage_to": item.mileage_to,
            "fuel_type": item.fuel_type,
            "gearbox": item.gearbox,
            "damaged": item.damaged,
            "source": item.source,
            "poll_interval_seconds": item.poll_interval_seconds,
            "current": item.search_key in car_keys,
        }
        for item in get_car_manager(app).list_active()
    ]
    return (
        any(item["current"] for item in tickets),
        any(item["current"] for item in cars),
        tickets,
        cars,
    )


def _fx_public() -> dict:
    try:
        from fx import pln_per_sek

        return {"pln_per_sek": pln_per_sek()}
    except Exception:
        logger.warning("SEK rate is unavailable", exc_info=True)
        return {}


def _known_on_sites(catalogs: list[dict], key: str, token: str, shared: bool) -> bool:
    found = [find_option(catalog.get(key) or [], token) is not None for catalog in catalogs if catalog.get(key)]
    if not found:
        return True
    return any(found) if shared and key == "regions" else all(found)


def _known_model(catalogs: list[dict], make_token: str, model_token: str) -> bool:
    checks = []
    for catalog in catalogs:
        makes = catalog.get("makes") or []
        if not makes:
            continue
        make = find_option(makes, make_token)
        if make is None:
            return False
        models = catalog.get("models", {}).get(make["id"]) or []
        if models:
            checks.append(find_option(models, model_token) is not None)
    return all(checks) if checks else True


def _public_state() -> dict:
    config = load_user_config()
    ticket_running, car_running, ticket_searches, car_searches = _running_searches()
    return {
        "config": {key: config.get(key, "") for key in PUBLIC_FIELDS},
        "ticket_running": ticket_running,
        "car_running": car_running,
        "ticket_searches": ticket_searches,
        "car_searches": car_searches,
        "fx": _fx_public(),
        "services": [
            {"id": key, "en": service.names["en"], "uk": service.names["uk"]}
            for key, service in SERVICES.items()
        ],
        "fuels": [{"id": key, "label": label} for key, label in FUEL_LABELS.items()],
        "gears": [{"id": key, "label": label} for key, label in GEARBOX_LABELS.items()],
    }


def _check_init_data(raw: str) -> bool:
    parsed = dict(parse_qsl(raw, keep_blank_values=True))
    received = parsed.pop("hash", "")
    if not received:
        return False
    secret = hmac.new(b"WebAppData", load_settings().telegram_bot_token.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, received):
        return False
    try:
        user = json.loads(parsed.get("user") or "{}")
    except json.JSONDecodeError:
        return False
    return str(user.get("id", "")) == str(load_settings().telegram_chat_id)


def _clean_patch(body: dict) -> dict:
    changes: dict = {}
    if "language" in body:
        changes["language"] = "uk" if str(body["language"]).lower().startswith("uk") else "en"
    if "service_key" in body:
        key = str(body["service_key"])
        if key not in SERVICES:
            raise ValueError("Unknown service")
        changes["service_key"] = key
    if "num_cases" in body:
        cases = int(body["num_cases"])
        if cases not in {1, 2, 3}:
            raise ValueError("Cases must be 1, 2 or 3")
        changes["num_cases"] = cases
    if "notify_from_date" in body or "notify_before_date" in body:
        current = load_user_config()
        start = str(body.get("notify_from_date", current.get("notify_from_date") or "")).strip()
        end = str(body.get("notify_before_date", current.get("notify_before_date") or "")).strip()
        if start:
            date.fromisoformat(start)
        if not end:
            raise ValueError("End date is required")
        date.fromisoformat(end)
        if start and start > end:
            raise ValueError("Start date is after the end date")
        if "notify_from_date" in body:
            changes["notify_from_date"] = start
        if "notify_before_date" in body:
            changes["notify_before_date"] = end
    if "poll_interval_seconds" in body:
        seconds = int(body["poll_interval_seconds"])
        changes["poll_interval_seconds"] = max(60, min(seconds, 86400))
    if "car_poll_interval_seconds" in body:
        seconds = int(body["car_poll_interval_seconds"])
        changes["car_poll_interval_seconds"] = max(60, min(seconds, 86400))
    current = load_user_config()
    if "car_source" in body:
        changes["car_source"] = ",".join(parse_sources(body["car_source"]))
    sources = parse_sources(changes.get("car_source", current.get("car_source") or "otomoto"))
    shared = len(sources) > 1
    catalogs = [
        blocket_catalog_or_fallback() if source == "blocket" else catalog_or_fallback()
        for source in sources
    ]
    list_ids = {
        "car_year_from": set.intersection(*(set(catalog["years"]) for catalog in catalogs)),
        "car_year_to": set.intersection(*(set(catalog["years"]) for catalog in catalogs)),
        "car_mileage_to": set.intersection(*(set(map(str, catalog["mileages"])) for catalog in catalogs)),
    }
    for field in SLUG_FIELDS:
        if field not in body:
            continue
        raw = str(body[field]).strip()
        if not raw:
            changes[field] = ""
            continue
        if shared:
            changes[field] = raw if field == "car_region" else re.sub(r"\s+", " ", raw).strip().casefold()
            continue
        if sources == ["blocket"]:
            if not re.fullmatch(r"\d+(?:\.\d+)*", raw):
                raise ValueError(f"Invalid {field}")
            changes[field] = raw
            continue
        slug = re.sub(r"[\s_]+", "-", raw).strip("-").lower()
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            raise ValueError(f"Invalid {field}")
        changes[field] = slug
    make = str(changes.get("car_make", current.get("car_make") or ""))
    if "car_make" in body and make and not _known_on_sites(catalogs, "makes", make, shared):
        raise ValueError("Unknown make")
    if "car_model" in body:
        model = str(changes.get("car_model") or "")
        if model and not _known_model(catalogs, make, model):
            raise ValueError("Unknown model")
    if "car_region" in body:
        region = str(changes.get("car_region") or "")
        if region and not _known_on_sites(catalogs, "regions", region, shared):
            raise ValueError("Unknown region")
    for field in INT_FIELDS:
        if field not in body:
            continue
        digits = re.sub(r"[^\d]", "", str(body[field]))
        if not digits:
            changes[field] = ""
            continue
        number = int(digits)
        if field == "car_mileage_to":
            if number > 2_000_000:
                raise ValueError("Mileage must be from 1 to 2 000 000 km")
            changes[field] = str(number)
            continue
        if str(number) not in list_ids[field]:
            kind = "year" if field.startswith("car_year") else "mileage"
            raise ValueError(f"Choose a {kind} from the list")
        changes[field] = str(number)
    for field in PRICE_FIELDS:
        if field not in body:
            continue
        changes[field] = parse_price(body[field])
    if "car_price_tolerance" in body:
        changes["car_price_tolerance"] = parse_tolerance(body["car_price_tolerance"])

    def picked(field: str) -> str:
        if field in changes:
            return str(changes[field])
        return str(current.get(field) or "")

    if "car_year_from" in body or "car_year_to" in body:
        start, end = picked("car_year_from"), picked("car_year_to")
        if start and end and int(start) > int(end):
            raise ValueError("Year from is after year to")
    if "car_price_from" in body or "car_price_to" in body:
        start, end = picked("car_price_from"), picked("car_price_to")
        if start and end and int(start) > int(end):
            raise ValueError("Price from is after price to")
    if "car_fuel_type" in body:
        fuel = str(body["car_fuel_type"])
        allowed_fuels = set(FUEL_CODES) if "blocket" in sources else set(FUEL_LABELS)
        if fuel and fuel not in allowed_fuels:
            raise ValueError("Unknown fuel")
        changes["car_fuel_type"] = fuel
    if "car_gearbox" in body:
        gear = str(body["car_gearbox"])
        if gear and gear not in GEARBOX_LABELS:
            raise ValueError("Unknown gearbox")
        changes["car_gearbox"] = gear
    if "car_damaged" in body:
        damaged = str(body["car_damaged"]).strip()
        if damaged not in {"", "0", "1"}:
            raise ValueError("Unknown condition")
        changes["car_damaged"] = damaged
    return changes


def _call(coro):
    if _loop is None:
        raise RuntimeError("Bot is not running")
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=60)


def _search_key(body: dict) -> str | None:
    if body.get("key") in (None, ""):
        return None
    key = str(body["key"])
    if len(key) > 500 or any(char in key for char in "\r\n\x00"):
        raise ValueError("Unknown search")
    return key


async def _touch_card() -> None:
    if _application is None:
        return
    try:
        from i18n import normalize_language
        from widget_sender import refresh_status_card

        await refresh_status_card(
            _application,
            int(load_settings().telegram_chat_id),
            normalize_language(str(load_user_config().get("language", "en"))),
        )
    except Exception:
        logger.exception("Status card was not refreshed")


async def _start_ticket() -> None:
    config = load_user_config()
    manager = get_search_manager(_application)
    if not manager.is_running(search_state_key_from_config(config)):
        await manager.start_config(config, _application, int(load_settings().telegram_chat_id))
    await _touch_card()


async def _stop_ticket(body: dict) -> None:
    manager = get_search_manager(_application)
    key = _search_key(body)
    if key:
        await manager.stop_key(key)
    elif body.get("all") is True:
        await manager.stop_all()
    else:
        await manager.stop_config(load_user_config())
    await _touch_card()


async def _start_car() -> None:
    config = load_user_config()
    if not str(config.get("car_make") or "").strip():
        raise ValueError("Enter the car make first")
    manager = get_car_manager(_application)
    await manager.start_config(config, _application, int(load_settings().telegram_chat_id))
    await _touch_card()


async def _stop_car(body: dict) -> None:
    manager = get_car_manager(_application)
    key = _search_key(body)
    if key:
        await manager.stop_key(key)
    elif body.get("all") is True:
        await manager.stop_all()
    else:
        await manager.stop_config(load_user_config())
    await _touch_card()


async def _reset_car_cache() -> None:
    if _application is not None:
        get_car_manager(_application).forget_tracked()
    clear_car_cache(CAR_STATE_FILE)


async def _stop_everything() -> None:
    if _application is None:
        raise RuntimeError("Bot is not running")
    await get_search_manager(_application).stop_all()
    await get_car_manager(_application).stop_all()
    await _touch_card()


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        logger.info("webapp " + fmt, *args)

    def _authorized(self) -> bool:
        if self.headers.get("X-Local-Preview") == "1":
            return self.client_address[0] in {"127.0.0.1", "::1"}
        return _check_init_data(self.headers.get("X-Telegram-Init-Data", ""))

    def _send(self, code: int, payload: dict | bytes, content_type: str) -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 20000:
            raise ValueError("Body is too large")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode() or "{}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/", "/index.html"}:
            page = (WEB_ROOT / "index.html").read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
            return
        if path not in {"/api/state", "/api/options"}:
            self._send(404, {"error": "Not found"}, "application/json")
            return
        if not self._authorized():
            self._send(401, {"error": "Open this page from the bot"}, "application/json")
            return
        if path == "/api/options":
            payload = dict(catalog_or_fallback())
            payload["blocket"] = blocket_catalog_or_fallback()
            self._send(200, payload, "application/json")
            return
        self._send(200, _public_state(), "application/json")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if not self._authorized():
            self._send(401, {"error": "Open this page from the bot"}, "application/json")
            return
        try:
            body = self._read_json()
            if path == "/api/state":
                changes = _clean_patch(body)
                if changes:
                    update_user_config(**changes)
            elif path == "/api/ticket/start":
                _call(_start_ticket())
            elif path == "/api/ticket/stop":
                _call(_stop_ticket(body))
            elif path == "/api/car/start":
                _call(_start_car())
            elif path == "/api/car/stop":
                _call(_stop_car(body))
            elif path == "/api/stop-all":
                _call(_stop_everything())
            elif path == "/api/car/reset-cache":
                if _application is not None and _loop is not None:
                    _call(_reset_car_cache())
                else:
                    clear_car_cache(CAR_STATE_FILE)
            else:
                self._send(404, {"error": "Not found"}, "application/json")
                return
        except Exception as exc:
            self._send(400, {"error": str(exc)}, "application/json")
            return
        self._send(200, _public_state(), "application/json")


def start_webapp(application) -> None:
    global _application, _loop
    _application = application
    _loop = asyncio.get_running_loop()
    port = int(os.getenv("WEBAPP_PORT", "8080") or "8080")
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    except OSError as exc:
        logger.warning("Mini App server did not start on port %s: %s", port, exc)
        return
    threading.Thread(target=server.serve_forever, name="webapp", daemon=True).start()
    threading.Thread(target=catalog_or_fallback, name="otomoto-catalog", daemon=True).start()
    threading.Thread(target=blocket_catalog_or_fallback, name="blocket-catalog", daemon=True).start()
    threading.Thread(target=_fx_public, name="sek-rate", daemon=True).start()
    logger.info("Mini App listening on http://0.0.0.0:%s", port)
