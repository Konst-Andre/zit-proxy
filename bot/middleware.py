"""
ZIT Bot — Cold Start Middleware
Відстежує час останнього запиту.
Якщо пройшло >14 хв (Render Free cold start) — попереджає юзера.
"""

import time
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Render Free засинає після ~15 хв неактивності
# KeepAlive пінгує кожні 14 хв — але між пінгами може бути gap
COLD_START_THRESHOLD = 14 * 60  # секунд

_last_request_time: float = time.monotonic()


class ColdStartMiddleware(BaseMiddleware):
    """
    Перед кожним message handler:
    - якщо з останнього запиту пройшло >14 хв → надсилає попередження
    - оновлює _last_request_time
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        global _last_request_time

        now     = time.monotonic()
        elapsed = now - _last_request_time
        _last_request_time = now

        if elapsed > COLD_START_THRESHOLD:
            lang = "ua"
            try:
                lc = (event.from_user.language_code or "").lower()
                lang = "ua" if lc.startswith("uk") else "en"
            except Exception:
                pass

            logger.info(
                "Cold start detected — elapsed: %.0fs | user: %s",
                elapsed,
                getattr(event.from_user, "id", "?"),
            )

            try:
                if lang == "ua":
                    await event.answer(
                        "⏳ <b>Перший запит після паузи</b>\n\n"
                        "Сервер прокидається — зачекай 15–20 секунд.\n"
                        "Наступні запити будуть швидкими.",
                        parse_mode="HTML",
                    )
                else:
                    await event.answer(
                        "⏳ <b>First request after idle</b>\n\n"
                        "Server is waking up — please wait 15–20 seconds.\n"
                        "Next requests will be fast.",
                        parse_mode="HTML",
                    )
            except Exception:
                pass  # не блокуємо обробку якщо попередження не відправилось

        return await handler(event, data)
