from __future__ import annotations

import asyncio
import json
import logging
import time
import zlib

import requests
from telegram import InputFile
from telegram.error import RetryAfter
from telegram.ext import Application

from i18n import Language
from ui_format import (
    PANEL_WIDGET_HTML,
    STATUS_WIDGET_HTML,
    car_alert_caption,
    car_alert_widget_html,
    car_card_caption,
    status_widget_caption,
    status_widget_chat_data,
    ticket_alert_caption,
    ticket_alert_widget_html,
)

logger = logging.getLogger(__name__)

# Bot API 10.4 limits for the widget's HTML source.
WIDGET_HTML_LIMIT = 32768
WIDGET_HTML_COMPRESSED_LIMIT = 4096

CARD_MESSAGE_ID = "status_card_message_id"
CARD_DRAWN_STATE = "status_card_drawn_state"
TICKET_PANEL_ID = "ticket_panel_widget_id"
CAR_PANEL_ID = "car_panel_widget_id"


def _widget_fits(html_text: str) -> bool:
    raw = len(html_text.encode("utf-8"))
    compressed = len(zlib.compress(html_text.encode("utf-8"), 9))
    if raw > WIDGET_HTML_LIMIT or compressed > WIDGET_HTML_COMPRESSED_LIMIT:
        logger.warning(
            "Widget HTML too large | raw=%d | compressed=%d", raw, compressed
        )
        return False
    return True


async def send_alert_widget(
    application: Application,
    chat_id: int,
    html_text: str,
    caption: str,
    reply_markup=None,
) -> bool:
    """Sends an alert as a widget. Returns False when the caller must fall back to a text alert."""
    if not _widget_fits(html_text):
        return False

    api_kwargs = {
        "chat_id": chat_id,
        "html": html_text,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        api_kwargs["reply_markup"] = reply_markup.to_dict()

    try:
        await application.bot.do_api_request("sendWidget", api_kwargs)
        return True
    except Exception as exc:
        logger.warning("sendWidget failed | %s", exc)
        return False


async def send_ticket_alert_widget(
    application: Application, chat_id: int, lang: Language, settings, new_slots, reply_markup=None
) -> bool:
    return await send_alert_widget(
        application,
        chat_id,
        ticket_alert_widget_html(lang, settings, new_slots),
        ticket_alert_caption(lang, settings, new_slots),
        reply_markup,
    )


def _download_photo(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/") or len(response.content) < 1000:
        raise ValueError(f"Unexpected photo response {content_type} {len(response.content)}")
    if len(response.content) > 9_000_000:
        raise ValueError("Photo is too large")
    return response.content


async def _send_car_card(application: Application, chat_id: int, caption: str, item) -> None:
    photo = None
    if item.image_url:
        try:
            photo = await asyncio.to_thread(_download_photo, item.image_url)
        except Exception:
            logger.warning("Car photo was not downloaded | id=%s", item.listing_id, exc_info=True)
    if photo:
        try:
            await application.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo, filename="car.jpg"),
                caption=caption,
                parse_mode="HTML",
            )
            return
        except RetryAfter:
            raise
        except Exception:
            logger.warning("Car photo was not sent | id=%s", item.listing_id, exc_info=True)
    await application.bot.send_message(
        chat_id=chat_id,
        text=caption,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )


async def _deliver_car_card(application: Application, chat_id: int, caption: str, item) -> bool:
    for _attempt in range(4):
        try:
            await _send_car_card(application, chat_id, caption, item)
            return True
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
        except Exception:
            logger.exception("Car card was not sent | id=%s", item.listing_id)
            return False
    logger.error("Car card was not sent after retries | id=%s", item.listing_id)
    return False


async def send_car_cards(application: Application, chat_id: int, lang: Language, new_listings, price_drops):
    sent_new = []
    sent_drops = []
    for item in new_listings:
        if await _deliver_car_card(application, chat_id, car_card_caption(lang, item), item):
            sent_new.append(item)
        await asyncio.sleep(0.35)
    for item, previous in price_drops:
        if await _deliver_car_card(application, chat_id, car_card_caption(lang, item, previous), item):
            sent_drops.append((item, previous))
        await asyncio.sleep(0.35)
    return sent_new, sent_drops


async def send_car_alert_widget(
    application: Application,
    chat_id: int,
    lang: Language,
    info,
    new_listings,
    price_drops,
) -> bool:
    return await send_alert_widget(
        application,
        chat_id,
        car_alert_widget_html(lang, info, new_listings, price_drops),
        car_alert_caption(lang, info, new_listings, price_drops),
    )


