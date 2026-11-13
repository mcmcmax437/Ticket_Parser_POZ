import unittest
from unittest.mock import patch

from car_config import car_search_key, car_search_params_from_config, parse_price, parse_tolerance
from otomoto_client import CarListing, CarSearchParams, OtomotoClient, accepted_price_bounds, listing_within_filters
from ui_format import _price_part
from car_config import CarSearchInfo


def _offer(price: int) -> CarListing:
    return CarListing(
        listing_id="1",
        title="Toyota Corolla",
        url="https://www.otomoto.pl/osobowe/oferta/toyota-corolla-ID6IhpCY.html",
        price=price,
        year=2020,
        mileage=126132,
        fuel_type="Hybryda",
        gearbox="Automatyczna",
    )


def _search(**overrides) -> CarSearchParams:
    params = dict(
        make="toyota",
        model="corolla",
        year_from=2018,
        price_from=40000,
        price_to=50000,
        fuel_type="hybrid",
        gearbox="automatic",
        price_tolerance=10,
    )
    params.update(overrides)
    return CarSearchParams(**params)


class PriceWindowTest(unittest.TestCase):
    def test_ten_percent_widens_both_sides(self) -> None:
        self.assertEqual(accepted_price_bounds(_search()), (36000, 55000))

    def test_zero_tolerance_keeps_the_stated_price(self) -> None:
        self.assertEqual(accepted_price_bounds(_search(price_tolerance=0)), (40000, 50000))

    def test_manual_price_and_tolerance_come_from_config(self) -> None:
        params = car_search_params_from_config(
            {"car_make": "toyota", "car_price_from": "47500", "car_price_to": "52000", "car_price_tolerance": "10"}
        )
        self.assertEqual((params.price_from, params.price_to, params.price_tolerance), (47500, 52000, 10))
        self.assertIn("47500", car_search_key(params))
        self.assertIn("10", car_search_key(params))

    def test_typed_price_accepts_amounts_outside_the_preset_steps(self) -> None:
        self.assertEqual(parse_price("47 500"), "47500")
        self.assertEqual(parse_price(""), "")
        self.assertEqual(parse_tolerance("10%"), "10")
        self.assertEqual(parse_tolerance(""), "0")
        with self.assertRaises(ValueError):
            parse_price("0")
        with self.assertRaises(ValueError):
            parse_tolerance("101")

    def test_offer_just_outside_the_cap_is_kept_only_inside_the_tolerance(self) -> None:
        self.assertTrue(listing_within_filters(_offer(54000), _search()))
        self.assertTrue(listing_within_filters(_offer(36000), _search()))
        self.assertTrue(listing_within_filters(_offer(55000), _search()))
        self.assertFalse(listing_within_filters(_offer(92900), _search()))
        self.assertFalse(listing_within_filters(_offer(35999), _search()))
        self.assertFalse(listing_within_filters(_offer(55001), _search()))
        self.assertFalse(listing_within_filters(_offer(54000), _search(price_tolerance=0)))

    def test_missing_price_stays_outside_when_a_limit_is_set(self) -> None:
        offer = _offer(54000)
        offer = CarListing(**{**offer.__dict__, "price": None})
        self.assertFalse(listing_within_filters(offer, _search()))

    def test_otomoto_query_uses_the_widened_limits(self) -> None:
        query = OtomotoClient().search_params(_search())
        self.assertEqual(query["search[filter_float_price:from]"], 36000)
        self.assertEqual(query["search[filter_float_price:to]"], 55000)
        exact = OtomotoClient().search_params(_search(price_tolerance=0))
        self.assertEqual(exact["search[filter_float_price:from]"], 40000)
        self.assertEqual(exact["search[filter_float_price:to]"], 50000)
        self.assertNotIn("search[filter_enum_damaged]", exact)
        undamaged = OtomotoClient().search_params(_search(damaged="0"))
        self.assertEqual(undamaged["search[filter_enum_damaged]"], "0")
        self.assertEqual(car_search_key(_search()), car_search_key(_search(damaged="")))
        self.assertNotEqual(car_search_key(_search()), car_search_key(_search(damaged="1")))

    def test_summary_shows_the_tolerance(self) -> None:
        info = CarSearchInfo(
            search_key="k",
            make="toyota",
            model="corolla",
            region="",
            year_from="2018",
            year_to="",
            price_from="40000",
            price_to="50000",
            price_tolerance="10",
            mileage_to="",
            fuel_type="",
            gearbox="",
            poll_interval_seconds=900,
            language="uk",
        )
        self.assertIn("±10%", _price_part(info))

    def test_api_accepts_a_typed_price_and_tolerance(self) -> None:
        catalog = {
            "makes": [],
            "models": {},
            "regions": [],
            "years": ["2018"],
            "prices": ["40000", "50000"],
            "mileages": ["150000"],
        }
        current = {
            "car_make": "toyota",
            "car_model": "",
            "car_region": "",
            "car_year_from": "",
            "car_year_to": "",
            "car_price_from": "40000",
            "car_price_to": "50000",
            "car_mileage_to": "",
            "car_price_tolerance": "0",
        }
        with patch("webapp_server.catalog_or_fallback", return_value=catalog), patch(
            "webapp_server.load_user_config", return_value=current
        ):
            from webapp_server import _clean_patch

            saved = _clean_patch({"car_price_from": "47500", "car_price_tolerance": "10"})
            self.assertEqual(saved["car_price_from"], "47500")
            self.assertEqual(saved["car_price_tolerance"], "10")
            with self.assertRaises(ValueError):
                _clean_patch({"car_price_to": "30000"})
            with self.assertRaises(ValueError):
                _clean_patch({"car_price_tolerance": "150"})
            with self.assertRaises(ValueError):
                _clean_patch({"car_year_from": "2011"})


if __name__ == "__main__":
    unittest.main()
