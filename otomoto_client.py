from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests
from lxml.html import document_fromstring

logger = logging.getLogger(__name__)

BASE_URL = "https://www.otomoto.pl"
CATEGORY = "osobowe"
MAX_PAGES = 8

FUEL_TYPES = ("petrol", "diesel", "hybrid", "plugin-hybrid", "electric", "petrol-lpg")
GEARBOXES = ("manual", "automatic")

# Card text is the Polish label, while the search param is the otomoto slug.
_FUEL_ACCEPTED = {
    "petrol": {"petrol", "benzyna", "bensin"},
    "diesel": {"diesel"},
    "hybrid": {"hybrid", "hybryda", "hybrid bensin", "hybrid diesel", "hybrid gas"},
    "plugin-hybrid": {
        "plugin-hybrid",
        "plugin hybrid",
        "hybryda plug-in",
        "plug in bensin",
        "plug in diesel",
    },
    "electric": {"electric", "elektryczny", "elektriska", "el"},
    "petrol-lpg": {"petrol-lpg", "petrol lpg", "benzyna lpg"},
}
_GEAR_ACCEPTED = {
    "manual": {"manual", "manualna", "manuell"},
    "automatic": {"automatic", "automatyczna", "automatisk"},
}


@dataclass(frozen=True)
class CarListing:
    listing_id: str
    title: str
    url: str
    price: int | None
    year: int | None
    mileage: int | None
    fuel_type: str
    gearbox: str
    image_url: str = ""
    location: str = ""
    currency: str = "zł"


@dataclass(frozen=True)
class CarSearchParams:
    make: str
    model: str = ""
    region: str = ""
    year_from: int | None = None
    year_to: int | None = None
    price_from: int | None = None
    price_to: int | None = None
    price_tolerance: int = 0
    mileage_to: int | None = None
    fuel_type: str = ""
    gearbox: str = ""
    damaged: str = ""
    source: str = ""


