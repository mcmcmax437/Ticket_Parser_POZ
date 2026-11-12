from __future__ import annotations

import logging
import re
from datetime import date

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import STATE_FILE, Settings, load_settings
from config_store import format_interval, load_user_config, update_user_config
from i18n import Language, button_texts, normalize_language, t
from monitor import load_state, save_state
from qmatic_client import QmaticClient, TimeSlot
from search_log import log_search_result
from search_config import search_state_key_from_config
from car_config import car_search_info, car_search_key_from_config, parse_price, parse_tolerance
from car_monitor import CAR_STATE_FILE, load_car_state, save_car_state
from car_session import CarManager, get_car_manager
from search_session import SearchManager, get_search_manager, SLOT_CONFIRMATIONS_KEY
from services import SERVICE_ORDER
from webapp_server import start_webapp, webapp_url
from widget_sender import refresh_status_card
from ui_format import (
    FUEL_LABELS,
    GEARBOX_LABELS,
    car_menu_html,
    car_search_line,
    case_button_label,
    format_date_range,
    interval_button_label,
    main_menu_html,
    service_button_label,
    settings_html,
)

logger = logging.getLogger(__name__)

PARSE_MODE = "HTML"
AWAITING_DATE = "awaiting_date"
DATE_FIELD = "date_field"
DATE_PROMPT_MESSAGE_ID = "date_prompt_message_id"
DATE_PROMPT_SETTINGS_VIEW = "date_prompt_settings_view"
PANEL_MESSAGE_ID = "panel_message_id"
KEYBOARD_SENT = "keyboard_sent"

AWAITING_CAR_FIELD = "awaiting_car_field"
CAR_PROMPT_MESSAGE_ID = "car_prompt_message_id"

CAR_SLUG_FIELDS = ("car_make", "car_model", "car_region")
CAR_INT_FIELDS = ("car_year_from", "car_year_to", "car_price_from", "car_price_to", "car_mileage_to")

CAR_PROMPT_KEYS = {
    "car_make": "prompt_car_make",
    "car_model": "prompt_car_model",
    "car_region": "prompt_car_region",
    "car_year_from": "prompt_car_year_from",
    "car_year_to": "prompt_car_year_to",
    "car_price_from": "prompt_car_price_from",
    "car_price_to": "prompt_car_price_to",
    "car_price_tolerance": "prompt_car_price_tolerance",
    "car_mileage_to": "prompt_car_mileage_to",
    "car_poll_interval_seconds": "prompt_car_poll_interval_seconds",
}

CAR_VALUE_BUTTON_KEYS = {
    "car_make": "btn_car_make",
    "car_model": "btn_car_model",
    "car_region": "btn_car_region",
    "car_year_from": "btn_car_year_from",
    "car_year_to": "btn_car_year_to",
    "car_price_from": "btn_car_price_from",
    "car_price_to": "btn_car_price_to",
    "car_price_tolerance": "btn_car_price_tolerance",
    "car_mileage_to": "btn_car_mileage_to",
}


def _lang() -> Language:
    return normalize_language(str(load_user_config().get("language", "en")))


def _authorized(update: Update, settings: Settings) -> bool:
    chat = update.effective_chat
    return chat is not None and str(chat.id) == settings.telegram_chat_id


def _manager(application: Application) -> SearchManager:
    return get_search_manager(application)


def _app_url(tab: str = "tickets") -> str:
    base = webapp_url()
    if not base.startswith("https://"):
        return ""
    return f"{base}/?tab={tab}"


def _reply_keyboard(lang: Language) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    url = _app_url()
    if url:
        rows.append([KeyboardButton(t("btn_open_app", lang), web_app=WebAppInfo(url=url))])
    rows.extend(
        [
            [
                KeyboardButton(t("btn_start_search", lang)),
                KeyboardButton(t("btn_stop_search", lang)),
            ],
            [
                KeyboardButton(t("btn_show_panel", lang)),
                KeyboardButton(t("btn_settings", lang)),
            ],
            [
                KeyboardButton(t("btn_car_menu", lang)),
                KeyboardButton(t("btn_car_status", lang)),
            ],
        ]
    )
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def _case_row(lang: Language, selected: int) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(case_button_label(n, selected), callback_data=f"set:cases:{n}")
        for n in (1, 2, 3)
    ]


def _service_rows(lang: Language, selected_service: str) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                service_button_label(lang, key, selected_service),
                callback_data=f"set:service:{key}",
            )
        ]
        for key in SERVICE_ORDER
    ]


def _search_control_rows(lang: Language, manager: SearchManager) -> list[list[InlineKeyboardButton]]:
    rows = [
        [
            InlineKeyboardButton(t("btn_start_inline", lang), callback_data="action:start_search"),
            InlineKeyboardButton(t("btn_stop_inline", lang), callback_data="action:stop_search"),
        ]
    ]
    if manager.active_count > 0:
        rows.append([InlineKeyboardButton(t("btn_stop_all", lang), callback_data="action:stop_all")])
    return rows


