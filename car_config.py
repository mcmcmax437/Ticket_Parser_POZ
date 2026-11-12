from __future__ import annotations

import re
from dataclasses import dataclass

from config_store import load_user_config
from i18n import normalize_language
from otomoto_client import CarSearchParams

PRICE_MAX = 20_000_000

CAR_CONFIG_KEYS = (
    "car_make",
    "car_model",
    "car_region",
    "car_year_from",
    "car_year_to",
    "car_price_from",
    "car_price_to",
    "car_price_tolerance",
    "car_mileage_to",
    "car_fuel_type",
    "car_gearbox",
)

CAR_FIELD_LABELS = {
    "car_make": "label_car_make",
    "car_model": "label_car_model",
    "car_region": "label_car_region",
    "car_year_from": "label_car_year_from",
    "car_year_to": "label_car_year_to",
    "car_price_from": "label_car_price_from",
    "car_price_to": "label_car_price_to",
    "car_price_tolerance": "label_car_price_tolerance",
    "car_mileage_to": "label_car_mileage_to",
    "car_fuel_type": "label_car_fuel_type",
    "car_gearbox": "label_car_gearbox",
}


def _as_int(value: object) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    return int(raw)


def parse_price(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    number = int(digits)
    if number < 1 or number > PRICE_MAX:
        raise ValueError(f"Price must be from 1 to {PRICE_MAX}")
    return str(number)


def parse_tolerance(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return "0"
    number = int(digits)
    if number > 100:
        raise ValueError("Tolerance must be from 0 to 100")
    return str(number)


def car_search_params_from_config(config: dict) -> CarSearchParams:
    return CarSearchParams(
        make=str(config.get("car_make") or "").strip(),
        model=str(config.get("car_model") or "").strip(),
        region=str(config.get("car_region") or "").strip(),
        year_from=_as_int(config.get("car_year_from")),
        year_to=_as_int(config.get("car_year_to")),
        price_from=_as_int(config.get("car_price_from")),
        price_to=_as_int(config.get("car_price_to")),
        price_tolerance=_as_int(config.get("car_price_tolerance")) or 0,
        mileage_to=_as_int(config.get("car_mileage_to")),
        fuel_type=str(config.get("car_fuel_type") or "").strip(),
        gearbox=str(config.get("car_gearbox") or "").strip(),
    )


def car_search_key(params: CarSearchParams) -> str:
    return "|".join(
        str(v or "")
        for v in (
            params.make,
            params.model,
            params.region,
            params.year_from,
            params.year_to,
            params.price_from,
            params.price_to,
            params.price_tolerance,
            params.mileage_to,
            params.fuel_type,
            params.gearbox,
        )
    )


def car_search_key_from_config(config: dict) -> str:
    return car_search_key(car_search_params_from_config(config))


@dataclass(frozen=True)
class CarSearchInfo:
    search_key: str
    make: str
    model: str
    region: str
    year_from: str
    year_to: str
    price_from: str
    price_to: str
    price_tolerance: str
    mileage_to: str
    fuel_type: str
    gearbox: str
    poll_interval_seconds: int
    language: str


def car_search_info(config: dict, search_key: str) -> CarSearchInfo:
    params = car_search_params_from_config(config)
    return CarSearchInfo(
        search_key=search_key,
        make=params.make,
        model=params.model,
        region=params.region,
        year_from=str(config.get("car_year_from") or ""),
        year_to=str(config.get("car_year_to") or ""),
        price_from=str(config.get("car_price_from") or ""),
        price_to=str(config.get("car_price_to") or ""),
        price_tolerance=parse_tolerance(config.get("car_price_tolerance")),
        mileage_to=str(config.get("car_mileage_to") or ""),
        fuel_type=params.fuel_type,
        gearbox=params.gearbox,
        poll_interval_seconds=int(config["car_poll_interval_seconds"]),
        language=normalize_language(str(config.get("language", "en"))),
    )


def current_car_config_active(active_keys: set[str]) -> bool:
    return car_search_key_from_config(load_user_config()) in active_keys
