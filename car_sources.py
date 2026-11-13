from __future__ import annotations

import re
from dataclasses import replace

from blocket_catalog import catalog_or_fallback as blocket_catalog
from car_config import car_search_key_from_config
from fx import to_sek
from otomoto_catalog import catalog_or_fallback as otomoto_catalog
from otomoto_client import CarSearchParams

SITES = ("otomoto", "blocket")


def norm_label(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def parse_sources(value: object) -> list[str]:
    parts = [part.strip().lower() for part in str(value or "").split(",") if part.strip()]
    if any(part not in SITES for part in parts):
        raise ValueError("Unknown site")
    selected = [site for site in SITES if site in parts]
    if not selected:
        raise ValueError("Choose a site")
    return selected


def find_option(options: list, token: object) -> dict | None:
    wanted = norm_label(token)
    if not wanted:
        return None
    for item in options or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") == str(token).strip() or norm_label(item.get("label")) == wanted:
            return item
    return None


def _catalog(source: str) -> dict:
    if source == "blocket":
        return blocket_catalog()
    return otomoto_catalog()


def materialize_configs(config: dict) -> list[dict]:
    """One config per selected site, with that site's own make, model and region ids.

    The form stores one price in PLN. A shared make is the name, and each site
    gets the id that name has in its own catalog. A region is kept only where it exists.
    """
    sources = parse_sources(config.get("car_source") or "otomoto")
    if len(sources) == 1:
        cfg = dict(config)
        cfg["car_source"] = sources[0]
        return [cfg]

    catalogs = {source: _catalog(source) for source in sources}
    prepared: list[dict] = []
    for source in sources:
        catalog = catalogs[source]
        make = find_option(catalog.get("makes") or [], config.get("car_make"))
        if make is None:
            raise ValueError("This make is not on every selected site")
        cfg = dict(config)
        cfg["car_source"] = source
        cfg["car_make"] = make["id"]
        model_token = str(config.get("car_model") or "").strip()
        if model_token:
            model = find_option(catalog.get("models", {}).get(make["id"], []), model_token)
            if model is None:
                raise ValueError("This model is not on every selected site")
            cfg["car_model"] = model["id"]
        region_token = str(config.get("car_region") or "").strip()
        if region_token:
            region = find_option(catalog.get("regions") or [], region_token)
            cfg["car_region"] = region["id"] if region else ""
        if source == "blocket":
            cfg["car_damaged"] = ""
        prepared.append(cfg)
    return prepared


def search_keys(config: dict) -> set[str]:
    try:
        configs = materialize_configs(config)
    except ValueError:
        return set()
    return {car_search_key_from_config(cfg) for cfg in configs if str(cfg.get("car_make") or "").strip()}


def prices_for_query(params: CarSearchParams) -> CarSearchParams:
    if params.source != "blocket":
        return params
    return replace(params, price_from=to_sek(params.price_from), price_to=to_sek(params.price_to))
