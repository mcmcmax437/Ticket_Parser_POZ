from __future__ import annotations

import logging

from config import Settings
from qmatic_client import TimeSlot

logger = logging.getLogger(__name__)


def log_search_result(
    settings: Settings,
    current_slots: list[TimeSlot],
    new_slots: list[TimeSlot],
    *,
    context: str = "search",
) -> None:
    deadline = settings.notify_before_date.isoformat()
    logger.info(
        "[%s] service=%s | until=%s | total=%d | new=%d | cases=%d | interval=%ds",
        context,
        settings.service_name,
        deadline,
        len(current_slots),
        len(new_slots),
        settings.num_cases,
        settings.poll_interval_seconds,
    )

    if new_slots:
        for slot in new_slots:
            logger.info("  + NEW  %s %s", slot.appointment_date.isoformat(), slot.time)
    elif not current_slots:
        logger.info("  (no slots available)")
    else:
        dates = sorted({slot.appointment_date.isoformat() for slot in current_slots})
        logger.info("  (no new slots; dates seen: %s)", ", ".join(dates[:5]) + ("…" if len(dates) > 5 else ""))
