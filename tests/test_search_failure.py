import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from blocket_client import BlocketClient, listing_from_doc
from car_config import car_search_key_from_config
from car_monitor import clear_car_cache
from car_session import CarManager, CarWorker
from otomoto_client import CarSearchParams, IncompleteSearch, OtomotoClient

DOC = {
    "id": "23991025",
    "heading": "Volvo V60",
    "facade_title": "Volvo V60",
    "canonical_url": "https://www.blocket.se/mobility/item/23991025",
    "price": {"amount": 99900, "currency_code": "SEK"},
    "year": 2018,
    "mileage": 29170,
    "mileage_unit": "SCANDINAVIAN_MILE",
    "fuel": "Hybrid bensin",
    "transmission": "Automatisk",
    "location": "Borlänge",
    "image": {"url": "https://images.blocketcdn.se/dynamic/default/item/23991025/photo"},
}

FIXTURE = """
<div data-testid="search-results">
  <article data-id="615">
    <a data-nextlink="false" aria-label="Toyota Corolla 1.8 Hybrid"
       href="https://www.otomoto.pl/osobowe/oferta/toyota-corolla-ID6IiVzi.html">
      <img src="//ireland.apollo.olxcdn.com/v1/files/abc-OTOMOTOPL/image;s=320x240" />
    </a>
    <span translate="no">47 200</span>
    <dd data-parameter="year">2020</dd>
    <dd data-parameter="mileage">49 000 km</dd>
    <dd data-parameter="fuel_type">Hybryda</dd>
    <dd data-parameter="gearbox">Automatyczna</dd>
    <p>1798 cm3 • 122 KM</p>
    <p>Sobków (Świętokrzyskie)</p>
  </article>
</div>
"""


class _Response:
    def __init__(self, status: int = 200, text: str = "", payload: dict | None = None, broken: bool = False) -> None:
        self.status_code = status
        self.text = text
        self._payload = payload or {}
        self._broken = broken

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                "503 Server Error: Service Unavailable for url: https://www.blocket.se/mobility/search/api/search/SECRET"
            )

    def json(self) -> dict:
        if self._broken:
            raise ValueError("not json")
        return self._payload


def _page(params: object) -> str:
    if isinstance(params, list):
        return str(dict(params).get("page"))
    if isinstance(params, dict):
        return str(params.get("page"))
    return ""


class PartialPageTest(unittest.TestCase):
    def test_blocket_keeps_cars_found_before_a_later_page_fails(self) -> None:
        def fake_get(url: str, params: object, timeout: int) -> _Response:
            del url, timeout
            if _page(params) == "1":
                return _Response(payload={"docs": [DOC], "metadata": {"paging": {"last": 3}}})
            return _Response(status=503)

        client = BlocketClient()
        with patch.object(client.session, "get", side_effect=fake_get):
            with self.assertRaises(IncompleteSearch) as caught:
                client.get_listings(CarSearchParams(make="volvo", source="blocket"))
        self.assertEqual(caught.exception.page, 2)
        self.assertEqual(caught.exception.site, "Blocket")
        self.assertEqual([item.listing_id for item in caught.exception.listings], ["b23991025"])
        self.assertNotIn("http", str(caught.exception))

    def test_blocket_page_one_failure_has_no_cars(self) -> None:
        client = BlocketClient()
        with patch.object(client.session, "get", return_value=_Response(status=503)):
            with self.assertRaises(IncompleteSearch) as caught:
                client.get_listings(CarSearchParams(make="volvo", source="blocket"))
        self.assertEqual(caught.exception.page, 1)
        self.assertEqual(caught.exception.listings, [])

    def test_otomoto_keeps_cars_found_before_a_later_page_fails(self) -> None:
        def fake_get(url: str, params: object, timeout: int) -> _Response:
            del url, timeout
            if _page(params) == "1":
                return _Response(text=FIXTURE)
            return _Response(status=503)

        client = OtomotoClient()
        with patch.object(client.session, "get", side_effect=fake_get):
            with self.assertRaises(IncompleteSearch) as caught:
                client.get_listings(CarSearchParams(make="toyota"))
        self.assertEqual(caught.exception.page, 2)
        self.assertEqual([item.listing_id for item in caught.exception.listings], ["615"])


class CacheResetTest(unittest.TestCase):
    def test_clear_removes_every_search_and_hidden_car(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "car_state.json"
            path.write_text(
                json.dumps({"by_search": {"toyota|": {"listings": {"1": 100}, "delivered": True}}, "dismissed": ["b9"]}),
                encoding="utf-8",
            )
            clear_car_cache(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"by_search": {}, "dismissed": []})

    def test_running_search_drops_memory_when_the_cache_is_cleared_mid_check(self) -> None:
        listing = listing_from_doc(DOC)
        assert listing is not None
        config = {
            "car_make": "volvo",
            "car_source": "blocket",
            "car_poll_interval_seconds": 60,
            "language": "uk",
        }
        manager = CarManager()
        worker = CarWorker(car_search_key_from_config(config), config)
        worker.manager = manager
        worker.known = {"b1": 100}
        manager._workers[worker.search_key] = worker

        async def send_cards(application, chat_id, language, new_listings, price_drops):
            del application, chat_id, language, price_drops
            manager.forget_tracked()
            return new_listings, []

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "car_state.json"
            with (
                patch("car_session.CAR_STATE_FILE", path),
                patch("car_session.send_car_cards", send_cards),
            ):
                asyncio.run(worker._publish(object(), 1, [listing]))
            self.assertEqual(worker.known, {})
            self.assertFalse(path.exists())


class WorkerErrorTest(unittest.TestCase):
    def _run(self, outcome: object) -> tuple[list[str], list]:
        config = {
            "car_make": "volvo",
            "car_source": "blocket",
            "car_poll_interval_seconds": 60,
            "language": "uk",
        }
        worker = CarWorker(car_search_key_from_config(config), config)
        worker.stop_event = asyncio.Event()
        messages: list[str] = []
        published: list = []

        class Bot:
            async def send_message(self, chat_id: int, text: str) -> None:
                del chat_id
                messages.append(text)

        class App:
            bot = Bot()

        def fetch(params: object) -> list:
            del params
            worker.stop_event.set()
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        async def send_cards(application, chat_id, language, new_listings, price_drops):
            del application, chat_id, language, price_drops
            published.append(list(new_listings))
            return new_listings, []

        async def refresh(*args, **kwargs) -> None:
            del args, kwargs

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "car_state.json"
            with (
                patch("car_session.CAR_STATE_FILE", path),
                patch("car_session.BlocketClient.get_listings", side_effect=fetch),
                patch("car_session.send_car_cards", send_cards),
                patch("car_session.refresh_status_card", refresh),
            ):
                asyncio.run(worker._loop(App(), 7))
        return messages, published

    def test_failed_later_page_sends_the_cars_then_a_short_note(self) -> None:
        listing = listing_from_doc(DOC)
        assert listing is not None
        messages, published = self._run(IncompleteSearch([listing], "Blocket", 2))
        self.assertEqual(published, [[listing]])
        self.assertEqual(len(messages), 1)
        self.assertIn("сторінці 2", messages[0])
        self.assertIn("1", messages[0])
        self.assertNotIn("http", messages[0])
        self.assertNotIn("SECRET", messages[0])

    def test_total_failure_stays_short_and_sends_no_cars(self) -> None:
        messages, published = self._run(requests.HTTPError("503 for url: https://www.blocket.se/secret"))
        self.assertEqual(published, [])
        self.assertEqual(messages, ["Blocket не відповів. Цього разу авто не знайдено."])
        self.assertNotIn("http", messages[0])
