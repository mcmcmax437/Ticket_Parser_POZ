from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from blocket_client import SEARCH_URL, BlocketClient, FUEL_CODES
from otomoto_catalog import MILEAGES
from ui_format import FUEL_LABELS, GEARBOX_LABELS

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR / "blocket_catalog_cache.json"
_TTL_SECONDS = 6 * 60 * 60

PRICES = (
    "10000",
    "20000",
    "30000",
    "40000",
    "50000",
    "75000",
    "100000",
    "150000",
    "200000",
    "250000",
    "300000",
    "400000",
    "500000",
    "700000",
    "1000000",
    "1500000",
    "2000000",
)
YEARS = tuple(str(year) for year in range(2027, 1949, -1))
MILEAGE_LIMIT_KM = 200_000

_lock = threading.Lock()
_cache: dict | None = None
_cached_at = 0.0


def _models(make: dict) -> list[dict[str, str]]:
    options = []
    for series in make.get("filter_items") or []:
        series_id = str(series.get("value") or "")
        series_label = str(series.get("display_name") or series_id)
        if series_id:
            options.append({"id": series_id, "label": series_label})
        for model in series.get("filter_items") or []:
            model_id = str(model.get("value") or "")
            if not model_id:
                continue
            options.append({"id": model_id, "label": str(model.get("display_name") or model_id)})
    options.sort(key=lambda item: item["label"].casefold())
    return options


def catalog_from_filters(filters: list) -> dict:
    catalog = _fallback()
    by_name = {item.get("name"): item for item in filters if isinstance(item, dict)}
    variant = by_name.get("variant") or {}
    makes = []
    models: dict[str, list[dict[str, str]]] = {}
    for make in variant.get("filter_items") or []:
        make_id = str(make.get("value") or "")
        if not make_id.startswith("0."):
            continue
        makes.append({"id": make_id, "label": str(make.get("display_name") or make_id)})
        built = _models(make)
        if built:
            models[make_id] = built
    if not makes:
        raise ValueError("Blocket make list is empty")
    makes.sort(key=lambda item: item["label"].casefold())
    catalog["makes"] = makes
    catalog["models"] = models

    location = by_name.get("location") or {}
    regions = []
    for item in location.get("filter_items") or []:
        region_id = str(item.get("value") or "")
        if region_id.startswith("0."):
            regions.append({"id": region_id, "label": str(item.get("display_name") or region_id)})
    if regions:
        catalog["regions"] = regions
    return catalog


def _fallback() -> dict:
    mileages = [value for value in MILEAGES if int(value) <= MILEAGE_LIMIT_KM]
    return {
        "makes": [],
        "models": {},
        "regions": [],
        "years": list(YEARS),
        "prices": list(PRICES),
        "mileages": mileages,
        "fuels": [{"id": key, "label": FUEL_LABELS[key]} for key in FUEL_CODES if key in FUEL_LABELS],
        "gears": [{"id": key, "label": label} for key, label in GEARBOX_LABELS.items()],
    }


def _fetch() -> dict:
    response = BlocketClient().session.get(SEARCH_URL, params={"rows": 1}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    filters = payload.get("filters") if isinstance(payload, dict) else None
    if not isinstance(filters, list):
        raise ValueError("Blocket catalog is missing")
    return catalog_from_filters(filters)


def _read_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict) and data.get("makes"):
        return data
    return None


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
    try:
        CACHE_FILE.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Could not store the Blocket catalog", exc_info=True)
    return catalog


def catalog_or_fallback() -> dict:
    try:
        return load_catalog()
    except Exception:
        logger.warning("Blocket catalog unavailable", exc_info=True)
        cached = _read_cache()
        if cached is not None:
            return cached
        return _fallback()
