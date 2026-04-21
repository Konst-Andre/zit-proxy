"""
ZIT Bot — Inline Query Handler
@bot <subject> → groq_generate() → InlineQueryResultArticle

Usage:
  @zit_prompt_bot cyberpunk girl neon rain
  @zit_prompt_bot дівчина під дощем у Токіо
"""

import os
import logging

from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from prompts import groq_generate

logger = logging.getLogger(__name__)
router = Router(name="inline")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Мінімальна довжина запиту — щоб не генерувати на кожен символ
MIN_QUERY_LEN = 3


def _detect_lang(query: InlineQuery) -> str:
    lc = (query.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _build_state(subject: str, lang: str) -> dict:
    """Default state for inline — no FSM, fixed params."""
    return {
        "subject":      subject,
        "scene":        "portrait",
        "style":        "photorealistic",
        "lighting":     "Cinematic",
        "mood":         "",
        "genre":        "",
        "subject_type": "none",
        "lang":         lang,
    }


def _format_inline_message(subject: str, result: dict, lang: str) -> str:
    """Format result as a clean shareable message."""
    if "error" in result:
        err = result["error"]
        return f"❌ {err}" if lang == "en" else f"❌ Помилка: {err}"

    positive = result.get("positive", "")
    negative = result.get("negative", "")
    notes    = result.get("notes", "")

    text = (
        f"🎯 <b>{subject}</b>\n\n"
        f"✦ <b>POSITIVE</b>\n"
        f"<code>{positive}</code>\n\n"
        f"✦ <b>NEGATIVE</b>\n"
        f"<code>{negative}</code>"
    )
    if notes:
        text += f"\n\n💡 {notes}"
    return text


@router.inline_query()
async def handle_inline(query: InlineQuery) -> None:
    subject = query.query.strip()

    # Empty or too short — show hint
    if len(subject) < MIN_QUERY_LEN:
        hint_text = (
            "Введи тему для генерації промпту…"
            if query.from_user.language_code and query.from_user.language_code.startswith("uk")
            else "Type a subject to generate a prompt…"
        )
        await query.answer(
            results=[],
            switch_pm_text=hint_text,
            switch_pm_parameter="inline_hint",
            cache_time=1,
        )
        return

    lang = _detect_lang(query)
    state = _build_state(subject, lang)

    try:
        result = await groq_generate(state, GROQ_API_KEY)
    except Exception as e:
        logger.exception("groq_generate failed in inline handler")
        result = {"error": str(e)[:150]}

    message_text = _format_inline_message(subject, result, lang)

    positive_preview = result.get("positive", "")[:120] + "…" if result.get("positive") else "—"

    title       = "✦ Prompt generated" if lang == "en" else "✦ Промпт згенеровано"
    description = positive_preview

    article = InlineQueryResultArticle(
        id="1",
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            parse_mode="HTML",
        ),
    )

    # cache_time=1 — не кешуємо, кожен запит унікальний
    await query.answer(
        results=[article],
        cache_time=1,
        is_personal=True,
    )
