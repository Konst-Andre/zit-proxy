"""
ZIT Bot — /random Handler
Randomizes all parameters and generates immediately.
No FSM dialog — simple message handler.
"""

import os
import random
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from data import (
    RANDOM_POOL, RANDOM_SCENES, RANDOM_STYLES,
    RANDOM_LIGHTINGS, RANDOM_MOODS, RANDOM_GENRES,
)
from prompts import groq_generate
from bot.dialogs.result import format_result_message

logger = logging.getLogger(__name__)
router = Router(name="random")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _random_state(lang: str) -> dict:
    scene   = random.choice(RANDOM_SCENES)
    style   = random.choice(RANDOM_STYLES)
    # 80% chance of lighting, 20% none
    lighting = random.choice(RANDOM_LIGHTINGS) if random.random() < 0.8 else ""
    # 50% chance of mood
    mood    = random.choice(RANDOM_MOODS) if random.random() < 0.5 else ""
    # 50% chance of genre
    genre   = random.choice(RANDOM_GENRES) if random.random() < 0.5 else ""
    # Subject from scene pool
    pool    = RANDOM_POOL.get(scene, RANDOM_POOL["portrait"])
    subject = random.choice(pool)

    return {
        "scene":    scene,
        "style":    style,
        "lighting": lighting,
        "mood":     mood,
        "genre":    genre,
        "subject":  subject,
        "lang":     lang,
    }


@router.message(Command("random"))
async def cmd_random(message: Message) -> None:
    lang = _detect_lang(message)
    wait_msg = await message.answer("🎲 Рандомізую параметри…" if lang == "ua" else "🎲 Randomizing parameters…")

    state = _random_state(lang)
    from data import SCENES, STYLES, LIGHTINGS, MOODS, GENRES
    sc = SCENES[state["scene"]]["label"]
    st = STYLES[state["style"]]["label"]
    li = LIGHTINGS.get(state["lighting"], {}).get("label", "—") if state["lighting"] else "—"
    mo = MOODS.get(state["mood"], {}).get("label", "—") if state["mood"] else "—"
    ge = GENRES.get(state["genre"], {}).get("label", "—") if state["genre"] else "—"

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
    await wait_msg.edit_text(text, parse_mode="HTML")