def _number(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _photo_url(article) -> str:
    sources = [src.strip() for src in article.xpath(".//img/@src") if src and src.strip()]
    if not sources:
        return ""
    src = sources[0]
    if src.startswith("//"):
        src = "https:" + src
    return re.sub(r";s=\d+x\d+", ";s=800x600", src)


def _location(article) -> str:
    for paragraph in article.xpath(".//p"):
        text = " ".join(part.strip() for part in paragraph.itertext() if part.strip())
        if "•" in text or "·" in text:
            continue
        if re.fullmatch(r".{2,60} \([^)]{2,40}\)", text):
            return text
    return ""


def _norm(value: str) -> str:
    cleaned = value.lower().replace("(", " ").replace(")", " ").replace("+", " ").replace("-", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _percent_delta(amount: int, percent: int) -> int:
    return (amount * percent + 50) // 100


def accepted_price_bounds(params: CarSearchParams) -> tuple[int | None, int | None]:
    """Widen the stated price by the tolerance, e.g. 50 000 zł ±10% accepts up to 55 000 zł."""
    percent = params.price_tolerance if params.price_tolerance > 0 else 0
    low = params.price_from
    high = params.price_to
    if percent and low is not None:
        low = max(0, low - _percent_delta(low, percent))
    if percent and high is not None:
        high = high + _percent_delta(high, percent)
    return low, high


def listing_within_filters(item: CarListing, params: CarSearchParams) -> bool:
    """Otomoto sometimes renders offers the price query did not ask for. Check the parsed offer."""
    low, high = accepted_price_bounds(params)
    if params.price_from is not None and (item.price is None or low is None or item.price < low):
        return False
    if params.price_to is not None and (item.price is None or high is None or item.price > high):
        return False
    if params.year_from is not None and (item.year is None or item.year < params.year_from):
        return False
    if params.year_to is not None and (item.year is None or item.year > params.year_to):
        return False
    if params.mileage_to is not None and (item.mileage is None or item.mileage > params.mileage_to):
        return False
    if params.fuel_type:
        accepted = {_norm(value) for value in _FUEL_ACCEPTED.get(params.fuel_type, {params.fuel_type})}
        if _norm(item.fuel_type) not in accepted:
            return False
    if params.gearbox:
        accepted = {_norm(value) for value in _GEAR_ACCEPTED.get(params.gearbox, {params.gearbox})}
        if _norm(item.gearbox) not in accepted:
            return False
    return True


class OtomotoClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv=128.0) Gecko/20100101 Firefox/128.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6",
            }
        )

    def search_url(self, params: CarSearchParams) -> str:
        path = [CATEGORY, params.make]
        if params.model:
            path.append(params.model)
        if params.region:
            path.append(params.region)
        return f"{BASE_URL}/{'/'.join(path)}"

    def search_params(self, params: CarSearchParams) -> dict[str, object]:
        query: dict[str, object] = {"search[border]": "created_at:desc"}
        if params.year_from:
            query["search[filter_float_year:from]"] = params.year_from
        if params.year_to:
            query["search[filter_float_year:to]"] = params.year_to
        low, high = accepted_price_bounds(params)
        if low:
            query["search[filter_float_price:from]"] = low
        if high:
            query["search[filter_float_price:to]"] = high
        if params.mileage_to:
            query["search[filter_float_mileage:to]"] = params.mileage_to
        if params.fuel_type:
            query["search[filter_enum_fuel_type]"] = params.fuel_type
        if params.gearbox:
            query["search[filter_enum_gearbox]"] = params.gearbox
        if params.damaged in {"0", "1"}:
            query["search[filter_enum_damaged]"] = params.damaged
        return query

    def get_listings(self, params: CarSearchParams) -> list[CarListing]:
        url = self.search_url(params)
        base_query = self.search_params(params)
        listings: list[CarListing] = []
        seen: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            response = self.session.get(url, params={**base_query, "page": page}, timeout=30)
            response.raise_for_status()
            page_listings = self.parse_listings(response.text)
            if not page_listings:
                break
            fresh = [item for item in page_listings if item.listing_id not in seen]
            if not fresh:
                break
            seen.update(item.listing_id for item in fresh)
            listings.extend(fresh)

        matched = self.filter_make_model(listings, params)
        kept = [item for item in matched if listing_within_filters(item, params)]
        if len(kept) != len(matched):
            logger.info(
                "Dropped %d offers outside the car filters | make=%s | model=%s",
                len(matched) - len(kept),
                params.make,
                params.model,
            )
        return kept

    def parse_listings(self, body: str) -> list[CarListing]:
        tree = document_fromstring(body)
        listings: list[CarListing] = []
        articles = tree.xpath("//*[@data-testid='search-results']//article[@data-id]")
        if not articles:
            articles = tree.xpath("//article[@data-id]")
        for article in articles:
            links = [
                a
                for a in article.xpath('.//a[@data-nextlink="false"]')
                if re.search(r"-I[A-Za-z0-9]{6,}\.html$", a.get("href", ""))
            ]
            if not links:
                continue
            prices = [
                s
                for s in article.xpath('.//span[@translate="no"]')
                if re.fullmatch(r"[\d \u00a0.]{2,}", (s.text or "").strip())
            ]
            fields: dict[str, str] = {}
            for dd in article.xpath(".//dd[@data-parameter]"):
                fields[dd.get("data-parameter")] = " ".join(
                    part.strip() for part in dd.itertext() if part.strip()
                ).strip()
            listings.append(
                CarListing(
                    listing_id=article.get("data-id"),
                    title=(links[0].get("aria-label") or "").strip(),
                    url=links[0].get("href", ""),
                    price=_number(prices[0].text) if prices else None,
                    year=_number(fields.get("year", "")),
                    mileage=_number(fields.get("mileage", "")),
                    fuel_type=fields.get("fuel_type", ""),
                    gearbox=fields.get("gearbox", ""),
                    image_url=_photo_url(article),
                    location=_location(article),
                )
            )
        return listings

    def filter_make_model(self, listings: list[CarListing], params: CarSearchParams) -> list[CarListing]:
        # otomoto silently falls back to other makes/models when a slug is wrong,
        # so keep only listings whose link slug belongs to the requested make/model.
        expected = params.make if not params.model else f"{params.make}-{params.model}"
        kept = []
        for item in listings:
            slug = re.search(r"/([^/]+)-I[A-Za-z0-9]{6,}\.html$", item.url)
            if slug and (
                slug.group(1) == expected
                or slug.group(1).startswith(f"{expected}-")
            ):
                kept.append(item)
        return kept
