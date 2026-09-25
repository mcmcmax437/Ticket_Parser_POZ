from __future__ import annotations

import logging
import sys

from config import load_settings
from telegram_bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = load_settings()
    application = build_application(settings.telegram_bot_token)
    logger.info("Telegram bot started")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