def _drawn_state(chat_data: str) -> str:
    """The part of the widget state the card actually draws, without the time-derived fields."""
    state = json.loads(chat_data)
    for key in ("t", "n"):
        state.pop(key, None)
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


async def _edit_status_card(application: Application, chat_id: int, message_id: int, state: str) -> bool:
    try:
        await application.bot.do_api_request(
            "editMessageWidgetData",
            {"chat_id": chat_id, "message_id": message_id, "chat_data": state},
        )
        return True
    except Exception as exc:
        logger.warning("editMessageWidgetData failed | %s", exc)
        return False


async def _send_status_card(
    application: Application,
    chat_id: int,
    lang: Language,
    ticket_searches: list,
    car_searches: list,
    checked_at: int,
) -> int | None:
    state = status_widget_chat_data(lang, ticket_searches, car_searches, checked_at)
    if not _widget_fits(STATUS_WIDGET_HTML):
        return None
    try:
        message = await application.bot.do_api_request(
            "sendWidget",
            {
                "chat_id": chat_id,
                "html": STATUS_WIDGET_HTML,
                "chat_data": state,
                "caption": status_widget_caption(lang, ticket_searches, car_searches, checked_at),
                "parse_mode": "HTML",
            },
        )
    except Exception as exc:
        logger.warning("sendWidget (status card) failed | %s", exc)
        return None
    return message["message_id"]


def _unchanged(exc: Exception) -> bool:
    return "not modified" in str(exc).lower()


async def _edit_interactive_widget(
    application: Application,
    chat_id: int,
    message_id: int,
    state: str,
    reply_markup,
) -> bool:
    try:
        await application.bot.do_api_request(
            "editMessageWidgetData",
            {"chat_id": chat_id, "message_id": message_id, "chat_data": state},
        )
    except Exception as exc:
        if not _unchanged(exc):
            logger.warning("editMessageWidgetData (panel) failed | %s", exc)
            return False
    if reply_markup is None:
        return True
    try:
        await application.bot.do_api_request(
            "editMessageReplyMarkup",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": reply_markup.to_dict(),
            },
        )
    except Exception as exc:
        if not _unchanged(exc):
            logger.warning("editMessageReplyMarkup (panel) failed | %s", exc)
    return True


async def upsert_panel_widget(
    application: Application,
    chat_id: int,
    storage_key: str,
    state: str,
    caption: str,
    reply_markup,
) -> int | None:
    """Sends or redraws an interactive menu widget. The HTML stays fixed; only chat_data changes."""
    if not _widget_fits(PANEL_WIDGET_HTML):
        return None
    chat_data = application.chat_data[chat_id]
    message_id = chat_data.get(storage_key)
    if message_id is not None and await _edit_interactive_widget(
        application, chat_id, message_id, state, reply_markup
    ):
        return message_id

    try:
        message = await application.bot.do_api_request(
            "sendWidget",
            {
                "chat_id": chat_id,
                "html": PANEL_WIDGET_HTML,
                "chat_data": state,
                "caption": caption,
                "parse_mode": "HTML",
                "allow_queries": True,
                "reply_markup": reply_markup.to_dict() if reply_markup is not None else None,
            },
        )
    except Exception as exc:
        logger.warning("sendWidget (panel) failed | %s", exc)
        return None
    message_id = message["message_id"]
    chat_data[storage_key] = message_id
    return message_id


async def refresh_status_card(application: Application, chat_id: int, lang: Language) -> None:
    """Redraws the live status card, creating it on the first change of state."""
    from car_session import get_car_manager
    from search_session import get_search_manager

    ticket_searches = get_search_manager(application).list_active()
    car_searches = get_car_manager(application).list_active()
    checked_at = int(time.time())

    chat_data = application.chat_data[chat_id]
    state = status_widget_chat_data(lang, ticket_searches, car_searches, checked_at)
    drawn = _drawn_state(state)
    if chat_data.get(CARD_DRAWN_STATE) == drawn:
        return

    message_id = chat_data.get(CARD_MESSAGE_ID)
    if message_id is not None:
        if await _edit_status_card(application, chat_id, message_id, state):
            chat_data[CARD_DRAWN_STATE] = drawn
            return
        chat_data.pop(CARD_MESSAGE_ID, None)

    message_id = await _send_status_card(application, chat_id, lang, ticket_searches, car_searches, checked_at)
    if message_id is not None:
        chat_data[CARD_MESSAGE_ID] = message_id
        chat_data[CARD_DRAWN_STATE] = drawn
