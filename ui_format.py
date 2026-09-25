from __future__ import annotations

import html

from config_store import format_interval, load_user_config
from i18n import Language, t
from search_config import ActiveSearchInfo, current_config_active
from services import SERVICE_BUTTON_I18N, ServiceKey


def _esc(value: object) -> str:
    return html.escape(str(value))


def _format_active_searches(lang: Language, active: list[ActiveSearchInfo]) -> str:
    if not active:
        return f"<i>{t('no_active_searches', lang)}</i>"

    lines = [f"<b>{t('label_active_searches', lang)} ({len(active)})</b>"]
    for item in active:
        lines.append(
            f"🟢 {_esc(item.service_name)} · 📅 {_esc(item.notify_before_date)} · 📂 {_esc(item.num_cases)}"
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
        f"   📅 {_esc(config['notify_before_date'])}"
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
