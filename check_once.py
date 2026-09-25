from __future__ import annotations

import argparse
import logging
import sys

from config import STATE_FILE, load_settings
from monitor import load_state, run_check
from qmatic_client import QmaticClient
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single availability check")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print slots without sending Telegram messages",
    )
    args = parser.parse_args()

    settings = load_settings(require_telegram=not args.dry_run)
    client = QmaticClient(settings)

    slots = client.get_slots_before(settings.notify_before_date)
    logger.info("Found %d slot(s) before %s", len(slots), settings.notify_before_date)

    for slot in slots:
        print(f"{slot.appointment_date.isoformat()} {slot.time}")

    if args.dry_run:
        return

    notifier = TelegramNotifier(settings)
    known_slots = load_state(STATE_FILE, settings.service_id)
    run_check(settings, client, notifier, known_slots)


if __name__ == "__main__":
    main()
