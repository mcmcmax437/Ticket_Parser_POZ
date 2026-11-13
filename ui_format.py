from __future__ import annotations

import html
import json
import re
import time

from config_store import format_interval, load_user_config
from i18n import Language, t
from search_config import ActiveSearchInfo, current_config_active
from car_config import CarSearchInfo, car_search_info, car_search_key_from_config
from otomoto_client import CarListing
from qmatic_client import TimeSlot
from services import SERVICE_BUTTON_I18N, ServiceKey
from telegram_notifier import BOOKING_URL

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
        lines.append(_active_search_line(item))
    return "\n".join(lines)


def _active_search_line(item: ActiveSearchInfo) -> str:
    return (
        f"🟢 {_esc(item.service_name)}"
        f" · 📅 {_esc(format_date_range(item.notify_from_date, item.notify_before_date))}"
        f" · 📂 {_esc(item.num_cases)}"
    )


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


def _price_part(info: CarSearchInfo) -> str:
    window = f"{_group(info.price_from or '…')}–{_group(info.price_to or '…')} zł"
    tolerance = str(info.price_tolerance or "").strip()
    if tolerance and tolerance != "0":
        window += f" ±{tolerance}%"
    return window


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
        parts.append(_price_part(info))
    if info.mileage_to:
        parts.append(f"≤ {_group(info.mileage_to)} km")
    if info.fuel_type:
        parts.append(FUEL_LABELS.get(info.fuel_type, info.fuel_type))
    if info.gearbox:
        parts.append(GEARBOX_LABELS.get(info.gearbox, info.gearbox))
    if info.damaged == "0":
        parts.append(t("damage_no", lang))
    elif info.damaged == "1":
        parts.append(t("damage_yes", lang))
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


def car_card_caption(lang: Language, item: CarListing, previous: int | None = None) -> str:
    if previous is not None and item.price is not None:
        mark = "📉"
        price = f"{_group(previous)} → {_group(item.price)} zł"
    else:
        mark = "🆕"
        price = f"{_group(item.price)} zł" if item.price is not None else "—"
    facts = []
    if item.year:
        facts.append(str(item.year))
    if item.mileage:
        facts.append(f"{_group(item.mileage)} km")
    if item.fuel_type:
        facts.append(item.fuel_type)
    if item.gearbox:
        facts.append(item.gearbox)
    lines = [f"{mark} <b>{_esc(item.title)}</b>", f"<b>{_esc(price)}</b>"]
    if facts:
        lines.append(_esc(" · ".join(facts)))
    if item.location:
        lines.append(_esc(item.location))
    if item.url:
        lines.append(f'<a href="{_esc(item.url)}">{t("car_open_listing", lang)}</a>')
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
        lines.append(car_card_caption(lang, item))
        lines.append("")
    for item, previous in price_drops:
        lines.append(car_card_caption(lang, item, previous))
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


# --- Telegram widgets (Bot API 10.4) ---

WIDGET_CSS = (
    "body{margin:0;padding:12px 14px}"
    "h3{font-size:17px;margin:0 0 6px}"
    ".sub{font-size:13px;color:var(--tg-theme-hint-color);margin-bottom:8px}"
    ".grp{font-size:13px;font-weight:700;margin-top:8px}"
    ".slot{font-size:14px;padding:2px 0}"
    ".it{font-size:14px;font-weight:700;margin-top:8px}"
    ".dt{font-size:13px;color:var(--tg-theme-hint-color)}"
    ".badge{display:inline-block;margin-bottom:8px;padding:4px 8px;border-radius:8px;"
    "background:var(--tg-theme-secondary-bg-color);font-size:13px;font-weight:700}"
    ".row{padding:4px 0;font-size:14px;line-height:1.4}"
    ".hint{margin-top:8px;font-size:12px;color:var(--tg-theme-hint-color)}"
)

