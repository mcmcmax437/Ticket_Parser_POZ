from __future__ import annotations

import asyncio
import logging
import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from config import STATE_FILE
from search_config import (
    ActiveSearchInfo,
    active_search_info,
    build_settings_from_config,
    search_state_key,
    search_state_key_from_config,
)
from i18n import t
from monitor import find_new_slots, load_state, save_state, slot_key
from qmatic_client import QmaticClient
from search_log import log_search_result
from telegram_notifier import format_new_slots_message

logger = logging.getLogger(__name__)

SLOT_CONFIRMATIONS_KEY = "slot_confirmations"


def _store_slot_notification(
    application: Application,
    search_key: str,
    new_slots: list,
) -> str:
    confirm_id = secrets.token_hex(4)
    application.bot_data.setdefault(SLOT_CONFIRMATIONS_KEY, {})[confirm_id] = {
        "search_key": search_key,
        "slot_keys": [slot_key(slot) for slot in new_slots],
    }
    return confirm_id


async def notify_new_slots_with_confirm(
    application: Application,
    chat_id: int,
    settings,
    search_key: str,
    new_slots: list,
) -> None:
    lang = settings.language
    text = format_new_slots_message(settings, new_slots, include_continue_hint=True)
    confirm_id = _store_slot_notification(application, search_key, new_slots)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t("btn_slot_confirmed", lang), callback_data=f"confirm:booked:{confirm_id}"),
                InlineKeyboardButton(t("btn_slot_not_booked", lang), callback_data=f"confirm:not_booked:{confirm_id}"),
            ]
        ]
    )

    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


class SearchWorker:
    def __init__(self, search_key: str, settings) -> None:
        self.search_key = search_key
        self.settings = settings
        self.task: asyncio.Task | None = None
        self.stop_event: asyncio.Event | None = None
        self.known_slots: set[str] = set()

    @property
    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self, application: Application, chat_id: int) -> None:
        if self.is_running:
            return

        client = QmaticClient(self.settings)
        current_slots = await asyncio.to_thread(
            client.get_slots_before,
            self.settings.notify_before_date,
        )
        self.known_slots = {slot_key(slot) for slot in current_slots}
        save_state(STATE_FILE, self.known_slots, self.search_key)

        logger.info(
            "Search STARTED | key=%s | service=%s | until=%s | baseline=%d",
            self.search_key,
            self.settings.service_name,
            self.settings.notify_before_date.isoformat(),
            len(self.known_slots),
        )
        log_search_result(self.settings, current_slots, [], context="search-start")

        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            self._loop(application, chat_id),
            name=f"search-{self.search_key[:24]}",
        )

    async def stop(self) -> None:
        if not self.is_running or self.stop_event is None:
            return

        logger.info("Search STOPPED | key=%s", self.search_key)
        self.stop_event.set()
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.stop_event = None

    async def _loop(self, application: Application, chat_id: int) -> None:
        try:
            while self.stop_event and not self.stop_event.is_set():
                client = QmaticClient(self.settings)
                lang = self.settings.language

                try:
                    current_slots = await asyncio.to_thread(
                        client.get_slots_before,
                        self.settings.notify_before_date,
                    )
                    current_keys = {slot_key(slot) for slot in current_slots}
                    new_slots = find_new_slots(current_slots, self.known_slots)

                    log_search_result(self.settings, current_slots, new_slots, context="search")

                    if new_slots:
                        await notify_new_slots_with_confirm(
                            application,
                            chat_id,
                            self.settings,
                            self.search_key,
                            new_slots,
                        )

                    self.known_slots = current_keys
                    save_state(STATE_FILE, current_keys, self.search_key)
                except Exception as exc:
                    logger.exception("Search check failed for %s", self.search_key)
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"{t('notify_error_title', lang)}\n{self.settings.service_name}\n{exc}",
                        )
                    except Exception:
                        logger.exception("Failed to send error message")

                for _ in range(self.settings.poll_interval_seconds):
                    if self.stop_event.is_set():
                        break
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Search cancelled | key=%s", self.search_key)
            raise


class SearchManager:
    def __init__(self) -> None:
        self._workers: dict[str, SearchWorker] = {}

    @property
    def active_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.is_running)

    def active_keys(self) -> set[str]:
        return {key for key, worker in self._workers.items() if worker.is_running}

    def list_active(self) -> list[ActiveSearchInfo]:
        result: list[ActiveSearchInfo] = []
        for worker in self._workers.values():
            if worker.is_running:
                result.append(active_search_info(worker.settings, worker.search_key))
        return result

    def is_running(self, search_key: str) -> bool:
        worker = self._workers.get(search_key)
        return worker is not None and worker.is_running

    async def start_config(self, config: dict, application: Application, chat_id: int) -> str:
        settings = build_settings_from_config(config)
        key = search_state_key(
            settings.service_id,
            settings.notify_before_date,
            settings.num_cases,
        )

        worker = self._workers.get(key)
        if worker and worker.is_running:
            return key

        if worker is None:
            worker = SearchWorker(key, settings)
            self._workers[key] = worker
        else:
            self._workers[key] = SearchWorker(key, settings)

        await self._workers[key].start(application, chat_id)
        return key

    async def stop_key(self, search_key: str) -> bool:
        worker = self._workers.get(search_key)
        if worker is None or not worker.is_running:
            return False
        await worker.stop()
        return True

    async def stop_config(self, config: dict) -> bool:
        key = search_state_key_from_config(config)
        return await self.stop_key(key)

    async def stop_all(self) -> int:
        stopped = 0
        for worker in list(self._workers.values()):
            if worker.is_running:
                await worker.stop()
                stopped += 1
        return stopped

    def release_known_slots(self, search_key: str, slot_keys: list[str]) -> None:
        worker = self._workers.get(search_key)
        if worker is None:
            return
        for key in slot_keys:
            worker.known_slots.discard(key)
        save_state(STATE_FILE, worker.known_slots, search_key)


def get_search_manager(application: Application) -> SearchManager:
    manager = application.bot_data.get("search_manager")
    if manager is None:
        manager = SearchManager()
        application.bot_data["search_manager"] = manager
    return manager


def get_search_session(application: Application) -> SearchManager:
    return get_search_manager(application)
