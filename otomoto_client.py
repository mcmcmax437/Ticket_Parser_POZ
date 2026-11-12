from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from lxml.html import document_fromstring

BASE_URL = "https://www.otomoto.pl"
CATEGORY = "osobowe"
MAX_PAGES = 8

FUEL_TYPES = ("petrol", "diesel", "hybrid", "plugin-hybrid", "electric", "petrol-lpg")
GEARBOXES = ("manual", "automatic")


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


@dataclass(frozen=True)
class CarSearchParams:
    make: str
    model: str = ""
    region: str = ""
    year_from: int | None = None
    year_to: int | None = None
    price_from: int | None = None
    price_to: int | None = None
    mileage_to: int | None = None
    fuel_type: str = ""
    gearbox: str = ""


def _number(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


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
        if params.price_from:
            query["search[filter_float_price:from]"] = params.price_from
        if params.price_to:
            query["search[filter_float_price:to]"] = params.price_to
        if params.mileage_to:
            query["search[filter_float_mileage:to]"] = params.mileage_to
        if params.fuel_type:
            query["search[filter_enum_fuel_type]"] = params.fuel_type
        if params.gearbox:
            query["search[filter_enum_gearbox]"] = params.gearbox
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

        return self.filter_make_model(listings, params)

    def parse_listings(self, body: str) -> list[CarListing]:
        tree = document_fromstring(body)
        listings: list[CarListing] = []
        for article in tree.xpath("//article[@data-id]"):
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
