from __future__ import annotations

import logging

import requests

from otomoto_client import (
    CarListing,
    CarSearchParams,
    IncompleteSearch,
    accepted_price_bounds,
    listing_within_filters,
)

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.blocket.se/mobility/search/api/search/SEARCH_ID_CAR_USED"
MAX_PAGES = 8
PAGE_SIZE = 50

# Blocket fuel ids. Hybrid and plug-in each cover more than one of their labels.
FUEL_CODES = {
    "petrol": ("1",),
    "diesel": ("2",),
    "electric": ("4",),
    "hybrid": ("6", "8", "5"),
    "plugin-hybrid": ("1352", "1356"),
}
GEAR_CODES = {"manual": "1", "automatic": "2"}


class BlocketClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "Accept": "application/json",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.6",
            }
        )

    def search_params(self, params: CarSearchParams) -> list[tuple[str, str]]:
        query: list[tuple[str, str]] = [
            ("sort", "PUBLISHED_DESC"),
            ("rows", str(PAGE_SIZE)),
        ]
        variant = params.model or params.make
        if variant:
            query.append(("variant", variant))
        if params.year_from:
            query.append(("year_from", str(params.year_from)))
        if params.year_to:
            query.append(("year_to", str(params.year_to)))
        low, high = accepted_price_bounds(params)
        if low:
            query.append(("price_from", str(low)))
        if high:
            query.append(("price_to", str(high)))
        if params.mileage_to:
            query.append(("mileage_to", str(params.mileage_to // 10)))
        for code in FUEL_CODES.get(params.fuel_type, ()):
            query.append(("fuel", code))
        gear = GEAR_CODES.get(params.gearbox, "")
        if gear:
            query.append(("transmission", gear))
        if params.region:
            query.append(("location", params.region))
        return query

    def get_listings(self, params: CarSearchParams) -> list[CarListing]:
        query = self.search_params(params)
        listings: list[CarListing] = []
        seen: set[str] = set()
        failed_page: int | None = None
        for page in range(1, MAX_PAGES + 1):
            try:
                response = self.session.get(SEARCH_URL, params=[*query, ("page", str(page))], timeout=30)
                response.raise_for_status()
                payload = response.json()
            except Exception:
                logger.warning("Blocket search stopped on page %s", page, exc_info=True)
                failed_page = page
                break
            docs = payload.get("docs") if isinstance(payload, dict) else None
            if not isinstance(docs, list) or not docs:
                break
            fresh = []
            for doc in docs:
                item = listing_from_doc(doc)
                if item is None or item.listing_id in seen:
                    continue
                seen.add(item.listing_id)
                fresh.append(item)
            if not fresh:
                break
            listings.extend(fresh)
            paging = (payload.get("metadata") or {}).get("paging") or {}
            last = paging.get("last")
            if isinstance(last, int) and page >= last:
                break
        kept = [item for item in listings if listing_within_filters(item, params)]
        if len(kept) != len(listings):
            logger.info(
                "Dropped %d Blocket offers outside the car filters | make=%s | model=%s",
                len(listings) - len(kept),
                params.make,
                params.model,
            )
        if failed_page is not None:
            raise IncompleteSearch(kept, "Blocket", failed_page)
        return kept


def listing_from_doc(doc: object) -> CarListing | None:
    if not isinstance(doc, dict):
        return None
    raw_id = str(doc.get("id") or "").strip()
    if not raw_id.isdigit():
        return None
    # sales_form 5 is leasing. Its amount is a monthly payment, not the car price.
    if doc.get("sales_form") == 5:
        return None
    price = doc.get("price") if isinstance(doc.get("price"), dict) else {}
    amount = price.get("amount")
    miles = doc.get("mileage")
    image = doc.get("image") if isinstance(doc.get("image"), dict) else {}
    title = str(doc.get("facade_title") or doc.get("heading") or "").strip()
    return CarListing(
        listing_id=f"b{raw_id}",
        title=title or raw_id,
        url=str(doc.get("canonical_url") or f"https://www.blocket.se/mobility/item/{raw_id}"),
        price=amount if isinstance(amount, int) else None,
        year=doc.get("year") if isinstance(doc.get("year"), int) else None,
        mileage=miles * 10 if isinstance(miles, int) else None,
        fuel_type=str(doc.get("fuel") or ""),
        gearbox=str(doc.get("transmission") or ""),
        image_url=str(image.get("url") or ""),
        location=str(doc.get("location") or ""),
        currency="kr",
    )
