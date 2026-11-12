from __future__ import annotations

import html

from config_store import format_interval, load_user_config
from i18n import Language, t
from search_config import ActiveSearchInfo, current_config_active
from car_config import CarSearchInfo, car_search_info, car_search_key_from_config
from otomoto_client import CarListing
from services import SERVICE_BUTTON_I18N, ServiceKey

FUEL_LABELS = {
    "petrol": "Benzyna",
    "diesel": "Diesel",
    "hybrid": "Hybryda",
    "plugin-hybrid": "Hybryda (plug-in)",
    "electric": "Elektriska",
    "petrol-lpg": "Benzyna+LPG",
}
GEARBOX_LABELS = {"manual": "Manualna", "automatic": "Automatyczna"}


def _esc(value: object) -> str:
    return html.escape(str(value))


def format_date_range(from_date: object, until_date: object) -> str:
    start = str(from_date or "").strip()
    end = str(until_date)
    if start:
        return f"{start} → {end}"
    return f"→ {end}"


def _format_active_searches(lang: Language, active: list[ActiveSearchInfo]) -> str:
    if not active:
        return f"<i>{t('no_active_searches', lang)}</i>"

    lines = [f"<b>{t('label_active_searches', lang)} ({len(active)})</b>"]
    for item in active:
        lines.append(
            f"🟢 {_esc(item.service_name)} · 📅 {_esc(format_date_range(item.notify_from_date, item.notify_before_date))} · 📂 {_esc(item.num_cases)}"
        )
    return "\n".join(lines)


def main_menu_html(
    lang: Language,
    service_name: str,
    active_searches: list[ActiveSearchInfo],
) -> str:
    config = load_user_config()
    interval = format_interval(int(config["poll_interval_seconds"]))
    active_keys = {s.search_key for s in active_searches}
    current_active = current_config_active(active_keys)

    if active_searches:
        if current_active:
            badge = t("badge_current_active", lang)
        else:
            badge = t("badge_searches_running", lang, count=len(active_searches))
    else:
        badge = t("badge_idle", lang)

    return (
        f"{t('main_title_html', lang)}\n"
        f"{t('divider', lang)}\n\n"
        f"{badge}\n\n"
        f"<b>{t('label_service', lang)}</b>\n"
        f"   {_esc(service_name)}\n\n"
        f"<b>{t('label_config', lang)}</b>\n"
        f"   📅 {_esc(format_date_range(config.get('notify_from_date'), config['notify_before_date']))}"
        f"   ·   📂 {_esc(config['num_cases'])}"
        f"   ·   ⏱ {_esc(interval)}\n\n"
        f"{_format_active_searches(lang, active_searches)}\n\n"
        f"<i>{t('main_hint', lang)}</i>"
    )


def settings_html(lang: Language, service_name: str, active_searches: list[ActiveSearchInfo]) -> str:
    config = load_user_config()
    interval = format_interval(int(config["poll_interval_seconds"]))
    return (
        f"{t('settings_title_html', lang)}\n"
        f"{t('divider', lang)}\n\n"
        f"<b>{t('label_service', lang)}</b>  {_esc(service_name)}\n"
        f"<b>{t('settings_notify_from', lang)}</b>  {_esc(config.get('notify_from_date') or '—')}\n"
        f"<b>{t('settings_notify_before', lang)}</b>  {_esc(config['notify_before_date'])}\n"
        f"<b>{t('settings_cases', lang)}</b>  {_esc(config['num_cases'])}\n"
        f"<b>{t('settings_interval', lang)}</b>  {_esc(interval)}\n\n"
        f"{_format_active_searches(lang, active_searches)}"
    )


def selected_prefix(is_selected: bool) -> str:
    return "● " if is_selected else "○ "


def service_button_label(lang: Language, service_key: ServiceKey, selected: str) -> str:
    prefix = selected_prefix(selected == service_key)
    return prefix + t(SERVICE_BUTTON_I18N[service_key], lang)


