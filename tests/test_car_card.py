import asyncio
import unittest
from unittest.mock import patch

from otomoto_client import OtomotoClient
from ui_format import car_card_caption
from widget_sender import _send_car_card, send_car_cards

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
    <p>Prywatny sprzedawca • Podbite</p>
  </article>
</div>
"""


class CarCardTest(unittest.TestCase):
    def test_card_keeps_the_photo_place_and_facts(self) -> None:
        item = OtomotoClient().parse_listings(FIXTURE)[0]
        self.assertEqual(item.title, "Toyota Corolla 1.8 Hybrid")
        self.assertEqual(item.price, 47200)
        self.assertEqual(item.year, 2020)
        self.assertEqual(item.mileage, 49000)
        self.assertEqual(item.location, "Sobków (Świętokrzyskie)")
        self.assertEqual(
            item.image_url,
            "https://ireland.apollo.olxcdn.com/v1/files/abc-OTOMOTOPL/image;s=800x600",
        )

    def test_caption_has_info_and_a_link(self) -> None:
        item = OtomotoClient().parse_listings(FIXTURE)[0]
        caption = car_card_caption("uk", item)
        self.assertIn("Toyota Corolla 1.8 Hybrid", caption)
        self.assertIn("47\u2009200 zł", caption)
        self.assertIn("2020", caption)
        self.assertIn("49\u2009000 km", caption)
        self.assertIn("Hybryda", caption)
        self.assertIn("Automatyczna", caption)
        self.assertIn("Sobków (Świętokrzyskie)", caption)
        self.assertIn("Відкрити оголошення", caption)
        self.assertIn(item.url, caption)
        drop = car_card_caption("uk", item, 50000)
        self.assertIn("50\u2009000 → 47\u2009200 zł", drop)

    def test_photo_is_sent_with_the_caption(self) -> None:
        item = OtomotoClient().parse_listings(FIXTURE)[0]
        sent = []

        class Bot:
            async def send_photo(self, **kwargs):
                sent.append(kwargs)

            async def send_message(self, **kwargs):
                raise AssertionError("text fallback")

        class App:
            bot = Bot()

        with patch("widget_sender._download_photo", return_value=b"jpeg-bytes" * 100):
            asyncio.run(_send_car_card(App(), 1, car_card_caption("uk", item), item))
        self.assertEqual(sent[0]["caption"], car_card_caption("uk", item))
        self.assertEqual(sent[0]["parse_mode"], "HTML")
        self.assertTrue(sent[0]["photo"])

    def test_hide_choice_survives_the_next_save(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from car_monitor import dismiss_listing, load_dismissed, save_car_state

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "car_state.json"
            save_car_state(path, "toyota", {"1": 43050})
            dismiss_listing(path, "6150632529")
            save_car_state(path, "toyota", {"1": 40000})
            self.assertEqual(load_dismissed(path), {"6150632529"})
            dismiss_listing(path, "nope")
            self.assertEqual(load_dismissed(path), {"6150632529"})

    def test_banners_come_before_each_group(self) -> None:
        item = OtomotoClient().parse_listings(FIXTURE)[0]
        sent = []

        class Bot:
            async def send_message(self, **kwargs):
                sent.append(kwargs)

            async def send_photo(self, **kwargs):
                sent.append(kwargs)

        class App:
            bot = Bot()

        with patch("widget_sender._download_photo", return_value=b"jpeg-bytes" * 100):
            asyncio.run(send_car_cards(App(), 1, "uk", [item], [(item, 50000)]))
        self.assertEqual(sent[0]["text"], "---------- НОВІ МАШИНИ ----------")
        self.assertEqual(sent[1]["reply_markup"].inline_keyboard[0][0].callback_data, "hide:615")
        self.assertEqual(sent[2]["text"], "---------- НОВА ЦІНА ----------")
        self.assertEqual(sent[3]["reply_markup"].inline_keyboard[0][0].text, "Не показувати")

    def test_hide_adds_a_visible_mark(self) -> None:
        from telegram_bot import _hidden_body, _mark_car_hidden

        mark = "🚫 <b>Не показувати</b>"
        self.assertEqual(_hidden_body("🆕 car", mark), f"{mark}\n🆕 car")
        self.assertEqual(_hidden_body(f"{mark}\n🆕 car", mark), f"{mark}\n🆕 car")

        class Photo:
            photo = (object(),)
            caption_html = "🆕 car"
            text = None

        class Text:
            photo = ()
            text = "🆕 car"
            text_html = "🆕 car"

        class Query:
            def __init__(self, message):
                self.message = message
                self.edits = []

            async def edit_message_caption(self, **kwargs):
                self.edits.append(kwargs)

            async def edit_message_text(self, **kwargs):
                self.edits.append(kwargs)

        photo = Query(Photo())
        asyncio.run(_mark_car_hidden(photo, "uk"))
        self.assertEqual(photo.edits[0]["caption"], f"{mark}\n🆕 car")
        self.assertIsNone(photo.edits[0]["reply_markup"])

        text = Query(Text())
        asyncio.run(_mark_car_hidden(text, "uk"))
        self.assertEqual(text.edits[0]["text"], f"{mark}\n🆕 car")
        self.assertIsNone(text.edits[0]["reply_markup"])


if __name__ == "__main__":
    unittest.main()
