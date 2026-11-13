from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from otomoto_client import CarListing

logger = logging.getLogger(__name__)

UTC = timezone.utc

BASE_DIR = Path(__file__).resolve().parent
CAR_STATE_FILE = BASE_DIR / "car_state.json"


def find_new_listings(current: list[CarListing], known: dict[str, int | None]) -> list[CarListing]:
    return [item for item in current if item.listing_id not in known]


def find_price_drops(current: list[CarListing], known: dict[str, int | None]) -> list[tuple[CarListing, int]]:
    drops: list[tuple[CarListing, int]] = []
    for item in current:
        previous = known.get(item.listing_id)
        if previous is None or item.price is None or item.price >= previous:
            continue
        drops.append((item, previous))
    return drops


def remember_shown(
    known: dict[str, int | None],
    listings: list[CarListing],
) -> dict[str, int | None]:
    remembered = dict(known)
    for item in listings:
        remembered[item.listing_id] = item.price
    return remembered


def load_car_state(path: Path, search_key: str) -> dict[str, int | None]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        by_search = data.get("by_search", {})
        entry = by_search.get(search_key, {})
        # Older files recorded a silent baseline. Those offers were never sent.
        if not entry.get("delivered"):
            return {}
        listings = entry.get("listings", {})
        if not isinstance(listings, dict):
            return {}
        return {
            str(key): (int(value) if isinstance(value, int) else None)
            for key, value in listings.items()
        }
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read car state file, starting fresh: %s", exc)
        return {}


def save_car_state(path: Path, search_key: str, listings: list[CarListing] | dict[str, int | None]) -> None:
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    by_search = existing.get("by_search", {})
    if not isinstance(by_search, dict):
        by_search = {}
    if isinstance(listings, dict):
        stored = {
            str(key): (int(value) if isinstance(value, int) else None)
            for key, value in listings.items()
        }
    else:
        stored = {item.listing_id: item.price for item in listings}
    by_search[search_key] = {
        "listings": stored,
        "delivered": True,
        "last_check": datetime.now(UTC).isoformat(),
    }

    path.write_text(json.dumps({"by_search": by_search}, ensure_ascii=False, indent=2), encoding="utf-8")