def case_button_label(num: int, selected: int) -> str:
    prefix = selected_prefix(selected == num)
    return f"{prefix}{num}"


def interval_button_label(seconds: int, selected: int) -> str:
    label = format_interval(seconds)
    prefix = selected_prefix(selected == seconds)
    return f"{prefix}{label}"


def _group(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        return text
    return f"{int(text):,}".replace(",", "\u2009")


def car_filter_summary(lang: Language, info: CarSearchInfo) -> str:
    parts = [info.make, info.model, info.region]
    if info.year_from or info.year_to:
        parts.append(f"{info.year_from or '…'}–{info.year_to or '…'}")
    if info.price_from or info.price_to:
        parts.append(f"{_group(info.price_from or '…')}–{_group(info.price_to or '…')} zł")
    if info.mileage_to:
        parts.append(f"≤ {_group(info.mileage_to)} km")
    if info.fuel_type:
        parts.append(FUEL_LABELS.get(info.fuel_type, info.fuel_type))
    if info.gearbox:
        parts.append(GEARBOX_LABELS.get(info.gearbox, info.gearbox))
    return " · ".join(_esc(p) for p in parts if p)


def car_search_line(lang: Language, info: CarSearchInfo) -> str:
    return (
        f"🚗 {car_filter_summary(lang, info)}"
        f" · ⏱ {_esc(format_interval(info.poll_interval_seconds))}"
    )


def car_menu_html(lang: Language, active_cars: list[CarSearchInfo]) -> str:
    config = load_user_config()
    current_key = car_search_key_from_config(config)
    active_keys = {item.search_key for item in active_cars}

    if current_key in active_keys:
        badge = t("badge_car_active", lang)
    elif active_cars:
        badge = t("badge_cars_running", lang, count=len(active_cars))
    else:
        badge = t("badge_car_idle", lang)

    return (
        f"{t('car_title_html', lang)}\n"
        f"{t('divider', lang)}\n\n"
        f"{badge}\n\n"
        f"<b>{t('label_car_config', lang)}</b>\n"
        f"   {car_filter_summary(lang, car_search_info(config, current_key))}\n\n"
        f"{_format_active_cars(lang, active_cars)}\n\n"
        f"<i>{t('car_hint', lang)}</i>"
    )


def _format_active_cars(lang: Language, active_cars: list[CarSearchInfo]) -> str:
    if not active_cars:
        return f"<i>{t('no_active_car_searches', lang)}</i>"
    lines = [f"<b>{t('label_active_car_searches', lang)} ({len(active_cars)})</b>"]
    for item in active_cars:
        lines.append(car_search_line(lang, item))
    return "\n".join(lines)


def format_car_alert_html(
    lang: Language,
    info: CarSearchInfo,
    new_listings: list[CarListing],
    price_drops: list[tuple[CarListing, int]],
) -> str:
    lines = [
        t("car_alert_title", lang),
        "",
        f"🔍 {car_filter_summary(lang, info)}",
        "",
    ]
    for item in new_listings:
        lines.append(f"🆕 <b>{_esc(item.title)}</b>")
        lines.append(f"   {_esc(_car_details(item))}")
        lines.append(f"   {item.url}")
        lines.append("")
    for item, previous in price_drops:
        lines.append(f"📉 <b>{_esc(item.title)}</b>")
        lines.append(f"   {_group(previous)} → {_group(item.price)} zł")
        lines.append(f"   {_esc(_car_details(item))}")
        lines.append(f"   {item.url}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _car_details(item: CarListing) -> str:
    parts = [f"{_group(item.price)} zł" if item.price is not None else "—"]
    if item.year:
        parts.append(str(item.year))
    if item.mileage:
        parts.append(f"{_group(item.mileage)} km")
    if item.fuel_type:
        parts.append(item.fuel_type)
    if item.gearbox:
        parts.append(item.gearbox)
    return " · ".join(parts)
