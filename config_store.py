from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services import get_service

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
USER_CONFIG_FILE = BASE_DIR / "user_config.json"

DEFAULT_USER_CONFIG: dict[str, Any] = {
    "num_cases": 1,
    "notify_before_date": "2026-06-15",
    "poll_interval_seconds": 300,
    "notify_on_start": False,
    "branch_id": "82431f5aac5af7c75a3be70c3de3d449396d10d39a51f95899011243f7a23097",
    "service_key": "annotations",
    "language": "en",
}


def _env_fallback(key: str, default: Any) -> Any:
    mapping = {
        "num_cases": ("NUM_CASES", int),
        "notify_before_date": ("NOTIFY_BEFORE_DATE", str),
        "poll_interval_seconds": ("POLL_INTERVAL_SECONDS", int),
        "notify_on_start": ("NOTIFY_ON_START", lambda v: v.strip().lower() in {"1", "true", "yes", "on"}),
        "branch_id": ("BRANCH_ID", str),
        "service_key": ("SERVICE_KEY", str),
        "language": ("LANGUAGE", str),
    }
    if key not in mapping:
        return default
    env_name, caster = mapping[key]
    raw = os.getenv(env_name)
    if raw is None or not str(raw).strip():
        return default
    return caster(raw.strip())


def _migrate_legacy_config(config: dict[str, Any]) -> dict[str, Any]:
    if "service_key" in config:
        return config

    legacy_service_id = config.pop("service_id", None)
    legacy_duration = config.pop("slot_duration_minutes", None)
    if legacy_service_id:
        from services import get_service_by_id

        service = get_service_by_id(str(legacy_service_id))
        if service:
            config["service_key"] = service.key
    if "service_key" not in config:
        config["service_key"] = "annotations"
    return config


def load_user_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_USER_CONFIG)
    for key in DEFAULT_USER_CONFIG:
        config[key] = _env_fallback(key, config[key])

    if USER_CONFIG_FILE.exists():
        try:
            stored = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                stored = _migrate_legacy_config(stored)
                config.update({k: stored[k] for k in DEFAULT_USER_CONFIG if k in stored})
                if "service_id" in stored and "service_key" not in stored:
                    config = _migrate_legacy_config({**config, **stored})
        except (json.JSONDecodeError, OSError):
            pass

    get_service(str(config["service_key"]))
    return config


def save_user_config(config: dict[str, Any]) -> None:
    payload = {key: config[key] for key in DEFAULT_USER_CONFIG}
    USER_CONFIG_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_user_config(**changes: Any) -> dict[str, Any]:
    config = load_user_config()
    config.update(changes)
    if "service_key" in changes:
        get_service(str(changes["service_key"]))
    save_user_config(config)
    return config


def format_interval(seconds: int) -> str:
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} min"
    return f"{seconds} s"