def _inline_menu_keyboard(lang: Language, manager: SearchManager) -> InlineKeyboardMarkup:
    config = load_user_config()
    return InlineKeyboardMarkup(
        [
            *_search_control_rows(lang, manager),
            [
                _from_date_button(lang, config),
                InlineKeyboardButton(
                    t("btn_until_date", lang, date=config["notify_before_date"]),
                    callback_data="prompt:until",
                ),
            ],
            [
                InlineKeyboardButton(t("btn_status", lang), callback_data="action:status"),
                InlineKeyboardButton(t("btn_car_menu", lang), callback_data="menu:car"),
            ],
            [
                InlineKeyboardButton(t("btn_show_panel", lang), callback_data="action:show_panel"),
                InlineKeyboardButton(t("btn_settings", lang), callback_data="menu:settings"),
            ],
        ]
    )


def _settings_keyboard(lang: Language, manager: SearchManager) -> InlineKeyboardMarkup:
    config = load_user_config()
    selected_cases = int(config["num_cases"])
    selected_service = str(config["service_key"])
    selected_interval = int(config["poll_interval_seconds"])
    return InlineKeyboardMarkup(
        [
            *_search_control_rows(lang, manager),
            [
                InlineKeyboardButton(t("btn_lang_en", lang), callback_data="set:lang:en"),
                InlineKeyboardButton(t("btn_lang_uk", lang), callback_data="set:lang:uk"),
            ],
            *_service_rows(lang, selected_service),
            [
                InlineKeyboardButton(t("btn_set_from", lang), callback_data="prompt:from"),
                InlineKeyboardButton(t("btn_set_deadline", lang), callback_data="prompt:until"),
            ],
            _case_row(lang, selected_cases),
            [
                InlineKeyboardButton(
                    interval_button_label(60, selected_interval),
                    callback_data="set:interval:60",
                ),
                InlineKeyboardButton(
                    interval_button_label(180, selected_interval),
                    callback_data="set:interval:180",
                ),
                InlineKeyboardButton(
                    interval_button_label(300, selected_interval),
                    callback_data="set:interval:300",
                ),
            ],
            [
                InlineKeyboardButton(
                    interval_button_label(600, selected_interval),
                    callback_data="set:interval:600",
                ),
                InlineKeyboardButton(
                    interval_button_label(900, selected_interval),
                    callback_data="set:interval:900",
                ),
            ],
            [InlineKeyboardButton(t("btn_reset_state", lang), callback_data="action:reset_state")],
            [
                InlineKeyboardButton(t("btn_show_panel", lang), callback_data="action:show_panel"),
                InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu:main"),
                InlineKeyboardButton(t("btn_car_menu", lang), callback_data="menu:car"),
            ],
        ]
    )


def _car_manager(application: Application) -> CarManager:
    return get_car_manager(application)


def _car_value_button(lang: Language, field: str, config: dict) -> InlineKeyboardButton:
    raw = str(config.get(field) or "").strip()
    if field == "car_price_tolerance":
        raw = raw or "0"
    label = t(CAR_VALUE_BUTTON_KEYS[field], lang, value=raw or "—")
    return InlineKeyboardButton(label, callback_data=f"prompt:{field}")


def _car_keyboard(lang: Language, manager, config: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t("btn_car_start", lang), callback_data="action:start_car"),
                InlineKeyboardButton(t("btn_car_stop", lang), callback_data="action:stop_car"),
            ],
            [
                _car_value_button(lang, "car_make", config),
                _car_value_button(lang, "car_model", config),
            ],
            [
                _car_value_button(lang, "car_year_from", config),
                _car_value_button(lang, "car_year_to", config),
            ],
            [
                _car_value_button(lang, "car_price_from", config),
                _car_value_button(lang, "car_price_to", config),
            ],
            [_car_value_button(lang, "car_price_tolerance", config)],
            [
                _car_value_button(lang, "car_mileage_to", config),
                _car_value_button(lang, "car_region", config),
            ],
            [
                InlineKeyboardButton(
                    t("btn_car_interval", lang, interval=format_interval(int(config["car_poll_interval_seconds"]))),
                    callback_data="prompt:car_poll_interval_seconds",
                )
            ],
            [
                InlineKeyboardButton(t("btn_car_status", lang), callback_data="action:car_status"),
                InlineKeyboardButton(t("btn_car_reset", lang), callback_data="action:car_reset"),
            ],
            [
                InlineKeyboardButton(t("btn_car_main_menu", lang), callback_data="menu:main"),
                InlineKeyboardButton(t("btn_settings", lang), callback_data="menu:settings"),
            ],
        ]
    )


def _car_content(application: Application, lang: Language) -> tuple[str, InlineKeyboardMarkup]:
    manager = _car_manager(application)
    config = load_user_config()
    return car_menu_html(lang, manager.list_active()), _car_keyboard(lang, manager, config)