STATUS_WIDGET_HTML = (
    f"<style>{WIDGET_CSS}</style>"
    "<div class=\"badge\" id=\"h\"></div><div id=\"l\"></div><div class=\"hint\" id=\"n\"></div>"
    "<script>"
    "const W=window.TelegramWidget;"
    "function r(){"
    "var s=null;"
    "try{s=JSON.parse(W.chatData)}catch(e){}"
    "document.getElementById('h').textContent=s?(s.h||''):'';"
    "var l=document.getElementById('l');l.innerHTML='';"
    "for(var x of(s.l||[])){var d=document.createElement('div');d.textContent=x;d.className='row';l.appendChild(d)}"
    "document.getElementById('n').textContent=s?(s.n||''):'';"
    "}"
    "if(W)W.onEvent('chatDataChanged',r);"
    "r();"
    "</script>"
)

PANEL_WIDGET_HTML = (
    "<style>"
    "body{margin:0;padding:12px 14px}"
    "h3{margin:0 0 8px;font-size:17px}"
    ".badge{display:inline-block;margin-bottom:8px;padding:4px 8px;border-radius:8px;"
    "background:var(--tg-theme-secondary-bg-color);font-size:13px;font-weight:700}"
    ".row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;"
    "border-top:1px solid var(--tg-theme-secondary-bg-color);font-size:14px}"
    ".k{color:var(--tg-theme-hint-color)}"
    ".lbl{margin:12px 0 6px;font-size:12px;font-weight:700;letter-spacing:.04em;"
    "text-transform:uppercase;color:var(--tg-theme-hint-color)}"
    ".chips{display:flex;flex-wrap:wrap;gap:6px}"
    ".chips button{margin:0}"
    "button.on{background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color)}"
    ".hint{margin-top:10px;font-size:12px;color:var(--tg-theme-hint-color)}"
    "</style>"
    "<h3 id=\"title\"></h3><div class=\"badge\" id=\"badge\"></div><div id=\"rows\"></div>"
    "<div class=\"lbl\" id=\"servicesLabel\" hidden></div><div class=\"chips\" id=\"services\"></div>"
    "<div class=\"lbl\" id=\"casesLabel\" hidden></div><div class=\"chips\" id=\"cases\"></div>"
    "<div class=\"lbl\" id=\"fuelsLabel\" hidden></div><div class=\"chips\" id=\"fuels\"></div>"
    "<div class=\"lbl\" id=\"gearsLabel\" hidden></div><div class=\"chips\" id=\"gears\"></div>"
    "<div class=\"hint\" id=\"hint\"></div>"
    "<script>"
    "const W=window.TelegramWidget;"
    "function chip(item){"
    "var b=document.createElement('button');"
    "b.type='button';b.textContent=item.n||'';"
    "if(item.on)b.className='on';"
    "b.onclick=function(){if(W&&W.request)W.request(item.d);};"
    "return b;}"
    "function fill(id,items){"
    "var box=document.getElementById(id);"
    "var label=document.getElementById(id+'Label');"
    "var list=items||[];"
    "if(label)label.hidden=!list.length;"
    "box.hidden=!list.length;box.innerHTML='';"
    "list.forEach(function(item){box.appendChild(chip(item));});}"
    "function render(){"
    "var s={};"
    "try{s=JSON.parse(W.chatData)||{};}catch(e){}"
    "document.getElementById('title').textContent=s.title||'';"
    "document.getElementById('badge').textContent=s.badge||'';"
    "var rows=document.getElementById('rows');rows.innerHTML='';"
    "(s.rows||[]).forEach(function(r){"
    "var d=document.createElement('div');d.className='row';"
    "var k=document.createElement('span');k.className='k';k.textContent=r.k||'';"
    "var v=document.createElement('b');v.textContent=r.v||'—';"
    "d.appendChild(k);d.appendChild(v);rows.appendChild(d);});"
    "fill('services',s.services);fill('cases',s.cases);"
    "fill('fuels',s.fuels);fill('gears',s.gears);"
    "var hint=document.getElementById('hint');hint.textContent=s.hint||'';hint.hidden=!s.hint;"
    "document.getElementById('servicesLabel').textContent=s.servicesLabel||'';"
    "document.getElementById('casesLabel').textContent=s.casesLabel||'';"
    "document.getElementById('fuelsLabel').textContent=s.fuelsLabel||'';"
    "document.getElementById('gearsLabel').textContent=s.gearsLabel||'';"
    "}"
    "if(W)W.onEvent('chatDataChanged',render);"
    "render();"
    "if(W&&W.ready)W.ready();"
    "</script>"
)

