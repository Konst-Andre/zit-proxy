"""
ZIT Bot — /random Handler
Randomizes all parameters and generates immediately.
Adds inline "🔀 Ще раз / Again" button after result.
"""

import os
import random
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from data import (
    RANDOM_POOL, RANDOM_SCENES, RANDOM_STYLES,
    RANDOM_LIGHTINGS, RANDOM_MOODS, RANDOM_GENRES,
    SCENES, STYLES, LIGHTINGS, MOODS, GENRES,
)
from prompts import groq_generate
from bot.dialogs.result import format_result_message

logger = logging.getLogger(__name__)
router = Router(name="random")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Callback data prefix для кнопки "Ще раз"
_CB_RANDOM_AGAIN = "random:again"


def _detect_lang_from_user(user) -> str:
    lc = (user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _detect_lang(message: Message) -> str:
    return _detect_lang_from_user(message.from_user)


def _random_state(lang: str) -> dict:
    scene    = random.choice(RANDOM_SCENES)
    style    = random.choice(RANDOM_STYLES)
    lighting = random.choice(RANDOM_LIGHTINGS) if random.random() < 0.8 else ""
    mood     = random.choice(RANDOM_MOODS)     if random.random() < 0.5 else ""
    genre    = random.choice(RANDOM_GENRES)    if random.random() < 0.5 else ""
    pool     = RANDOM_POOL.get(scene, RANDOM_POOL["portrait"])
    subject  = random.choice(pool)

    return {
        "scene":    scene,
        "style":    style,
        "lighting": lighting,
        "mood":     mood,
        "genre":    genre,
        "subject":  subject,
        "lang":     lang,
    }


def _again_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = "🔀 Ще раз" if lang == "ua" else "🔀 Again"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data=_CB_RANDOM_AGAIN),
    ]])


async def _run_random(
    lang: str,
    wait_msg,           # message to edit during generation
    reply_target,       # message to answer final result to
) -> None:
    """
    Core random generation logic shared by /random command and callback.
    wait_msg   — already sent "⏳ Рандомізую..." message (will be edited)
    reply_target — original message for final answer
    """
    state = _random_state(lang)

    sc = SCENES[state["scene"]]["label"]
    st = STYLES[state["style"]]["label"]
    li = LIGHTINGS.get(state["lighting"], {}).get("label", "—") if state["lighting"] else "—"
    mo = MOODS.get(state["mood"],     {}).get("label", "—") if state["mood"]     else "—"
    ge = GENRES.get(state["genre"],   {}).get("label", "—") if state["genre"]   else "—"

    params_preview = f"📐 {sc} · 🎨 {st} · 💡 {li} · 🌙 {mo} · 🌐 {ge}"
    await wait_msg.edit_text(
        f"🎲 <b>Тема:</b> {state['subject']}\n{params_preview}\n\n⏳ Генерація…",
        parse_mode="HTML",
    )

    try:
        result = await groq_generate(state, GROQ_API_KEY)
    except Exception as e:
        logger.exception("groq_generate failed in /random")
        result = {"error": str(e)[:200]}

    text = format_result_message(state, result, lang)
    kb   = _again_keyboard(lang)

    # Edit wait_msg with result + keyboard
    await wait_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ─── /random COMMAND ─────────────────────────────────────────────────────────

@router.message(Command("random"))
async def cmd_random(message: Message) -> None:
    lang     = _detect_lang(message)
    wait_msg = await message.answer(
        "🎲 Рандомізую параметри…" if lang == "ua" else "🎲 Randomizing parameters…"
    )
    await _run_random(lang, wait_msg, message)


# ─── CALLBACK — "Ще раз / Again" BUTTON ─────────────────────────────────────

@router.callback_query(F.data == _CB_RANDOM_AGAIN)
async def cb_random_again(callback: CallbackQuery) -> None:
    """
    Re-runs full random generation with new params.
    Edits the existing result message → no chat spam.
    """
    lang = _detect_lang_from_user(callback.from_user)

    # Replace keyboard with loading text immediately
    await callback.message.edit_text(
        "🎲 Рандомізую параметри…" if lang == "ua" else "🎲 Randomizing parameters…",
        reply_markup=None,
    )
    await callback.answer()  # dismiss loading spinner on button

    await _run_random(lang, callback.message, callback.message)
