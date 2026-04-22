"""
ZIT Bot — /image Command Handler
Flow: /image → subject input → Groq prompt → fal-ai image → photo + caption

FSM: ImageFSM.subject (один стан — чекаємо тему)
"""

import os
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile

from bot.states import ImageFSM
from prompts import groq_generate
from bot.image_gen import generate_image

logger = logging.getLogger(__name__)
router = Router(name="image_cmd")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _is_ready_prompt(text: str) -> bool:
    """
    Визначає чи текст — вже готовий EN промпт (з /prompt або Mini App),
    чи коротка тема яку треба обробити через Groq.

    Критерії готового промпту:
    - довжина > 150 символів
    - >85% ASCII символів (англійський текст)
    """
    if len(text) <= 150:
        return False
    ascii_ratio = sum(1 for c in text if c.isascii()) / len(text)
    return ascii_ratio > 0.85


# ─── /image ENTRY ────────────────────────────────────────────────────────────

@router.message(Command("image"))
async def cmd_image(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    await state.set_state(ImageFSM.subject)
    await state.update_data(lang=lang)

    if lang == "ua":
        text = (
            "🖼 <b>Зображення за темою</b>\n\n"
            "Введи тему — опиши що намалювати.\n"
            "Можна українською — переведу автоматично.\n\n"
            "<i>Наприклад: дівчина під дощем у Токіо</i>"
        )
    else:
        text = (
            "🖼 <b>Image from subject</b>\n\n"
            "Enter a subject — describe what to generate.\n"
            "Any language works — I'll translate automatically.\n\n"
            "<i>Example: girl in the rain in Tokyo</i>"
        )
    await message.answer(text)


# ─── SUBJECT INPUT ───────────────────────────────────────────────────────────

@router.message(ImageFSM.subject)
async def on_subject(message: Message, state: FSMContext) -> None:
    subject = message.text.strip() if message.text else ""
    if not subject:
        await message.answer("⚠️ Введи текстову тему" if (await state.get_data()).get("lang") == "ua" else "⚠️ Please enter a text subject")
        return

    data = await state.get_data()
    lang = data.get("lang", "ua")

    # Очищаємо стан одразу — юзер може стартувати нову команду
    await state.clear()

    # ── Step 1: prompt generation або bypass ──────────────────────────────
    if _is_ready_prompt(subject):
        # Готовий EN промпт (скопійований з /prompt або Mini App) — пропускаємо Groq
        logger.info("Detected ready prompt — skipping Groq")
        positive = subject
        negative = ""
        notes    = ""
        wait_msg = await message.answer(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )
    else:
        # Коротка тема / UA текст — генеруємо промпт через Groq
        wait_msg = await message.answer(
            "⏳ Генерую промпт…" if lang == "ua" else "⏳ Generating prompt…"
        )
        state_for_groq = {
            "subject":      subject,
            "scene":        "portrait",
            "style":        "photorealistic",
            "lighting":     "Cinematic",
            "mood":         "",
            "genre":        "",
            "subject_type": "none",
            "lang":         lang,
        }
        try:
            prompt_result = await groq_generate(state_for_groq, GROQ_API_KEY)
        except Exception as e:
            logger.exception("groq_generate failed in /image")
            await wait_msg.edit_text(
                f"❌ Помилка генерації промпту: {str(e)[:120]}" if lang == "ua"
                else f"❌ Prompt generation error: {str(e)[:120]}"
            )
            return
        positive = prompt_result.get("positive", "")
        negative = prompt_result.get("negative", "")
        notes    = prompt_result.get("notes", "")

    # ── Step 2: image generation ───────────────────────────────────────────
    if not _is_ready_prompt(subject):
        # Оновлюємо повідомлення тільки якщо до цього показували "Генерую промпт"
        await wait_msg.edit_text(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )

    try:
        image_bytes = await generate_image(positive)
    except Exception as e:
        logger.exception("generate_image failed in /image")
        await wait_msg.edit_text(
            f"❌ Помилка генерації зображення: {str(e)[:120]}" if lang == "ua"
            else f"❌ Image generation error: {str(e)[:120]}"
        )
        return

    # ── Step 3: send result ────────────────────────────────────────────────
    await wait_msg.delete()

    caption = (
        f"🎯 <b>{subject}</b>\n\n"
        f"✦ <b>POSITIVE</b>\n"
        f"<code>{positive}</code>\n\n"
        f"✦ <b>NEGATIVE</b>\n"
        f"<code>{negative}</code>"
    )
    if notes:
        caption += f"\n\n💡 {notes}"

    # Telegram caption limit — 1024 символи
    if len(caption) > 1024:
        caption = caption[:1020] + "…"

    photo = BufferedInputFile(image_bytes, filename="image.png")
    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
