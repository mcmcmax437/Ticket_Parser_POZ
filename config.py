from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from config_store import load_user_config
from i18n import Language, normalize_language
from services import BRANCH_NAME, ServiceDefinition, get_service, service_label, slot_duration_for_cases

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    branch_id: str
    service: ServiceDefinition
    num_cases: int
    notify_before_date: date
    poll_interval_seconds: int
    notify_on_start: bool
    language: Language
    base_url: str = "https://rezerwacja5.um.poznan.pl/qmaticwebbooking/rest/schedule"
    branch_name: str = BRANCH_NAME

    @property
    def service_id(self) -> str:
        return self.service.service_id

    @property
    def service_key(self) -> str:
        return self.service.key

    @property
    def service_name(self) -> str:
        return service_label(self.service, self.language)

    @property
    def slot_duration_minutes(self) -> int:
        return self.service.duration_minutes

    @property
    def custom_slot_length(self) -> int:
        return slot_duration_for_cases(self.service, self.num_cases)


def load_settings(*, require_telegram: bool = True) -> Settings:
    user_config = load_user_config()

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if require_telegram:
        if not telegram_bot_token:
            raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
        if not telegram_chat_id:
            raise ValueError("Missing required environment variable: TELEGRAM_CHAT_ID")

    notify_before = str(user_config["notify_before_date"]).strip()
    if not notify_before:
        raise ValueError("notify_before_date is required (format: YYYY-MM-DD)")

    service = get_service(str(user_config["service_key"]))
    num_cases = int(user_config["num_cases"])
    if num_cases < 1 or num_cases > service.max_cases:
        num_cases = min(max(num_cases, 1), service.max_cases)

    return Settings(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        branch_id=str(user_config["branch_id"]),
        service=service,
        num_cases=num_cases,
        notify_before_date=date.fromisoformat(notify_before),
        poll_interval_seconds=int(user_config["poll_interval_seconds"]),
        notify_on_start=bool(user_config["notify_on_start"]),
        language=normalize_language(str(user_config.get("language", "en"))),
    )
