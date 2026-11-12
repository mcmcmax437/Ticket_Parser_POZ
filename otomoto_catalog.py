from __future__ import annotations

import json
import logging
import re
import threading
import time

from otomoto_client import BASE_URL, OtomotoClient

logger = logging.getLogger(__name__)

REGIONS = (
    ("mazowieckie", "Mazowieckie"),
    ("wielkopolskie", "Wielkopolskie"),
    ("slaskie", "Śląskie"),
    ("malopolskie", "Małopolskie"),
    ("dolnoslaskie", "Dolnośląskie"),
    ("pomorskie", "Pomorskie"),
    ("lodzkie", "Łódzkie"),
    ("kujawsko-pomorskie", "Kujawsko-pomorskie"),
    ("zachodniopomorskie", "Zachodniopomorskie"),
    ("lubelskie", "Lubelskie"),
    ("podkarpackie", "Podkarpackie"),
    ("swietokrzyskie", "Świętokrzyskie"),
    ("lubuskie", "Lubuskie"),
    ("warminsko-mazurskie", "Warmińsko-mazurskie"),
    ("podlaskie", "Podlaskie"),
    ("opolskie", "Opolskie"),
)
YEARS = tuple(str(year) for year in range(2027, 1989, -1)) + (
    "1980",
    "1970",
    "1960",
    "1950",
    "1940",
    "1930",
    "1920",
    "1910",
    "1900",
)
PRICES = (
    "2000",
    "3000",
    "5000",
    "10000",
    "15000",
    "20000",
    "25000",
    "30000",
    "35000",
    "40000",
    "50000",
    "65000",
    "80000",
    "100000",
    "200000",
    "500000",
    "1000000",
    "7500000",
)
MILEAGES = (
    "20000",
    "35000",
    "50000",
    "75000",
    "100000",
    "125000",
    "150000",
    "170000",
    "175000",
    "180000",
    "200000",
    "250000",
)

_lock = threading.Lock()
_cache: dict | None = None
_cached_at = 0.0
_TTL_SECONDS = 6 * 60 * 60


def _option_values(state: dict) -> list[dict[str, str]]:
    options = []
    for group in state.get("values") or []:
        for item in group.get("values") or []:
            slug = str(item.get("id") or "").strip()
            if not slug:
                continue
            label = str(item.get("name") or slug).strip() or slug
            options.append({"id": slug, "label": label})
    return options


def _walk_states(node, found: list) -> None:
    if isinstance(node, dict):
        if node.get("__typename") == "OpenForInputFilterState":
            found.append(node)
        for value in node.values():
            _walk_states(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_states(item, found)


def _fallback() -> dict:
    return {
        "makes": [],
        "models": {},
        "regions": [{"id": slug, "label": label} for slug, label in REGIONS],
        "years": list(YEARS),
        "prices": list(PRICES),
        "mileages": list(MILEAGES),
    }


def _fetch() -> dict:
    response = OtomotoClient().session.get(f"{BASE_URL}/osobowe", timeout=30)
    response.raise_for_status()
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text)
    if not match:
        raise ValueError("Otomoto page has no catalog")
    page = json.loads(match.group(1))
    payload = None
    for value in page["props"]["pageProps"]["urqlState"].values():
        raw = value.get("data") if isinstance(value, dict) else None
        if isinstance(raw, str) and "OpenForInputFilterState" in raw and "filter_enum_make" in raw:
            payload = json.loads(raw)
            break
    if payload is None:
        raise ValueError("Otomoto catalog is missing")

    states: list[dict] = []
    _walk_states(payload, states)
    catalog = _fallback()
    for state in states:
        filter_id = state.get("filterId")
        options = _option_values(state)
        if not options:
            continue
        if filter_id == "filter_enum_make":
            catalog["makes"] = options
        elif filter_id == "filter_enum_model":
            make = ""
            for condition in state.get("conditions") or []:
                if condition.get("filterId") == "filter_enum_make":
                    make = str(condition.get("value") or "")
            if make:
                catalog["models"][make] = options
        elif filter_id == "filter_float_year":
            catalog["years"] = [item["id"] for item in options]
        elif filter_id == "filter_float_price":
            catalog["prices"] = [item["id"] for item in options]
        elif filter_id == "filter_float_mileage":
            catalog["mileages"] = [item["id"] for item in options]
    if not catalog["makes"]:
        raise ValueError("Otomoto make list is empty")
    return catalog


def load_catalog() -> dict:
    global _cache, _cached_at
    now = time.time()
    with _lock:
        if _cache is not None and now - _cached_at < _TTL_SECONDS:
            return _cache
    catalog = _fetch()
    with _lock:
        _cache = catalog
        _cached_at = time.time()
        return catalog


def catalog_or_fallback() -> dict:
    try:
        return load_catalog()
    except Exception:
        logger.warning("Otomoto catalog unavailable", exc_info=True)
        fallback = _fallback()
        fallback["error"] = "Car list is unavailable"
        return fallback