async def present_ticket(application: Application, chat_id: int) -> None:
    del application, chat_id


async def present_car(application: Application, chat_id: int) -> None:
    del application, chat_id


async def send_open_app(application: Application, chat_id: int, tab: str = "tickets") -> None:
    lang = _lang()
    url = _app_url(tab)
    if not url:
        await application.bot.send_message(chat_id=chat_id, text=t("app_missing_url", lang))
        return
    label = t("btn_open_app", lang)
    await application.bot.send_message(
        chat_id=chat_id,
        text=t("app_intro", lang),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, web_app=WebAppInfo(url=url))]]
        ),
    )


async def _refresh_car_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    await present_car(context.application, chat_id)


def _is_car_message(query) -> bool:
    markup = query.message.reply_markup if query.message else None
    if not markup or not markup.inline_keyboard:
        return False
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data and (
                btn.callback_data.startswith("prompt:car") or btn.callback_data.startswith("set:car")
            ):
                return True
    return False


async def _prompt_for_car_value(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    lang: Language,
    field: str,
) -> None:
    if query.message:
        _remember_panel(context, query.message.message_id)

    chat_id = query.message.chat_id if query.message else None
    if chat_id is None:
        return

    await _delete_message_safe(context, chat_id, context.user_data.get(CAR_PROMPT_MESSAGE_ID))

    prompt = await context.bot.send_message(
        chat_id=chat_id,
        text=t(CAR_PROMPT_KEYS[field], lang),
        parse_mode=PARSE_MODE,
    )

    context.user_data[AWAITING_CAR_FIELD] = field
    context.user_data[CAR_PROMPT_MESSAGE_ID] = prompt.message_id


async def _apply_car_value(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    raw: str,
    lang: Language,
) -> bool:
    field = str(context.user_data.get(AWAITING_CAR_FIELD) or "")
    value = raw.strip()

    if field in CAR_SLUG_FIELDS:
        slug = re.sub(r"[\s_]+", "-", value).strip("-").lower()
        if slug and not re.fullmatch(r"[a-z0-9-]+", slug):
            return False
        stored = slug
    elif field in ("car_price_from", "car_price_to"):
        try:
            stored = parse_price(value)
        except ValueError:
            return False
        current = load_user_config()
        start = stored if field == "car_price_from" else str(current.get("car_price_from") or "")
        end = stored if field == "car_price_to" else str(current.get("car_price_to") or "")
        if start and end and int(start) > int(end):
            return False
    elif field == "car_price_tolerance":
        try:
            stored = parse_tolerance(value)
        except ValueError:
            return False
    elif field in CAR_INT_FIELDS:
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            stored = ""
        elif field.startswith("car_year") and not 1900 <= int(digits) <= 2100:
            return False
        else:
            stored = str(int(digits))
    elif field == "car_poll_interval_seconds":
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            return False
        stored = str(max(60, min(int(digits), 86400)))
    else:
        return False

    update_user_config(**{field: stored})
    context.user_data.pop(AWAITING_CAR_FIELD, None)
    await _delete_message_safe(context, chat_id, context.user_data.pop(CAR_PROMPT_MESSAGE_ID, None))

    manager = _car_manager(context.application)
    text = car_menu_html(lang, manager.list_active())
    keyboard = _car_keyboard(lang, manager, load_user_config())
    if not await _update_panel(context, chat_id, text, keyboard):
        await _send_panel(context, chat_id, text, keyboard)
    return True


async def _start_car_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _car_manager(context.application)
    config = load_user_config()

    if not str(config.get("car_make") or "").strip():
        message = t("car_make_required", lang)
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        else:
            await _reply(update, context, message)
        return

    key = car_search_key_from_config(config)
    if manager.is_running(key):
        message = t("car_search_already_running", lang)
        if update.callback_query:
            await update.callback_query.answer(message)
        else:
            await _reply(update, context, message)
        return

    chat = update.effective_chat
    if chat is None:
        return

    await manager.start_config(config, context.application, chat.id)

    if update.callback_query:
        try:
            await update.callback_query.answer("✅")
        except BadRequest:
            pass
    else:
        await _reply(
            update,
            context,
            t(
                "car_search_started",
                lang,
                filters=car_search_line(lang, car_search_info(config, key)),
                interval=format_interval(int(config["car_poll_interval_seconds"])),
            ),
        )

    await _refresh_panel_from_update(update, context)


async def _stop_car_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _car_manager(context.application)

    if not await manager.stop_config(load_user_config()):
        message = t("car_search_not_running", lang)
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        else:
            await _reply(update, context, message)
        return

    if update.callback_query:
        try:
            await update.callback_query.answer(t("car_search_stopped", lang))
        except BadRequest:
            pass
    else:
        await _reply(update, context, t("car_search_stopped", lang))

    await _refresh_panel_from_update(update, context)


