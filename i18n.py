from __future__ import annotations

from typing import Literal

Language = Literal["en", "uk"]

TRANSLATIONS: dict[str, dict[Language, str]] = {
    "cmd_start": {"en": "Main menu", "uk": "Головне меню"},
    "cmd_menu": {"en": "Main menu", "uk": "Головне меню"},
    "cmd_settings": {"en": "Settings", "uk": "Налаштування"},
    "cmd_stop": {"en": "Stop search", "uk": "Зупинити пошук"},
    "cmd_monitor": {"en": "Monitoring panel", "uk": "Панель моніторингу"},
    "main_title": {"en": "🏛 *Poznań appointment monitor*", "uk": "🏛 *Монітор записів Poznań*"},
    "main_title_html": {"en": "🏛 <b>Poznań Appointment Monitor</b>", "uk": "🏛 <b>Монітор записів Poznań</b>"},
    "settings_title_html": {"en": "⚙️ <b>Settings</b>", "uk": "⚙️ <b>Налаштування</b>"},
    "divider": {"en": "────────────────", "uk": "────────────────"},
    "badge_idle": {"en": "🟡 <b>Ready</b> — configure and press Start", "uk": "🟡 <b>Готово</b> — налаштуйте і натисніть Start"},
    "badge_current_active": {
        "en": "🟢 <b>This setup is searching</b>",
        "uk": "🟢 <b>Цей набір у пошуку</b>",
    },
    "badge_searches_running": {
        "en": "🟢 <b>{count} search(es) running</b>",
        "uk": "🟢 <b>{count} пошук(и) активні</b>",
    },
    "label_active_searches": {"en": "Active searches", "uk": "Активні пошуки"},
    "no_active_searches": {"en": "No active searches", "uk": "Немає активних пошуків"},
    "btn_start_inline": {"en": "🟢 Start", "uk": "🟢 Старт"},
    "btn_stop_inline": {"en": "🔴 Stop", "uk": "🔴 Стоп"},
    "btn_stop_all": {"en": "⏹ Stop all", "uk": "⏹ Зуп. всі"},
    "label_service": {"en": "Service", "uk": "Послуга"},
    "label_config": {"en": "Configuration", "uk": "Налаштування"},
    "main_hint": {
        "en": "Search keeps running after slots appear — tap ✅ when you booked",
        "uk": "Пошук триває після знаходження слотів — натисніть ✅ коли записалися",
    },
    "main_intro": {
        "en": "Set target date → Start search → get notified → Stop when done",
        "uk": "Дата → Почати пошук → сповіщення → Зупинити",
    },
    "panel_resent": {
        "en": "Monitoring panel sent below",
        "uk": "Панель моніторингу надіслано нижче",
    },
    "settings_title": {"en": "⚙️ *Settings*", "uk": "⚙️ *Налаштування*"},
    "settings_cases": {"en": "Number of cases", "uk": "Кількість справ"},
    "settings_notify_before": {"en": "Target date", "uk": "Цільова дата"},
    "settings_service": {"en": "Service", "uk": "Послуга"},
    "settings_interval": {"en": "Check interval", "uk": "Інтервал перевірки"},
    "yes": {"en": "yes", "uk": "так"},
    "no": {"en": "no", "uk": "ні"},
    "btn_start_search": {"en": "🟢 Start search", "uk": "🟢 Почати пошук"},
    "btn_stop_search": {"en": "🔴 Stop search", "uk": "🔴 Зупинити пошук"},
    "btn_menu": {"en": "📋 Menu", "uk": "📋 Меню"},
    "btn_show_panel": {"en": "📋 Monitoring", "uk": "📋 Моніторинг"},
    "btn_settings": {"en": "⚙️ Settings", "uk": "⚙️ Налаштування"},
    "btn_status": {"en": "📊 Status", "uk": "📊 Статус"},
    "btn_until_date": {"en": "📅 {date}", "uk": "📅 {date}"},
    "btn_case_short_1": {"en": "1", "uk": "1"},
    "btn_case_short_2": {"en": "2", "uk": "2"},
    "btn_case_short_3": {"en": "3", "uk": "3"},
    "btn_service_annotations": {"en": "📋 Annotations", "uk": "📋 Анотації"},
    "btn_service_vehicle": {"en": "🚗 Registration", "uk": "🚗 Реєстрація"},
    "btn_service_certificate": {"en": "📄 Certificate", "uk": "📄 Документ"},
    "label_cases": {"en": "Cases", "uk": "Справи"},
    "menu_status_idle": {"en": "Waiting", "uk": "Очікування"},
    "menu_status_searching": {"en": "Searching", "uk": "Пошук"},
    "service_change_blocked": {
        "en": "Stop the search before changing the service.",
        "uk": "Спочатку зупиніть пошук, щоб змінити послугу.",
    },
    "saved_service": {"en": "✅ Service selected", "uk": "✅ Послугу обрано"},
    "btn_set_deadline": {"en": "📅 Set target date", "uk": "📅 Встановити дату"},
    "btn_reset_state": {"en": "🔄 Reset known slots", "uk": "🔄 Скинути відомі слоти"},
    "btn_main_menu": {"en": "⬅️ Back to menu", "uk": "⬅️ До меню"},
    "btn_lang_en": {"en": "🇬🇧 English", "uk": "🇬🇧 English"},
    "btn_lang_uk": {"en": "🇺🇦 Ukrainian", "uk": "🇺🇦 Українська"},
    "no_slots_in_range": {
        "en": "No free slots in the selected range.",
        "uk": "Немає вільних слотів у вибраному діапазоні.",
    },
    "and_more": {"en": "… and {count} more", "uk": "… і ще {count}"},
    "access_denied": {"en": "Access denied.", "uk": "Доступ заборонено."},
    "prompt_date_message": {
        "en": "📅 <b>Enter target date</b>\n\nType the date in format:\n<code>YYYY-MM-DD</code>\n\nExample: <code>2026-08-30</code>",
        "uk": "📅 <b>Введіть цільову дату</b>\n\nНадішліть дату у форматі:\n<code>YYYY-MM-DD</code>\n\nПриклад: <code>2026-08-30</code>",
    },
    "prompt_date_short": {
        "en": "Send the date in YYYY-MM-DD format in chat",
        "uk": "Надішліть дату у форматі YYYY-MM-DD у чат",
    },
    "invalid_date": {
        "en": "❌ Invalid format. Use <code>YYYY-MM-DD</code>",
        "uk": "❌ Невірний формат. Використайте <code>YYYY-MM-DD</code>",
    },
    "saved_cases": {"en": "✅ Cases: <b>{value}</b>", "uk": "✅ Справ: <b>{value}</b>"},
    "saved_interval": {"en": "✅ Interval: <b>{value}</b>", "uk": "✅ Інтервал: <b>{value}</b>"},
    "saved_date": {"en": "✅ Date: <b>{value}</b>", "uk": "✅ Дата: <b>{value}</b>"},
    "saved_language_en": {"en": "✅ Language: *English*", "uk": "✅ Мову змінено на *English*"},
    "saved_language_uk": {"en": "✅ Language: *Ukrainian*", "uk": "✅ Мову змінено на *Українська*"},
    "reset_state_done": {
        "en": "🔄 Known slots cleared.",
        "uk": "🔄 Відомі слоти очищено.",
    },
    "status_title": {"en": "📊 <b>Status</b>", "uk": "📊 <b>Статус</b>"},
    "status_available": {
        "en": "Available until <b>{date}</b>: <b>{count}</b>",
        "uk": "Доступно до <b>{date}</b>: <b>{count}</b>",
    },
    "status_known": {"en": "Tracked: <b>{count}</b>", "uk": "Відстежується: <b>{count}</b>"},
    "search_started": {
        "en": "🟢 <b>Search started</b>\n\n📋 {service}\n📅 until {date}  ·  📂 {cases}  ·  ⏱ {interval}",
        "uk": "🟢 <b>Пошук розпочато</b>\n\n📋 {service}\n📅 до {date}  ·  📂 {cases}  ·  ⏱ {interval}",
    },
    "search_already_running": {
        "en": "This setup is already searching.",
        "uk": "Цей набір уже в пошуку.",
    },
    "search_stopped": {
        "en": "🔴 <b>Search stopped</b> for current setup",
        "uk": "🔴 <b>Пошук зупинено</b> для поточного набору",
    },
    "search_stopped_all": {
        "en": "⏹ <b>All searches stopped</b> ({count})",
        "uk": "⏹ <b>Усі пошуки зупинено</b> ({count})",
    },
    "search_not_running": {
        "en": "Search is not running.",
        "uk": "Пошук не запущено.",
    },
    "notify_new_slots_title": {"en": "🆕 New free slots!", "uk": "🆕 Нові вільні слоти!"},
    "notify_service": {"en": "Service", "uk": "Послуга"},
    "notify_branch": {"en": "Branch", "uk": "Відділення"},
    "notify_cases": {"en": "Number of cases", "uk": "Кількість справ"},
    "notify_booking": {"en": "Booking", "uk": "Запис"},
    "notify_search_continues": {
        "en": "Tap ✅ if you booked, or ❌ if you missed it.",
        "uk": "Натисніть ✅ якщо записалися, або ❌ якщо не встигли.",
    },
    "btn_slot_confirmed": {"en": "✅ I booked it", "uk": "✅ Записався"},
    "btn_slot_not_booked": {"en": "❌ Didn't book", "uk": "❌ Не записався"},
    "notify_booking_confirmed": {
        "en": "✅ Booking confirmed — search stopped.",
        "uk": "✅ Запис підтверджено — пошук зупинено.",
    },
    "notify_not_booked": {
        "en": "❌ Not booked — still searching.",
        "uk": "❌ Не записався — пошук триває.",
    },
    "search_still_running": {
        "en": "Still searching",
        "uk": "Пошук триває",
    },
    "search_confirmed_stopped": {
        "en": "Search stopped",
        "uk": "Пошук зупинено",
    },
    "confirm_expired": {
        "en": "This confirmation link expired.",
        "uk": "Посилання підтвердження застаріло.",
    },
    "notify_error_title": {"en": "Monitor error:", "uk": "Помилка монітора:"},
}


def normalize_language(value: str | None) -> Language:
    if value and value.lower().startswith("uk"):
        return "uk"
    return "en"


def t(key: str, lang: Language, **kwargs: object) -> str:
    template = TRANSLATIONS[key][lang]
    return template.format(**kwargs) if kwargs else template


def button_texts(key: str) -> set[str]:
    return {t(key, "en"), t(key, "uk")}
