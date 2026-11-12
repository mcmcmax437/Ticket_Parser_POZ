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
        "en": "Set a date range → Start search → get notified → Stop when done",
        "uk": "Діапазон дат → Почати пошук → сповіщення → Зупинити",
    },
    "panel_resent": {
        "en": "Monitoring panel sent below",
        "uk": "Панель моніторингу надіслано нижче",
    },
    "settings_title": {"en": "⚙️ *Settings*", "uk": "⚙️ *Налаштування*"},
    "settings_cases": {"en": "Number of cases", "uk": "Кількість справ"},
    "settings_notify_from": {"en": "From", "uk": "Від"},
    "settings_notify_before": {"en": "Until", "uk": "До"},
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
    "btn_from_date": {"en": "From {date}", "uk": "Від {date}"},
    "btn_from_any": {"en": "From any", "uk": "Від будь-якої"},
    "btn_until_date": {"en": "Until {date}", "uk": "До {date}"},
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
    "btn_set_from": {"en": "📅 Set start date", "uk": "📅 Дата від"},
    "btn_set_deadline": {"en": "📅 Set end date", "uk": "📅 Дата до"},
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
    "prompt_date_from": {
        "en": "📅 <b>Enter start date</b>\n\nSlots on this day and later.\n<code>YYYY-MM-DD</code>\n\nExample: <code>2026-07-01</code>",
        "uk": "📅 <b>Введіть дату від</b>\n\nСлоти з цього дня і пізніше.\n<code>YYYY-MM-DD</code>\n\nПриклад: <code>2026-07-01</code>",
    },
    "prompt_date_message": {
        "en": "📅 <b>Enter end date</b>\n\nSlots up to and including this day.\n<code>YYYY-MM-DD</code>\n\nExample: <code>2026-08-30</code>",
        "uk": "📅 <b>Введіть дату до</b>\n\nСлоти до цього дня включно.\n<code>YYYY-MM-DD</code>\n\nПриклад: <code>2026-08-30</code>",
    },
    "invalid_date_range": {
        "en": "❌ Start date must be on or before the end date.",
        "uk": "❌ Дата «від» має бути не пізніше дати «до».",
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
        "en": "Available <b>{range}</b>: <b>{count}</b>",
        "uk": "Доступно <b>{range}</b>: <b>{count}</b>",
    },
    "status_known": {"en": "Tracked: <b>{count}</b>", "uk": "Відстежується: <b>{count}</b>"},
    "search_started": {
        "en": "🟢 <b>Search started</b>\n\n📋 {service}\n📅 {range}  ·  📂 {cases}  ·  ⏱ {interval}",
        "uk": "🟢 <b>Пошук розпочато</b>\n\n📋 {service}\n📅 {range}  ·  📂 {cases}  ·  ⏱ {interval}",
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
    "cmd_car": {"en": "Car search", "uk": "Поиск авто"},
    "car_title_html": {"en": "🚗 <b>Car search (otomoto.pl)</b>", "uk": "🚗 <b>Поиск авто (otomoto.pl)</b>"},
    "car_hint": {
        "en": "Set make → add filters → Start car search. You get notified about new listings and price drops.",
        "uk": "Set make → add filters → Start car search. You get notified about new listings and price drops.",
    },
    "label_car_config": {"en": "Filters", "uk": "Filters"},
    "label_active_car_searches": {"en": "Car searches running", "uk": "Car searches running"},
    "no_active_car_searches": {"en": "No car search is running.", "uk": "No car search is running."},
    "badge_car_idle": {"en": "🟡 <b>Ready</b> — set the make and press Start", "uk": "🟡 <b>Ready</b> — set the make and press Start"},
    "badge_car_active": {"en": "🟢 <b>This car search is running</b>", "uk": "🟢 <b>This car search is running</b>"},
    "badge_cars_running": {"en": "🟢 <b>{count} car search(es) running</b>", "uk": "🟢 <b>{count} car search(es) running</b>"},
    "car_alert_title": {"en": "🚗 <b>Car hits!</b>", "uk": "🚗 <b>Car hits!</b>"},
    "car_status_title": {"en": "🚗 <b>Car status</b>", "uk": "🚗 <b>Car status</b>"},
    "car_reset_done": {"en": "🔄 Tracked listings cleared.", "uk": "🔄 Tracked listings cleared."},
    "car_make_required": {"en": "Set the car make first.", "uk": "Set the car make first."},
    "car_search_already_running": {"en": "This car search is already running.", "uk": "This car search is already running."},
    "car_search_not_running": {"en": "Car search is not running.", "uk": "Car search is not running."},
    "car_search_stopped": {"en": "🔴 <b>Car search stopped</b>", "uk": "🔴 <b>Car search stopped</b>"},
    "car_search_stopped_all": {"en": "⏹ <b>All car searches stopped</b> ({count})", "uk": "⏹ <b>All car searches stopped</b> ({count})"},
    "widget_more": {"en": "+{count} more", "uk": "+{count} more"},
    "widget_last_check": {"en": "Last check: {time}", "uk": "Last check: {time}"},
    "widget_hits": {"en": "{count} hit(s)", "uk": "{count} hit(s)"},
    "widget_new": {"en": "🆕 New listing", "uk": "🆕 New listing"},
    "widget_drop": {"en": "💷 Price drop", "uk": "💷 Price drop"},
    "car_search_started": {
        "en": "🟢 <b>Car search started</b>\n\n🔍 {filters}\n⏱ {interval}",
        "uk": "🟢 <b>Car search started</b>\n\n🔍 {filters}\n⏱ {interval}",
    },
    "invalid_car_value": {
        "en": "❌ Invalid value. Make/model/region use latin letters and hyphens (e.g. <code>volkswagen</code>, <code>seria-3</code>). Numbers for prices, years and mileage.",
        "uk": "❌ Invalid value. Make/model/region use latin letters and hyphens (e.g. <code>volkswagen</code>, <code>seria-3</code>). Numbers for prices, years and mileage.",
    },
    "btn_open_app": {"en": "Open app", "uk": "Відкрити застосунок"},
    "app_intro": {
        "en": "Appointments and car filters are in the app. Alerts still arrive in this chat.",
        "uk": "Записи і фільтри авто — у застосунку. Сповіщення й далі приходять у цей чат.",
    },
    "app_missing_url": {
        "en": "Set WEBAPP_URL in .env to an https address that points at this bot's port 8080, then restart.",
        "uk": "Вкажіть WEBAPP_URL у .env — https-адреса на порт 8080 цього бота — і перезапустіть.",
    },
    "btn_car_menu": {"en": "🚗 Car search", "uk": "🚗 Поиск авто"},
    "btn_car_status": {"en": "🚗 Car status", "uk": "🚗 Поиск статус"},
    "btn_car_start": {"en": "🟢 Start car search", "uk": "🟢 Start car search"},
    "btn_car_stop": {"en": "🔴 Stop car search", "uk": "🔴 Stop car search"},
    "btn_car_main_menu": {"en": "⬅️ Ticket menu", "uk": "⬅️ Ticket menu"},
    "btn_car_reset": {"en": "🔄 Clear tracked listings", "uk": "🔄 Clear tracked listings"},
    "btn_car_any": {"en": "Any", "uk": "Будь-яке"},
    "field_make": {"en": "Make", "uk": "Марка"},
    "field_model": {"en": "Model", "uk": "Модель"},
    "field_year": {"en": "Year", "uk": "Рік"},
    "field_price": {"en": "Price", "uk": "Ціна"},
    "field_mileage": {"en": "Mileage", "uk": "Пробіг"},
    "field_region": {"en": "Region", "uk": "Регіон"},
    "field_fuel": {"en": "Fuel", "uk": "Паливо"},
    "field_gear": {"en": "Gearbox", "uk": "Коробка"},
    "btn_car_make": {"en": "Make: {value}", "uk": "Make: {value}"},
    "btn_car_model": {"en": "Model: {value}", "uk": "Model: {value}"},
    "btn_car_region": {"en": "Region: {value}", "uk": "Region: {value}"},
    "btn_car_year_from": {"en": "Year from: {value}", "uk": "Year from: {value}"},
    "btn_car_year_to": {"en": "Year to: {value}", "uk": "Year to: {value}"},
    "btn_car_price_from": {"en": "Price from: {value}", "uk": "Price from: {value}"},
    "btn_car_price_to": {"en": "Price to: {value}", "uk": "Price to: {value}"},
    "btn_car_mileage_to": {"en": "Max mileage: {value}", "uk": "Max mileage: {value}"},
    "btn_car_interval": {"en": "Interval: {interval}", "uk": "Interval: {interval}"},
    "prompt_car_make": {
        "en": "🚗 <b>Enter car make</b>\n\notomoto.pl slug, lowercase. Example: <code>volkswagen</code>",
        "uk": "🚗 <b>Enter car make</b>\n\notomoto.pl slug, lowercase. Example: <code>volkswagen</code>",
    },
    "prompt_car_model": {
        "en": "🚗 <b>Enter car model</b>\n\notomoto.pl slug, lowercase, hyphens. Example: <code>seria-3</code>\nSend empty to clear.",
        "uk": "🚗 <b>Enter car model</b>\n\notomoto.pl slug, lowercase, hyphens. Example: <code>seria-3</code>\nSend empty to clear.",
    },
    "prompt_car_region": {
        "en": "🚗 <b>Enter region or city</b>\n\notomoto.pl slug. Examples: <code>mazowieckie</code>, <code>warszawa</code>",
        "uk": "🚗 <b>Enter region or city</b>\n\notomoto.pl slug. Examples: <code>mazowieckie</code>, <code>warszawa</code>",
    },
    "prompt_car_year_from": {
        "en": "🚗 <b>Enter first year</b>\n\nExample: <code>2015</code>",
        "uk": "🚗 <b>Enter first year</b>\n\nExample: <code>2015</code>",
    },
    "prompt_car_year_to": {
        "en": "🚗 <b>Enter last year</b>\n\nExample: <code>2020</code>",
        "uk": "🚗 <b>Enter last year</b>\n\nExample: <code>2020</code>",
    },
    "prompt_car_price_from": {
        "en": "🚗 <b>Enter minimum price in PLN</b>\n\nExample: <code>20000</code>",
        "uk": "🚗 <b>Enter minimum price in PLN</b>\n\nExample: <code>20000</code>",
    },
    "prompt_car_price_to": {
        "en": "🚗 <b>Enter maximum price in PLN</b>\n\nExample: <code>40000</code>",
        "uk": "🚗 <b>Enter maximum price in PLN</b>\n\nExample: <code>40000</code>",
    },
    "prompt_car_mileage_to": {
        "en": "🚗 <b>Enter maximum mileage in km</b>\n\nExample: <code>150000</code>",
        "uk": "🚗 <b>Enter maximum mileage in km</b>\n\nExample: <code>150000</code>",
    },
    "prompt_car_poll_interval_seconds": {
        "en": "🚗 <b>Enter car check interval in seconds</b>\n\nExample: <code>900</code>",
        "uk": "🚗 <b>Enter car check interval in seconds</b>\n\nExample: <code>900</code>",
    },
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