async def _stop_all_cars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _car_manager(context.application)
    count = await manager.stop_all()
    message = t("car_search_stopped_all", lang, count=count) if count else t("car_search_not_running", lang)
    if update.callback_query:
        await update.callback_query.answer(message, show_alert=count == 0)
    else:
        await _reply(update, context, message)

    await _refresh_panel_from_update(update, context)


async def _show_car_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _car_manager(context.application)
    config = load_user_config()
    key = car_search_key_from_config(config)
    known = load_car_state(CAR_STATE_FILE, key)
    active = manager.is_running(key)
    badge = t("menu_status_searching", lang) if active else t("menu_status_idle", lang)

    lines = [
        f"{t('car_status_title', lang)}",
        t("divider", lang),
        "",
        f"🔹 {badge}",
        f"🔹 {car_search_line(lang, car_search_info(config, key))}",
        f"🔹 {t('status_known', lang, count=len(known))}",
    ]
    for item in manager.list_active():
        lines.append(f"🔹 {car_search_line(lang, item)}")

    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=PARSE_MODE)
    elif update.message:
        await update.message.reply_text(text, parse_mode=PARSE_MODE, reply_markup=_reply_keyboard(lang))


def _format_slots(slots: list[TimeSlot], lang: Language, limit: int = 25) -> str:
    if not slots:
        return t("no_slots_in_range", lang)

    lines: list[str] = []
    current_date = None
    shown = 0
    for slot in slots:
        if shown >= limit:
            lines.append(f"\n{t('and_more', lang, count=len(slots) - limit)}")
            break
        if slot.appointment_date != current_date:
            current_date = slot.appointment_date
            lines.append(f"\n<b>{current_date.isoformat()}</b>")
        lines.append(f"  • {slot.time}")
        shown += 1
    return "\n".join(lines)


async def _refresh_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    *,
    settings_view: bool = False,
) -> None:
    lang = _lang()
    manager = _manager(context.application)
    active = manager.list_active()
    settings = load_settings()

    if settings_view:
        text = settings_html(lang, settings.service_name, active)
        keyboard = _settings_keyboard(lang, manager)
        if not await _update_panel(context, chat_id, text, keyboard):
            await _send_panel(context, chat_id, text, keyboard)
        return

    await present_ticket(context.application, chat_id)


async def _refresh_panel_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE, *, settings_view: bool = False) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    await refresh_status_card(context.application, chat.id, _lang())

    if settings_view and update.callback_query and update.callback_query.message:
        lang = _lang()
        manager = _manager(context.application)
        active = manager.list_active()
        settings = load_settings()
        text = settings_html(lang, settings.service_name, active)
        keyboard = _settings_keyboard(lang, manager)
        _remember_panel(context, update.callback_query.message.message_id)
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode=PARSE_MODE, reply_markup=keyboard
            )
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.warning("Could not refresh panel: %s", exc)
        return

    if not settings_view:
        await present_ticket(context.application, chat.id)
        return

    await _refresh_panel(context, chat.id, settings_view=settings_view)


async def _edit_message_safe(
    bot,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> bool:
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=PARSE_MODE,
            reply_markup=reply_markup,
        )
        return True
    except BadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.warning("Could not edit message %s: %s", message_id, exc)
        return False


def _remember_panel(context: ContextTypes.DEFAULT_TYPE, message_id: int) -> None:
    context.chat_data[PANEL_MESSAGE_ID] = message_id


async def _update_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> bool:
    panel_id = context.chat_data.get(PANEL_MESSAGE_ID)
    if panel_id is None:
        return False
    if await _edit_message_safe(
        context.bot,
        chat_id=chat_id,
        message_id=panel_id,
        text=text,
        reply_markup=reply_markup,
    ):
        return True
    context.chat_data.pop(PANEL_MESSAGE_ID, None)
    return False


async def _force_send_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    context.chat_data.pop(PANEL_MESSAGE_ID, None)
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=PARSE_MODE,
        reply_markup=reply_markup,
    )
    _remember_panel(context, message.message_id)


async def _send_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    if await _update_panel(context, chat_id, text, reply_markup):
        return

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=PARSE_MODE,
        reply_markup=reply_markup,
    )
    _remember_panel(context, message.message_id)


async def _show_monitor_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    settings_view: bool = False,
) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    lang = _lang()
    manager = _manager(context.application)
    active = manager.list_active()
    settings = load_settings()

    if settings_view:
        text = settings_html(lang, settings.service_name, active)
        keyboard = _settings_keyboard(lang, manager)
        await _force_send_panel(context, chat.id, text, keyboard)
    else:
        await send_open_app(context.application, chat.id)
    await _ensure_reply_keyboard(context, chat.id, lang)

    if update.callback_query:
        try:
            await update.callback_query.answer(t("panel_resent", lang))
        except BadRequest:
            pass


