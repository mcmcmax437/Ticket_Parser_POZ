from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

from car_config import car_search_info, car_search_key_from_config, car_search_params_from_config
from car_sources import materialize_configs, prices_for_query
from car_monitor import (
    CAR_STATE_FILE,
    find_new_listings,
    find_price_drops,
    load_car_state,
    load_dismissed,
    remember_shown,
    save_car_state,
)
from i18n import normalize_language, t
from blocket_client import BlocketClient
from otomoto_client import CarListing, OtomotoClient
from widget_sender import refresh_status_card, send_car_cards

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

        self.known = load_car_state(CAR_STATE_FILE, self.search_key)
        logger.info(
            "Car search STARTED | key=%s | already_shown=%d",
            self.search_key,
            len(self.known),
        )

        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            self._loop(application, chat_id),
            name=f"car-{self.search_key[:24]}",
        )
        await refresh_status_card(application, chat_id, self.language)

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

    async def _publish(self, application: Application, chat_id: int, current: list[CarListing]) -> None:
        dismissed = load_dismissed(CAR_STATE_FILE)
        new_listings = [
            item for item in find_new_listings(current, self.known) if item.listing_id not in dismissed
        ]
        price_drops = [
            pair for pair in find_price_drops(current, self.known) if pair[0].listing_id not in dismissed
        ]
        sent_new: list[CarListing] = []
        sent_drops: list[tuple[CarListing, int]] = []
        if new_listings or price_drops:
            sent_new, sent_drops = await send_car_cards(
                application,
                chat_id,
                self.language,
                new_listings,
                price_drops,
            )
            logger.info(
                "Car hits | key=%s | new=%d | drops=%d",
                self.search_key,
                len(sent_new),
                len(sent_drops),
            )
        failed = {item.listing_id for item in new_listings}
        failed.update(item.listing_id for item, _previous in price_drops)
        failed.difference_update(item.listing_id for item in sent_new)
        failed.difference_update(item.listing_id for item, _previous in sent_drops)
        remembered = remember_shown(self.known, current)
        for listing_id in failed:
            if listing_id in self.known:
                remembered[listing_id] = self.known[listing_id]
            else:
                remembered.pop(listing_id, None)
        self.known = remembered
        save_car_state(CAR_STATE_FILE, self.search_key, self.known)

    async def _loop(self, application: Application, chat_id: int) -> None:
        try:
            first_check = True
            while self.stop_event and not self.stop_event.is_set():
                if not first_check:
                    for _ in range(self.poll_interval_seconds):
                        if self.stop_event.is_set():
                            break
                        await asyncio.sleep(1)
                first_check = False
                if self.stop_event.is_set():
                    break

                client = BlocketClient() if self.params.source == "blocket" else OtomotoClient()
                try:
                    current = await asyncio.to_thread(client.get_listings, prices_for_query(self.params))
                    await self._publish(application, chat_id, current)
                    await refresh_status_card(application, chat_id, self.language)
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

    async def start_config(self, config: dict, application: Application, chat_id: int) -> list[str]:
        keys: list[str] = []
        configs = materialize_configs(config)
        if any(cfg.get("car_source") == "blocket" and (cfg.get("car_price_from") or cfg.get("car_price_to")) for cfg in configs):
            try:
                from fx import pln_per_sek

                pln_per_sek()
            except Exception as exc:
                raise ValueError("Could not convert zł to kr right now") from exc
        for cfg in configs:
            if not str(cfg.get("car_make") or "").strip():
                raise ValueError("Enter the car make first")
            key = car_search_key_from_config(cfg)
            keys.append(key)
            worker = self._workers.get(key)
            if worker and worker.is_running:
                continue
            self._workers[key] = CarWorker(key, cfg)
            await self._workers[key].start(application, chat_id)
        return keys

    async def stop_key(self, search_key: str) -> bool:
        worker = self._workers.get(search_key)
        if worker is None or not worker.is_running:
            return False
        await worker.stop()
        return True

    async def stop_config(self, config: dict) -> bool:
        try:
            configs = materialize_configs(config)
        except ValueError:
            configs = [config]
        stopped = False
        for cfg in configs:
            if await self.stop_key(car_search_key_from_config(cfg)):
                stopped = True
        return stopped

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
