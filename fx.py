from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# NBP table A: how many PLN one Swedish krona costs.
NBP_SEK_URL = "https://api.nbp.pl/api/exchangerates/rates/a/sek/?format=json"
CACHE_FILE = Path(__file__).resolve().parent / "fx_cache.json"
_TTL_SECONDS = 12 * 60 * 60

_lock = threading.Lock()
_rate: float | None = None
_cached_at = 0.0


def _fetch_rate() -> float:
    response = requests.get(NBP_SEK_URL, headers={"Accept": "application/json"}, timeout=20)
    response.raise_for_status()
    rate = float(response.json()["rates"][0]["mid"])
    if rate <= 0:
        raise ValueError("SEK rate is not usable")
    return rate


def _read_cache() -> tuple[float, float] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        rate = float(data["pln_per_sek"])
        saved_at = float(data["at"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if rate <= 0:
        return None
    return rate, saved_at


def pln_per_sek() -> float:
    """PLN paid for 1 SEK. Divide a zloty amount by this to get kronor."""
    global _rate, _cached_at
    now = time.time()
    with _lock:
        if _rate is not None and now - _cached_at < _TTL_SECONDS:
            return _rate
    try:
        rate = _fetch_rate()
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logger.warning("Could not refresh the SEK rate", exc_info=True)
        cached = _read_cache()
        if cached is None:
            raise
        rate, saved_at = cached
        with _lock:
            _rate = rate
            _cached_at = saved_at
        return rate
    with _lock:
        _rate = rate
        _cached_at = time.time()
    try:
        CACHE_FILE.write_text(
            json.dumps({"pln_per_sek": rate, "at": _cached_at}),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Could not store the SEK rate", exc_info=True)
    return rate


def to_sek(amount: int | None) -> int | None:
    if amount is None:
        return None
    if amount <= 0:
        return 0
    return max(1, int(amount / pln_per_sek() + 0.5))