async def _show_car_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    await send_open_app(context.application, chat.id, "cars")
    await _ensure_reply_keyboard(context, chat.id, _lang())

    if update.callback_query:
        try:
            await update.callback_query.answer(t("panel_resent", lang))
        except BadRequest:
            pass


async def _delete_message_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BadRequest as exc:
        logger.debug("Could not delete message %s: %s", message_id, exc)


def _from_date_button(lang: Language, config: dict) -> InlineKeyboardButton:
    raw = str(config.get("notify_from_date") or "").strip()
    label = t("btn_from_date", lang, date=raw) if raw else t("btn_from_any", lang)
    return InlineKeyboardButton(label, callback_data="prompt:from")


async def _prompt_for_date(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    lang: Language,
    *,
    settings_view: bool,
    field: str,
) -> None:
    if query.message:
        _remember_panel(context, query.message.message_id)

    chat_id = query.message.chat_id if query.message else None
    if chat_id is None:
        return

    await _delete_message_safe(context, chat_id, context.user_data.get(DATE_PROMPT_MESSAGE_ID))

    prompt = await context.bot.send_message(
        chat_id=chat_id,
        text=t("prompt_date_from" if field == "from" else "prompt_date_message", lang),
        parse_mode=PARSE_MODE,
    )

    context.user_data[AWAITING_DATE] = True
    context.user_data[DATE_FIELD] = field
    context.user_data[DATE_PROMPT_MESSAGE_ID] = prompt.message_id
    context.user_data[DATE_PROMPT_SETTINGS_VIEW] = settings_view


async def _apply_date_change(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    parsed: date,
    lang: Language,
) -> bool:
    field = str(context.user_data.get(DATE_FIELD) or "until")
    config = load_user_config()
    if field == "from":
        until = date.fromisoformat(str(config["notify_before_date"]))
        if parsed > until:
            return False
        update_user_config(notify_from_date=parsed.isoformat())
    else:
        raw_from = str(config.get("notify_from_date") or "").strip()
        if raw_from and parsed < date.fromisoformat(raw_from):
            return False
        update_user_config(notify_before_date=parsed.isoformat())
    settings_view = bool(context.user_data.pop(DATE_PROMPT_SETTINGS_VIEW, False))
    context.user_data.pop(AWAITING_DATE, None)
    context.user_data.pop(DATE_FIELD, None)

    await _delete_message_safe(context, chat_id, context.user_data.pop(DATE_PROMPT_MESSAGE_ID, None))

    settings = load_settings()
    manager = _manager(context.application)
    active = manager.list_active()
    if settings_view:
        text = settings_html(lang, settings.service_name, active)
        keyboard = _settings_keyboard(lang, manager)
        if not await _update_panel(context, chat_id, text, keyboard):
            await _send_panel(context, chat_id, text, keyboard)
    else:
        await present_ticket(context.application, chat_id)
    return True


async def _ensure_reply_keyboard(context: ContextTypes.DEFAULT_TYPE, chat_id: int, lang: Language) -> None:
    if context.chat_data.get(KEYBOARD_SENT):
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=t("main_intro", lang),
        reply_markup=_reply_keyboard(lang),
    )
    context.chat_data[KEYBOARD_SENT] = True


async def _refresh_inline_menu(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    lang: Language,
    *,
    settings_view: bool = False,
) -> None:
    manager = _manager(context.application)
    active = manager.list_active()
    settings = load_settings()
    if not settings_view:
        chat = query.message.chat if query.message else None
        if chat is not None:
            await present_ticket(context.application, chat.id)
        return

    text = settings_html(lang, settings.service_name, active)
    keyboard = _settings_keyboard(lang, manager)

    if query.message is None:
        return

    _remember_panel(context, query.message.message_id)

    try:
        await query.edit_message_text(text, parse_mode=PARSE_MODE, reply_markup=keyboard)
    except BadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning("Could not refresh menu: %s", exc)


async def _send_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    edit: bool = False,
) -> None:
    del edit
    chat = update.effective_chat
    if chat is None:
        return

    await send_open_app(context.application, chat.id)
    await _ensure_reply_keyboard(context, chat.id, lang)


