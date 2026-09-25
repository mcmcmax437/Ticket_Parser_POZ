from __future__ import annotations

import json
import logging
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from config import STATE_FILE, Settings, load_settings
from qmatic_client import QmaticClient, TimeSlot
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def slot_key(slot: TimeSlot) -> str:
    return f"{slot.appointment_date.isoformat()} {slot.time}"


def load_state(path: Path, service_id: str | None = None) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if service_id and isinstance(data.get("by_service"), dict):
            return set(data["by_service"].get(service_id, []))
        if service_id is None:
            return set(data.get("known_slots", []))
        return set()
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read state file, starting fresh: %s", exc)
        return set()


def save_state(path: Path, known_slots: set[str], service_id: str) -> None:
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    by_service = existing.get("by_service", {})
    if not isinstance(by_service, dict):
        by_service = {}
    by_service[service_id] = sorted(known_slots)

    payload = {
        "by_service": by_service,
        "last_check": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_new_slots(current: list[TimeSlot], known: set[str]) -> list[TimeSlot]:
    return [slot for slot in current if slot_key(slot) not in known]


def run_check(
    settings: Settings,
    client: QmaticClient,
    notifier: TelegramNotifier,
    known_slots: set[str],
    *,
    notify_on_start: bool = False,
) -> set[str]:
    current_slots = client.get_slots_before(settings.notify_before_date)
    current_keys = {slot_key(slot) for slot in current_slots}

    if notify_on_start:
        notifier.notify_startup(current_slots)
        save_state(STATE_FILE, current_keys, settings.service_id)
        return current_keys

    new_slots = find_new_slots(current_slots, known_slots)
    if new_slots:
        logger.info("Found %d new slot(s)", len(new_slots))
        notifier.notify_new_slots(new_slots)
    else:
        logger.info(
            "No new slots. %d slot(s) available before %s.",
            len(current_slots),
            settings.notify_before_date.isoformat(),
        )

    save_state(STATE_FILE, current_keys, settings.service_id)
    return current_keys


def main() -> None:
    settings = load_settings()
    client = QmaticClient(settings)
    notifier = TelegramNotifier(settings)
    known_slots = load_state(STATE_FILE, settings.service_id)
    first_run = not STATE_FILE.exists()

    logger.info(
        "Starting monitor: cases=%d, notify_before=%s, interval=%ds",
        settings.num_cases,
        settings.notify_before_date.isoformat(),
        settings.poll_interval_seconds,
    )

    while True:
        settings = load_settings()
        client = QmaticClient(settings)
        notifier = TelegramNotifier(settings)

        try:
            known_slots = run_check(
                settings,
                client,
                notifier,
                known_slots,
                notify_on_start=first_run and settings.notify_on_start,
            )
            first_run = False
        except Exception as exc:
            logger.exception("Check failed")
            try:
                notifier.notify_error(str(exc))
            except Exception:
                logger.exception("Failed to send Telegram error notification")

        for _ in range(settings.poll_interval_seconds):
            time.sleep(1)


def monitor_worker(stop_event: threading.Event) -> None:
    known_slots = load_state(STATE_FILE, settings.service_id)
    first_run = not STATE_FILE.exists()

    while not stop_event.is_set():
        settings = load_settings()
        client = QmaticClient(settings)
        notifier = TelegramNotifier(settings)

        try:
            known_slots = run_check(
                settings,
                client,
                notifier,
                known_slots,
                notify_on_start=first_run and settings.notify_on_start,
            )
            first_run = False
        except Exception as exc:
            logger.exception("Check failed")
            try:
                notifier.notify_error(str(exc))
            except Exception:
                logger.exception("Failed to send Telegram error notification")

        for _ in range(settings.poll_interval_seconds):
            if stop_event.is_set():
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
