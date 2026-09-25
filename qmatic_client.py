from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests

from config import Settings


@dataclass(frozen=True)
class TimeSlot:
    appointment_date: date
    time: str


class QmaticClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Accept-Language": "pl-PL,pl;q=0.9",
                "User-Agent": "TicketParser/1.0",
            }
        )

    def get_available_dates(self) -> list[date]:
        url = (
            f"{self.settings.base_url}/branches/{self.settings.branch_id}/dates"
            f";servicePublicId={self.settings.service_id}"
            f";customSlotLength={self.settings.custom_slot_length}"
        )
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        return [date.fromisoformat(item["date"]) for item in payload]

    def get_available_times(self, appointment_date: date) -> list[str]:
        date_str = appointment_date.isoformat()
        url = (
            f"{self.settings.base_url}/branches/{self.settings.branch_id}"
            f"/dates/{date_str}/times"
            f";servicePublicId={self.settings.service_id}"
            f";customSlotLength={self.settings.custom_slot_length}"
        )
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        return [item["time"] for item in payload]

    def get_slots_before(self, before_date: date) -> list[TimeSlot]:
        slots: list[TimeSlot] = []
        for appointment_date in self.get_available_dates():
            if appointment_date > before_date:
                continue
            for time_value in self.get_available_times(appointment_date):
                slots.append(TimeSlot(appointment_date=appointment_date, time=time_value))
        slots.sort(key=lambda slot: (slot.appointment_date, slot.time))
        return slots
