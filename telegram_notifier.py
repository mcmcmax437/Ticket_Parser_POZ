from __future__ import annotations

import requests

from config import Settings
from i18n import t
from qmatic_client import TimeSlot


def format_new_slots_message(
    settings: Settings,
    new_slots: list[TimeSlot],
    *,
    include_continue_hint: bool = False,
) -> str:
    lang = settings.language
    lines = [
        t("notify_new_slots_title", lang),
        "",
        f"{t('notify_service', lang)}: {settings.service_name}",
        f"{t('notify_branch', lang)}: {settings.branch_name}",
        f"{t('notify_cases', lang)}: {settings.num_cases}",
        "",
    ]

    current_date = None
    for slot in new_slots:
        if slot.appointment_date != current_date:
            current_date = slot.appointment_date
            lines.append(f"\n{current_date.isoformat()}:")
        lines.append(f"  • {slot.time}")

    lines.extend(
        [
            "",
            f"{t('notify_booking', lang)}:",
            "https://rezerwacja5.um.poznan.pl/qmaticwebbooking/",
        ]
    )

    if include_continue_hint:
        lines.extend(["", t("notify_search_continues", lang)])

    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    def send_message(self, text: str) -> None:
        response = requests.post(
            f"{self.api_url}/sendMessage",
            json={
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        response.raise_for_status()

    def notify_new_slots(self, new_slots: list[TimeSlot]) -> None:
        if not new_slots:
            return
        self.send_message(format_new_slots_message(self.settings, new_slots))

    def notify_startup(self, slots: list[TimeSlot]) -> None:
        lang = self.settings.language
        deadline = self.settings.notify_before_date.isoformat()

        if not slots:
            self.send_message(
                f"{t('notify_startup_title', lang)}\n"
                f"{t('notify_startup_none', lang, date=deadline)}"
            )
            return

        lines = [
            t("notify_startup_title", lang),
            t("notify_startup_list", lang, date=deadline),
            "",
        ]
        current_date = None
        for slot in slots:
            if slot.appointment_date != current_date:
                current_date = slot.appointment_date
                lines.append(f"\n{current_date.isoformat()}:")
            lines.append(f"  • {slot.time}")

        self.send_message("\n".join(lines))

    def notify_error(self, message: str) -> None:
        self.send_message(f"{t('notify_error_title', self.settings.language)}\n{message}")