CARD_LINE_LIMIT = 6
WIDGET_CAPTION_URL_LIMIT = 5
_TAGS = re.compile(r"<[^>]+>")


def _plain(value: str) -> str:
    return html.unescape(_TAGS.sub("", value))


def ticket_alert_widget_html(lang: Language, settings, new_slots: list[TimeSlot]) -> str:
    lines = [
        f"<h3>{t('notify_new_slots_title', lang)}</h3>",
        f"<div class=\"sub\">{_esc(settings.service_name)} · {_esc(settings.branch_name)} · {_esc(settings.num_cases)}</div>",
    ]
    current_date = None
    for slot in new_slots:
        if slot.appointment_date != current_date:
            current_date = slot.appointment_date
            lines.append(f"<div class=\"grp\">{_esc(current_date.isoformat())}</div>")
        lines.append(f"<div class=\"slot\">{_esc(slot.time)}</div>")
    return f"<style>{WIDGET_CSS}</style>" + "".join(lines)


def ticket_alert_caption(lang: Language, settings, new_slots: list[TimeSlot]) -> str:
    return (
        f"{t('notify_new_slots_title', lang)} · {len(new_slots)} · "
        f"{_esc(settings.service_name)} · → {settings.notify_before_date.isoformat()}\n"
        f"{BOOKING_URL}"
    )


def car_alert_widget_html(
    lang: Language,
    info: CarSearchInfo,
    new_listings: list[CarListing],
    price_drops: list[tuple[CarListing, int]],
) -> str:
    lines = [
        f"<h3>{t('car_alert_title', lang)}</h3>",
        f"<div class=\"sub\">🔍 {car_filter_summary(lang, info)}</div>",
    ]
    for item in new_listings:
        lines.append(f"<div class=\"it\">🆕 {_esc(item.title)}</div>")
        lines.append(f"<div class=\"dt\">{_esc(_car_details(item))}</div>")
    for item, previous in price_drops:
        lines.append(f"<div class=\"it\">📉 {_esc(item.title)}</div>")
        lines.append(f"<div class=\"dt\">{_group(previous)} → {_group(item.price)} zł</div>")
    return f"<style>{WIDGET_CSS}</style>" + "".join(lines)


def car_alert_caption(
    lang: Language,
    info: CarSearchInfo,
    new_listings: list[CarListing],
    price_drops: list[tuple[CarListing, int]],
) -> str:
    urls = [item.url for item in new_listings][:WIDGET_CAPTION_URL_LIMIT]
    urls += [item.url for item, _ in price_drops][: WIDGET_CAPTION_URL_LIMIT - len(urls)]
    return (
        f"{t('car_alert_title', lang)} · {len(new_listings)} 🆕 · {len(price_drops)} 📉 · "
        f"{_esc(car_filter_summary(lang, info))}\n" + "\n".join(urls)
    )


def _status_badge(
    lang: Language,
    ticket_searches: list[ActiveSearchInfo],
    car_searches: list[CarSearchInfo],
) -> str:
    if not ticket_searches and not car_searches:
        return t("badge_idle", lang)
    parts = []
    if ticket_searches:
        parts.append(f"{t('label_active_searches', lang)} ({len(ticket_searches)})")
    if car_searches:
        parts.append(f"{t('label_active_car_searches', lang)} ({len(car_searches)})")
    return f"🟢 <b>{' · '.join(parts)}</b>"


