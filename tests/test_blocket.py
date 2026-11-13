import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from blocket_catalog import catalog_from_filters
from blocket_client import BlocketClient, listing_from_doc
from car_config import CarSearchInfo, car_search_key, car_search_params_from_config
from car_sources import materialize_configs, prices_for_query
from car_monitor import dismiss_listing, load_dismissed
from otomoto_client import CarSearchParams, listing_within_filters
from ui_format import _price_part


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

FILTERS = [
    {
        "name": "variant",
        "filter_items": [
            {
                "display_name": "Volvo",
                "value": "0.818",
                "filter_items": [
                    {
                        "display_name": "V60-Serie",
                        "value": "1.818.2843",
                        "filter_items": [{"display_name": "V60", "value": "2.818.2843.9", "filter_items": []}],
                    }
                ],
            }
        ],
    },
    {
        "name": "location",
        "filter_items": [
            {"display_name": "Stockholm", "value": "0.300001", "filter_items": []},
        ],
    },
]


def _blocket(**overrides) -> CarSearchParams:
    params = dict(
        make="0.818",
        model="1.818.2843",
        region="0.300001",
        year_from=2018,
        price_from=80000,
        price_to=200000,
        price_tolerance=10,
        mileage_to=200000,
        fuel_type="hybrid",
        gearbox="automatic",
        source="blocket",
    )
    params.update(overrides)
    return CarSearchParams(**params)


class BlocketSearchTest(unittest.TestCase):
    def test_listing_uses_kronor_and_kilometers(self) -> None:
        item = listing_from_doc(DOC)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.listing_id, "b23991025")
        self.assertEqual(item.price, 99900)
        self.assertEqual(item.currency, "kr")
        self.assertEqual(item.mileage, 291700)
        self.assertEqual(item.url, "https://www.blocket.se/mobility/item/23991025")
        leased = dict(DOC)
        leased["sales_form"] = 5
        self.assertIsNone(listing_from_doc(leased))

    def test_query_converts_kilometers_and_repeats_hybrid_fuels(self) -> None:
        query = BlocketClient().search_params(_blocket())
        self.assertIn(("variant", "1.818.2843"), query)
        self.assertIn(("mileage_to", "20000"), query)
        self.assertIn(("price_from", "72000"), query)
        self.assertIn(("price_to", "220000"), query)
        self.assertIn(("fuel", "6"), query)
        self.assertIn(("fuel", "8"), query)
        self.assertIn(("transmission", "2"), query)
        self.assertIn(("location", "0.300001"), query)
        self.assertNotIn("damaged", {name for name, _value in query})

    def test_swedish_hybrid_stays_inside_the_filter(self) -> None:
        item = listing_from_doc(DOC)
        assert item is not None
        self.assertTrue(listing_within_filters(item, _blocket(price_tolerance=0, mileage_to=300000)))
        self.assertFalse(listing_within_filters(item, _blocket(fuel_type="diesel")))

    def test_blocket_key_is_separate_and_priced_in_kronor(self) -> None:
        self.assertTrue(car_search_key(_blocket()).startswith("blocket|"))
        self.assertFalse(car_search_key(_blocket(source="")).startswith("blocket|"))
        info = CarSearchInfo(
            search_key="k",
            make="0.818",
            model="",
            region="",
            year_from="",
            year_to="",
            price_from="80000",
            price_to="200000",
            price_tolerance="0",
            mileage_to="",
            fuel_type="",
            gearbox="",
            poll_interval_seconds=900,
            language="uk",
            source="blocket",
        )
        with patch("fx.pln_per_sek", return_value=0.4):
            text = _price_part(info)
        self.assertIn("zł", text)
        self.assertIn("200\u2009000–500\u2009000 kr", text)

    def test_catalog_keeps_make_series_and_county(self) -> None:
        catalog = catalog_from_filters(FILTERS)
        self.assertEqual(catalog["makes"], [{"id": "0.818", "label": "Volvo"}])
        self.assertEqual(catalog["models"]["0.818"][0]["label"], "V60")
        self.assertEqual(catalog["regions"], [{"id": "0.300001", "label": "Stockholm"}])
        self.assertNotIn("petrol-lpg", {item["id"] for item in catalog["fuels"]})

    def test_one_zloty_price_starts_both_sites(self) -> None:
        otomoto = {
            "makes": [{"id": "toyota", "label": "Toyota"}],
            "models": {"toyota": [{"id": "corolla", "label": "Corolla"}]},
            "regions": [{"id": "mazowieckie", "label": "Mazowieckie"}],
        }
        blocket = {
            "makes": [{"id": "0.813", "label": "Toyota"}],
            "models": {"0.813": [{"id": "1.9", "label": "Corolla"}]},
            "regions": [{"id": "0.300001", "label": "Stockholm"}],
        }
        config = {
            "car_source": "blocket,otomoto",
            "car_make": "toyota",
            "car_model": "corolla",
            "car_region": "mazowieckie",
            "car_price_from": "40000",
            "car_price_to": "50000",
            "car_damaged": "0",
        }
        with (
            patch("car_sources.otomoto_catalog", return_value=otomoto),
            patch("car_sources.blocket_catalog", return_value=blocket),
            patch("fx.pln_per_sek", return_value=0.4),
        ):
            configs = materialize_configs(config)
            self.assertEqual([item["car_source"] for item in configs], ["otomoto", "blocket"])
            self.assertEqual(configs[1]["car_make"], "0.813")
            self.assertEqual(configs[1]["car_model"], "1.9")
            self.assertEqual(configs[1]["car_region"], "")
            self.assertEqual(configs[1]["car_damaged"], "")
            self.assertEqual(configs[0]["car_region"], "mazowieckie")
            queried = prices_for_query(car_search_params_from_config(configs[1]))
            self.assertEqual((queried.price_from, queried.price_to), (100000, 125000))
            self.assertIn("40000", car_search_key(car_search_params_from_config(configs[1])))
            self.assertNotIn("|100000|", car_search_key(car_search_params_from_config(configs[1])))

    def test_hidden_blocket_car_is_remembered(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "car_state.json"
            dismiss_listing(path, "b23991025")
            dismiss_listing(path, "nope")
            self.assertEqual(load_dismissed(path), {"b23991025"})


if __name__ == "__main__":
    unittest.main()
