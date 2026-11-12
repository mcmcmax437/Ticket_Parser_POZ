from __future__ import annotations

import asyncio
import logging

from telegram import Application

from car_config import car_search_info, car_search_key_from_config, car_search_params_from_config
from car_monitor import CAR_STATE_FILE, find_new_listings, find_price_drops, load_car_state, save_car_state
from i18n import normalize_language, t
from otomoto_client import OtomotoClient
from ui_format import format_car_alert_html

logger = logging.getLogger(__name__)


class CarWorker:
    def __init__(self, search_key: str, config: dict) -> None:
        self.search_key = search_key
        self.config = config
        self.params = car_search_params_from_config(config)
        self.info = car_search_info(config, search_key)
        self.poll_interval_seconds = int(config["car_poll_interval_seconds"])
        self.language = normalize_language(str(config.get("language", "en")))
        self.known: dict[str, int | None] = {}
        self.task: asyncio.Task | None = None
        self.stop_event: asyncio.Event | None = None

    @property
    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self, application: Application, chat_id: int) -> None:
        if self.is_running:
            return

        client = OtomotoClient()
        current = await asyncio.to_thread(client.get_listings, self.params)
        self.known = {item.listing_id: item.price for item in current}
        save_car_state(CAR_STATE_FILE, self.search_key, current)

        logger.info(
            "Car search STARTED | key=%s | baseline=%d",
            self.search_key,
            len(self.known),
        )

        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            self._loop(application, chat_id),
            name=f"car-{self.search_key[:24]}",
        )

    async def stop(self) -> None:
        if not self.is_running or self.stop_event is None:
            return

        logger.info("Car search STOPPED | key=%s", self.search_key)
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
                for _ in range(self.poll_interval_seconds):
                    if self.stop_event.is_set():
                        break
                    await asyncio.sleep(1)
                if self.stop_event.is_set():
                    break

                client = OtomotoClient()
                try:
                    current = await asyncio.to_thread(client.get_listings, self.params)
                    new_listings = find_new_listings(current, self.known)
                    price_drops = find_price_drops(current, self.known)

                    if new_listings or price_drops:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=format_car_alert_html(
                                self.language,
                                self.info,
                                new_listings,
                                price_drops,
                            ),
                            disable_web_page_preview=True,
                        )
                        logger.info(
                            "Car hits | key=%s | new=%d | drops=%d",
                            self.search_key,
                            len(new_listings),
                            len(price_drops),
                        )

                    self.known = {item.listing_id: item.price for item in current}
                    save_car_state(CAR_STATE_FILE, self.search_key, current)
                except Exception as exc:
                    logger.exception("Car search check failed for %s", self.search_key)
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"{t('notify_error_title', self.language)}\n{exc}",
                        )
                    except Exception:
                        logger.exception("Failed to send car error message")
        except asyncio.CancelledError:
            logger.info("Car search cancelled | key=%s", self.search_key)
            raise


class CarManager:
    def __init__(self) -> None:
        self._workers: dict[str, CarWorker] = {}

    @property
    def active_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.is_running)

    def active_keys(self) -> set[str]:
        return {key for key, worker in self._workers.items() if worker.is_running}

    def list_active(self) -> list[CarSearchInfo]:
        return [
            worker.info
            for worker in self._workers.values()
            if worker.is_running
        ]

    def is_running(self, search_key: str) -> bool:
        worker = self._workers.get(search_key)
        return worker is not None and worker.is_running

    async def start_config(self, config: dict, application: Application, chat_id: int) -> str:
        key = car_search_key_from_config(config)

        worker = self._workers.get(key)
        if worker and worker.is_running:
            return key

        self._workers[key] = CarWorker(key, config)
        await self._workers[key].start(application, chat_id)
        return key

    async def stop_key(self, search_key: str) -> bool:
        worker = self._workers.get(search_key)
        if worker is None or not worker.is_running:
            return False
        await worker.stop()
        return True

    async def stop_config(self, config: dict) -> bool:
        return await self.stop_key(car_search_key_from_config(config))

    async def stop_all(self) -> int:
        stopped = 0
        for worker in list(self._workers.values()):
            if worker.is_running:
                await worker.stop()
                stopped += 1
        return stopped


def get_car_manager(application: Application) -> CarManager:
    manager = application.bot_data.get("car_manager")
    if manager is None:
        manager = CarManager()
        application.bot_data["car_manager"] = manager
    return manager