def status_widget_chat_data(
    lang: Language,
    ticket_searches: list[ActiveSearchInfo],
    car_searches: list[CarSearchInfo],
    checked_at: int,
) -> str:
    lines = [_plain(_active_search_line(item)) for item in ticket_searches[:CARD_LINE_LIMIT]]
    lines += [_plain(car_search_line(lang, item)) for item in car_searches[: CARD_LINE_LIMIT - len(lines)]]
    hidden = len(ticket_searches) + len(car_searches) - len(lines)
    if hidden > 0:
        lines.append(t("widget_more", lang, count=hidden))
    return json.dumps(
        {
            "t": checked_at,
            "h": _plain(_status_badge(lang, ticket_searches, car_searches)),
            "l": lines,
            "n": t("widget_last_check", lang, time=time.strftime("%H:%M", time.localtime(checked_at))),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _span(value: object) -> str:
    text = str(value or "").strip()
    return text or "—"


def _chips(options: list[tuple[str, str]], selected: str, prefix: str, any_label: str) -> list[dict]:
    chips = [
        {"n": name, "d": f"{prefix}:{value}", "on": selected == value}
        for value, name in options
    ]
    chips.append({"n": any_label, "d": f"{prefix}:", "on": not selected})
    return chips


def ticket_panel_state(lang: Language, service_name: str, active: list[ActiveSearchInfo]) -> str:
    config = load_user_config()
    active_keys = {item.search_key for item in active}
    if active and current_config_active(active_keys):
        badge = t("badge_current_active", lang)
    elif active:
        badge = t("badge_searches_running", lang, count=len(active))
    else:
        badge = t("badge_idle", lang)
    selected_service = str(config.get("service_key") or "")
    selected_cases = int(config["num_cases"])
    services = [
        {
            "n": t(SERVICE_BUTTON_I18N[key], lang),
            "d": f"svc:{key}",
            "on": key == selected_service,
        }
        for key in ("annotations", "vehicle_registration", "certificate_pickup")
    ]
    return json.dumps(
        {
            "title": _plain(t("main_title_html", lang)),
            "badge": _plain(badge),
            "rows": [
                {"k": t("settings_notify_from", lang), "v": _span(config.get("notify_from_date"))},
                {"k": t("settings_notify_before", lang), "v": _span(config.get("notify_before_date"))},
                {"k": t("settings_interval", lang), "v": format_interval(int(config["poll_interval_seconds"]))},
            ],
            "servicesLabel": t("label_service", lang),
            "services": services,
            "casesLabel": t("settings_cases", lang),
            "cases": [
                {"n": str(n), "d": f"n:{n}", "on": n == selected_cases}
                for n in (1, 2, 3)
            ],
            "hint": t("main_hint", lang),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def car_panel_state(lang: Language, active_cars: list[CarSearchInfo]) -> str:
    config = load_user_config()
    current_key = car_search_key_from_config(config)
    active_keys = {item.search_key for item in active_cars}
    if current_key in active_keys:
        badge = t("badge_car_active", lang)
    elif active_cars:
        badge = t("badge_cars_running", lang, count=len(active_cars))
    else:
        badge = t("badge_car_idle", lang)
    info = car_search_info(config, current_key)
    year = "—"
    if info.year_from or info.year_to:
        year = f"{info.year_from or '…'} – {info.year_to or '…'}"
    price = "—"
    if info.price_from or info.price_to:
        price = _price_part(info)
    return json.dumps(
        {
            "title": _plain(t("car_title_html", lang)),
            "badge": _plain(badge),
            "rows": [
                {"k": t("field_make", lang), "v": _span(info.make)},
                {"k": t("field_model", lang), "v": _span(info.model)},
                {"k": t("field_year", lang), "v": year},
                {"k": t("field_price", lang), "v": price},
                {"k": t("field_mileage", lang), "v": f"≤ {_group(info.mileage_to)} km" if info.mileage_to else "—"},
                {"k": t("field_region", lang), "v": _span(info.region)},
                {"k": t("settings_interval", lang), "v": format_interval(info.poll_interval_seconds)},
            ],
            "fuelsLabel": t("field_fuel", lang),
            "fuels": _chips(list(FUEL_LABELS.items()), info.fuel_type, "f", t("btn_car_any", lang)),
            "gearsLabel": t("field_gear", lang),
            "gears": _chips(list(GEARBOX_LABELS.items()), info.gearbox, "g", t("btn_car_any", lang)),
            "hint": t("car_hint", lang),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def status_widget_caption(
    lang: Language,
    ticket_searches: list[ActiveSearchInfo],
    car_searches: list[CarSearchInfo],
    checked_at: int,
) -> str:
    return (
        f"{_status_badge(lang, ticket_searches, car_searches)}\n"
        f"{t('widget_last_check', lang, time=time.strftime('%H:%M', time.localtime(checked_at)))}"
    )
