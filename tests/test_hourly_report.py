import asyncio
import unittest
from unittest.mock import patch

from blocket_client import BlocketClient
from car_config import car_search_key_from_config
from car_session import CarManager, CarWorker
from otomoto_client import CarSearchParams, OtomotoClient
from tests.test_search_failure import DOC, FIXTURE, _Response, _page
from ui_format import hourly_report_html


def _config() -> dict:
    return {
        "car_make": "volvo",
        "car_model": "v60",
        "car_source": "otomoto",
        "car_poll_interval_seconds": 60,
        "language": "uk",
    }


class FilterCountTest(unittest.TestCase):
    def test_blocket_counts_cars_outside_the_price(self) -> None:
        expensive = {
            **DOC,
            "id": "300",
            "price": {"amount": 200000, "currency_code": "SEK"},
        }

        def fake_get(url: str, params: object, timeout: int) -> _Response:
            del url, timeout
            if _page(params) == "1":
                return _Response(payload={"docs": [DOC, expensive], "metadata": {"paging": {"last": 1}}})
            return _Response(payload={"docs": []})

        client = BlocketClient()
        with patch.object(client.session, "get", side_effect=fake_get):
            batch = client.get_listings(CarSearchParams(make="volvo", source="blocket", price_to=100000))
        self.assertEqual([item.listing_id for item in batch.listings], ["b23991025"])
        self.assertEqual(batch.reviewed, ("b23991025", "b300"))
        self.assertEqual(batch.rejected, ("b300",))

    def test_otomoto_counts_a_car_the_make_filter_drops(self) -> None:
        extra = """
        <article data-id="700">
          <a data-nextlink="false" aria-label="Skoda Octavia"
             href="https://www.otomoto.pl/osobowe/oferta/skoda-octavia-ID6IiVza.html">
            <img src="//ireland.apollo.olxcdn.com/v1/files/abc-OTOMOTOPL/image;s=320x240" />
          </a>
          <span translate="no">12 000</span>
        </article>
        """
        body = FIXTURE.replace("</div>", extra + "</div>")

        def fake_get(url: str, params: object, timeout: int) -> _Response:
            del url, timeout
            if _page(params) == "1":
                return _Response(text=body)
            return _Response(text="<html></html>")

        client = OtomotoClient()
        with patch.object(client.session, "get", side_effect=fake_get):
            batch = client.get_listings(CarSearchParams(make="toyota"))
        self.assertEqual([item.listing_id for item in batch.listings], ["615"])
        self.assertEqual(batch.reviewed, ("615", "700"))
        self.assertEqual(batch.rejected, ("700",))


class HourlyReportTest(unittest.TestCase):
    def test_same_car_is_counted_once_and_a_later_pass_clears_the_rejection(self) -> None:
        worker = CarWorker(car_search_key_from_config(_config()), _config())
        worker.note_listings(("1", "2"), ("2",))
        worker.note_listings(("2", "3"), ())
        self.assertEqual((worker.seen_ids, worker.rejected_ids), ({"1", "2", "3"}, set()))
        worker.note_listings(("3",), ("3",))
        self.assertEqual(worker.rejected_ids, {"3"})

    def test_report_names_the_search_and_both_counts(self) -> None:
        worker = CarWorker(car_search_key_from_config(_config()), _config())
        text = hourly_report_html("uk", [(worker.info, 12, 4)])
        self.assertIn("Годинний звіт", text)
        self.assertIn("volvo", text)
        self.assertIn("Переглянуто: 12", text)
        self.assertIn("Не пройшли фільтрацію: 4", text)

    def test_running_search_sends_the_hour_then_starts_again_from_zero(self) -> None:
        manager = CarManager()
        manager.report_every = 0.05
        worker = CarWorker(car_search_key_from_config(_config()), _config())
        worker.note_listings(("10", "11"), ("11",))
        manager._workers[worker.search_key] = worker
        messages: list[str] = []

        class Bot:
            async def send_message(self, chat_id: int, text: str, parse_mode: str) -> None:
                del chat_id, parse_mode
                messages.append(text)

        class App:
            bot = Bot()

        async def run() -> None:
            worker.task = asyncio.create_task(asyncio.sleep(30))
            manager._arm_reporter(App(), 5)
            try:
                for _ in range(40):
                    if len(messages) >= 2:
                        break
                    await asyncio.sleep(0.03)
            finally:
                if worker.task and not worker.task.done():
                    worker.task.cancel()
                    try:
                        await worker.task
                    except asyncio.CancelledError:
                        pass
                await manager._cancel_reporter_if_idle()

        asyncio.run(run())
        self.assertGreaterEqual(len(messages), 2)
        self.assertIn("Переглянуто: 2", messages[0])
        self.assertIn("Не пройшли фільтрацію: 1", messages[0])
        self.assertIn("Переглянуто: 0", messages[1])
        self.assertIn("Не пройшли фільтрацію: 0", messages[1])
        self.assertEqual(worker.seen_ids, set())