async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()
    if not _authorized(update, settings):
        return
    await _show_monitor_panel(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()
    if not _authorized(update, settings):
        return
    await _send_main_menu(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_command(update, context)


async def car_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()
    if not _authorized(update, settings):
        return
    await _show_car_panel(update, context)


async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    force_new: bool = False,
) -> None:
    settings = load_settings()
    if not _authorized(update, settings):
        return

    lang = _lang()
    manager = _manager(context.application)
    active = manager.list_active()
    text = settings_html(lang, settings.service_name, active)
    keyboard = _settings_keyboard(lang, manager)
    chat = update.effective_chat
    if chat is None:
        return

    if force_new:
        await _show_monitor_panel(update, context, settings_view=True)
        return

    if await _update_panel(context, chat.id, text, keyboard):
        return

    await _send_panel(context, chat.id, text, keyboard)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _stop_search(update, context)


async def _start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _manager(context.application)
    config = load_user_config()
    search_key = search_state_key_from_config(config)

    if manager.is_running(search_key):
        if update.callback_query:
            try:
                await update.callback_query.answer(t("search_already_running", lang), show_alert=True)
            except BadRequest:
                pass
        else:
            await _reply(update, context, t("search_already_running", lang))
        await _refresh_panel_from_update(update, context)
        return

    chat = update.effective_chat
    if chat is None:
        return

    settings = load_settings()
    await manager.start_config(config, context.application, chat.id)

    if update.callback_query:
        try:
            await update.callback_query.answer("✅")
        except BadRequest:
            pass
    else:
        await _reply(
            update,
            context,
            t(
                "search_started",
                lang,
                service=settings.service_name,
                range=format_date_range(config.get("notify_from_date"), config["notify_before_date"]),
                cases=config["num_cases"],
                interval=format_interval(int(config["poll_interval_seconds"])),
            ),
        )

    await _refresh_panel_from_update(update, context)


async def _stop_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _manager(context.application)
    config = load_user_config()

    if not await manager.stop_config(config):
        if update.callback_query:
            await update.callback_query.answer(t("search_not_running", lang), show_alert=True)
        else:
            await _reply(update, context, t("search_not_running", lang))
        return

    if update.callback_query:
        try:
            await update.callback_query.answer(t("search_stopped", lang))
        except BadRequest:
            pass
    else:
        await _reply(update, context, t("search_stopped", lang))

    await _refresh_panel_from_update(update, context)


async def _stop_all_searches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang()
    manager = _manager(context.application)
    count = await manager.stop_all()

    message = t("search_stopped_all", lang, count=count) if count else t("search_not_running", lang)
    if update.callback_query:
        await update.callback_query.answer(message, show_alert=count == 0)
    else:
        await _reply(update, context, message)

    await _refresh_panel_from_update(update, context)


async def _pop_slot_notification(
    context: ContextTypes.DEFAULT_TYPE,
    confirm_id: str,
) -> tuple[str, list[str]] | None:
    pending = context.application.bot_data.get(SLOT_CONFIRMATIONS_KEY, {})
    entry = pending.pop(confirm_id, None)
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry, []
    return str(entry["search_key"]), list(entry.get("slot_keys", []))


async def _confirm_slot_booked(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirm_id: str,
) -> None:
    query = update.callback_query
    if query is None:
        return

    lang = _lang()
    popped = await _pop_slot_notification(context, confirm_id)
    if popped is None:
        try:
            await query.answer(t("confirm_expired", lang), show_alert=True)
        except BadRequest:
            pass
        return

    search_key, _slot_keys = popped
    manager = _manager(context.application)
    await manager.stop_key(search_key)

    try:
        await query.answer(t("search_confirmed_stopped", lang))
    except BadRequest:
        pass

    if query.message and query.message.text:
        confirmed_text = f"{query.message.text}\n\n{t('notify_booking_confirmed', lang)}"
        try:
            await query.edit_message_text(confirmed_text, disable_web_page_preview=True)
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.warning("Could not update slot notification: %s", exc)

    await _refresh_panel_from_update(update, context)


async def _confirm_slot_not_booked(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirm_id: str,
) -> None:
    query = update.callback_query
    if query is None:
        return

    lang = _lang()
    popped = await _pop_slot_notification(context, confirm_id)
    if popped is None:
        try:
            await query.answer(t("confirm_expired", lang), show_alert=True)
        except BadRequest:
            pass
        return

    search_key, slot_keys = popped
    manager = _manager(context.application)
    if slot_keys:
        manager.release_known_slots(search_key, slot_keys)

    try:
        await query.answer(t("search_still_running", lang))
    except BadRequest:
        pass

    if query.message and query.message.text:
        updated_text = f"{query.message.text}\n\n{t('notify_not_booked', lang)}"
        try:
            await query.edit_message_text(updated_text, disable_web_page_preview=True)
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.warning("Could not update slot notification: %s", exc)


async def _reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    lang = _lang()
    markup = _reply_keyboard(lang)
    if update.message:
        await update.message.reply_text(text, parse_mode=PARSE_MODE, reply_markup=markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, parse_mode=PARSE_MODE, reply_markup=markup)


async def _show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()
    lang = _lang()
    client = QmaticClient(settings)
    state_key = search_state_key_from_config(load_user_config())
    known_slots = load_state(STATE_FILE, state_key)
    manager = _manager(context.application)
    current_active = manager.is_running(state_key)

    slots = client.get_slots_before(settings.notify_before_date, settings.notify_from_date)
    log_search_result(settings, slots, [], context="status")
    badge = t("menu_status_searching", lang) if current_active else t("menu_status_idle", lang)
    active_lines = ""
    for item in manager.list_active():
        active_lines += (
            f"\n🟢 {item.service_name} · {format_date_range(item.notify_from_date, item.notify_before_date)} · {item.num_cases}"
        )

    text = (
        f"{t('status_title', lang)}\n"
        f"{t('divider', lang)}\n\n"
        f"🔹 {badge}\n"
        f"🔹 {t('settings_service', lang)}: <b>{settings.service_name}</b>\n"
        f"🔹 {t('status_available', lang, range=format_date_range(settings.notify_from_date, settings.notify_before_date), count=len(slots))}\n"
        f"🔹 {t('status_known', lang, count=len(known_slots))}\n"
        f"🔹 {t('settings_cases', lang)}: <b>{settings.num_cases}</b>"
        f"{active_lines}\n"
        f"\n{_format_slots(slots, lang)}"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=PARSE_MODE)
    elif update.message:
        await update.message.reply_text(text, parse_mode=PARSE_MODE, reply_markup=_reply_keyboard(lang))


def _is_settings_message(query) -> bool:
    markup = query.message.reply_markup if query.message else None
    if not markup or not markup.inline_keyboard:
        return False
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith("set:lang:"):
                return True
    return False


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    settings = load_settings()
    lang = _lang()

    if not _authorized(update, settings):
        await query.answer()
        await query.edit_message_text(t("access_denied", lang))
        return

    data = query.data or ""
    settings_view = _is_settings_message(query)

    if data in {"prompt:date", "prompt:until", "prompt:from"}:
        await query.answer()
        field = "from" if data == "prompt:from" else "until"
        await _prompt_for_date(query, context, lang, settings_view=settings_view, field=field)
        return

    if data == "menu:car":
        await query.answer()
        chat = update.effective_chat
        if chat is not None:
            await send_open_app(context.application, chat.id, "cars")
        return

    if data.startswith("prompt:car"):
        await query.answer()
        await _prompt_for_car_value(query, context, lang, data.split(":", 1)[1])
        return

    if data == "action:start_car":
        await _start_car_search(update, context)
        return

    if data == "action:stop_car":
        await _stop_car_search(update, context)
        return

    if data == "action:stop_all_cars":
        await _stop_all_cars(update, context)
        return

    if data == "action:car_status":
        await _show_car_status(update, context)
        return

    if data == "action:car_reset":
        save_car_state(CAR_STATE_FILE, car_search_key_from_config(load_user_config()), [])
        await query.answer(t("car_reset_done", lang))
        if query.message:
            await _refresh_car_panel(context, query.message.chat_id)
        return

    if data.startswith("set:car_fuel:") or data.startswith("set:car_gearbox:"):
        field = "car_fuel_type" if data.startswith("set:car_fuel:") else "car_gearbox"
        update_user_config(**{field: data.rsplit(":", 1)[1]})
        if query.message:
            await _refresh_car_panel(context, query.message.chat_id)
        return

    if data == "action:start_search":
        await _start_search(update, context)
        return

    if data == "action:stop_search":
        await _stop_search(update, context)
        return

    if data == "action:stop_all":
        await _stop_all_searches(update, context)
        return

    if data == "action:show_panel":
        await _show_monitor_panel(update, context, settings_view=settings_view)
        return

    if data.startswith("confirm:booked:"):
        await _confirm_slot_booked(update, context, data.rsplit(":", 1)[-1])
        return

    if data.startswith("confirm:not_booked:"):
        await _confirm_slot_not_booked(update, context, data.rsplit(":", 1)[-1])
        return

    if data == "action:reset_state":
        config = load_user_config()
        state_key = search_state_key_from_config(config)
        save_state(STATE_FILE, set(), state_key)
        await query.answer(t("reset_state_done", lang))
        await _refresh_inline_menu(query, context, lang, settings_view=settings_view)
        return

    await query.answer()

    if data == "menu:main":
        await query.answer()
        chat = update.effective_chat
        if chat is not None:
            await send_open_app(context.application, chat.id, "tickets")
        return

    if data == "menu:settings":
        if query.message:
            _remember_panel(context, query.message.message_id)
        manager = _manager(context.application)
        active = manager.list_active()
        try:
            await query.edit_message_text(
                settings_html(lang, settings.service_name, active),
                reply_markup=_settings_keyboard(lang, manager),
                parse_mode=PARSE_MODE,
            )
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.warning("Could not open settings: %s", exc)
        return

    if data.startswith("set:lang:"):
        new_lang = normalize_language(data.rsplit(":", 1)[1])
        update_user_config(language=new_lang)
        await _refresh_inline_menu(query, context, new_lang, settings_view=True)
        return

    if data.startswith("set:service:"):
        service_key = data.rsplit(":", 1)[1]
        update_user_config(service_key=service_key)
        await _refresh_inline_menu(query, context, lang, settings_view=settings_view)
        return

    if data.startswith("set:cases:"):
        num_cases = int(data.rsplit(":", 1)[1])
        update_user_config(num_cases=num_cases)
        await _refresh_inline_menu(query, context, lang, settings_view=settings_view)
        return

    if data.startswith("set:interval:"):
        interval = int(data.rsplit(":", 1)[1])
        update_user_config(poll_interval_seconds=interval)
        await _refresh_inline_menu(query, context, lang, settings_view=True)
        return

    if data == "action:status":
        await _show_status(update, context)
        return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()
    if not _authorized(update, settings):
        return

    text = (update.message.text or "").strip()
    lang = _lang()

    if context.user_data.get(AWAITING_DATE):
        chat = update.effective_chat
        if chat is None:
            return

        try:
            parsed = date.fromisoformat(text)
        except ValueError:
            await update.message.reply_text(t("invalid_date", lang), parse_mode=PARSE_MODE)
            return

        applied = await _apply_date_change(context, chat.id, parsed, lang)
        if not applied:
            await update.message.reply_text(t("invalid_date_range", lang), parse_mode=PARSE_MODE)
        return

    if context.user_data.get(AWAITING_CAR_FIELD):
        chat = update.effective_chat
        if chat is None:
            return
        applied = await _apply_car_value(context, chat.id, text, lang)
        if not applied:
            await update.message.reply_text(t("invalid_car_value", lang), parse_mode=PARSE_MODE)
        return

    if text in button_texts("btn_start_search"):
        await _start_search(update, context)
        return

    if text in button_texts("btn_stop_search"):
        await _stop_search(update, context)
        return

    if text in button_texts("btn_show_panel") or text in button_texts("btn_menu"):
        await _show_monitor_panel(update, context)
        return

    if text in button_texts("btn_settings"):
        await settings_command(update, context, force_new=True)
        return

    if text in button_texts("btn_car_menu"):
        await _show_car_panel(update, context)
        return

    if text in button_texts("btn_car_status"):
        await _show_car_status(update, context)
        return


async def _set_bot_commands(application: Application) -> None:
    lang = _lang()
    await application.bot.set_my_commands(
        [
            BotCommand("start", t("cmd_start", lang)),
            BotCommand("menu", t("cmd_menu", lang)),
            BotCommand("monitor", t("cmd_monitor", lang)),
            BotCommand("stop", t("cmd_stop", lang)),
            BotCommand("settings", t("cmd_settings", lang)),
            BotCommand("car", t("cmd_car", lang)),
        ]
    )


async def _send_startup_menu(application: Application) -> None:
    settings = load_settings()
    lang = _lang()
    chat_id = int(settings.telegram_chat_id)
    await send_open_app(application, chat_id)
    await application.bot.send_message(
        chat_id=chat_id,
        text=t("main_intro", lang),
        reply_markup=_reply_keyboard(lang),
    )


class WidgetQueryHandler(BaseHandler):
    def check_update(self, update: object):
        if isinstance(update, Update):
            return update.api_kwargs.get("widget_query") or None
        return None


async def widget_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = dict(update.api_kwargs.get("widget_query") or {})
    query_id = raw.get("id")
    data = str(raw.get("data") or "")
    chat = raw.get("chat") or {}
    chat_id = chat.get("id")
    settings = load_settings()

    async def answer() -> None:
        if not query_id:
            return
        try:
            await context.bot.do_api_request("answerWidgetQuery", {"widget_query_id": query_id})
        except Exception:
            logger.exception("answerWidgetQuery failed")

    if chat_id is None or str(chat_id) != settings.telegram_chat_id:
        await answer()
        return

    if data.startswith("f:"):
        value = data[2:]
        if value in FUEL_LABELS or value == "":
            update_user_config(car_fuel_type=value)
        await answer()
        await present_car(context.application, chat_id)
        return

    if data.startswith("g:"):
        value = data[2:]
        if value in GEARBOX_LABELS or value == "":
            update_user_config(car_gearbox=value)
        await answer()
        await present_car(context.application, chat_id)
        return

    if data.startswith("svc:"):
        service_key = data[4:]
        if service_key in SERVICE_ORDER:
            update_user_config(service_key=service_key)
        await answer()
        await present_ticket(context.application, chat_id)
        return

    if data.startswith("n:"):
        try:
            num_cases = int(data[2:])
        except ValueError:
            num_cases = 0
        if num_cases in {1, 2, 3}:
            update_user_config(num_cases=num_cases)
        await answer()
        await present_ticket(context.application, chat_id)
        return

    await answer()


def build_application(token: str) -> Application:
    async def post_init(application: Application) -> None:
        start_webapp(application)
        await _set_bot_commands(application)
        url = _app_url()
        if url:
            try:
                await application.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="App", web_app=WebAppInfo(url=url))
                )
            except Exception:
                logger.exception("Could not set the Mini App menu button")
        try:
            await _send_startup_menu(application)
        except Exception:
            logger.exception("Failed to send startup menu")

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("car", car_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(WidgetQueryHandler(widget_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return application
