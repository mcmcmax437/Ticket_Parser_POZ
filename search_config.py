from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from config_store import load_user_config
from i18n import normalize_language
from services import get_service


def search_state_key(service_id: str, notify_before: date, num_cases: int) -> str:
    return f"{service_id}|{notify_before.isoformat()}|{num_cases}"


def search_state_key_from_config(config: dict) -> str:
    service = get_service(str(config["service_key"]))
    return search_state_key(
        service.service_id,
        date.fromisoformat(str(config["notify_before_date"])),
        int(config["num_cases"]),
    )


@dataclass(frozen=True)
class ActiveSearchInfo:
    search_key: str
    service_key: str
    service_name: str
    notify_before_date: str
    num_cases: int


def build_settings_from_config(config: dict, *, require_telegram: bool = True):
    from config import Settings

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if require_telegram:
        if not telegram_bot_token:
            raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
        if not telegram_chat_id:
            raise ValueError("Missing required environment variable: TELEGRAM_CHAT_ID")

    notify_before = str(config["notify_before_date"]).strip()
    service = get_service(str(config["service_key"]))
    num_cases = int(config["num_cases"])
    num_cases = min(max(num_cases, 1), service.max_cases)

    return Settings(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        branch_id=str(config.get("branch_id", load_user_config()["branch_id"])),
        service=service,
        num_cases=num_cases,
        notify_before_date=date.fromisoformat(notify_before),
        poll_interval_seconds=int(config["poll_interval_seconds"]),
        notify_on_start=bool(config.get("notify_on_start", False)),
        language=normalize_language(str(config.get("language", "en"))),
    )


def active_search_info(settings, search_key: str) -> ActiveSearchInfo:
    return ActiveSearchInfo(
        search_key=search_key,
        service_key=settings.service_key,
        service_name=settings.service_name,
        notify_before_date=settings.notify_before_date.isoformat(),
        num_cases=settings.num_cases,
    )


def current_config_active(active_keys: set[str]) -> bool:
    config = load_user_config()
    return search_state_key_from_config(config) in active_keys
