"""
ZIT Bot — /image Command Handler
Flow: /image → subject → Groq (якщо потрібно) → image → photo + кнопки

FSM: ImageFSM.subject → ImageFSM.result
Кнопки після результату:
  [ 🔄 Нова тема ] [ ↺ Повтор ]
  [   📋 Копіювати промпт     ]
"""

import os
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, BufferedInputFile,
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.states import ImageFSM
from prompts import groq_generate
from bot.image_gen import generate_image

logger = logging.getLogger(__name__)
router = Router(name="image_cmd")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

_CB_NEW   = "img:new"
_CB_REGEN = "img:regen"
_CB_COPY  = "img:copy"


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _is_ready_prompt(text: str) -> bool:
    if len(text) <= 150:
        return False
    return sum(1 for c in text if c.isascii()) / len(text) > 0.85


def _result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Нова тема" if lang == "ua" else "🔄 New topic",
                callback_data=_CB_NEW,
            ),
            InlineKeyboardButton(
                text="↺ Повтор" if lang == "ua" else "↺ Repeat",
                callback_data=_CB_REGEN,
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Копіювати промпт" if lang == "ua" else "📋 Copy prompt",
                callback_data=_CB_COPY,
            ),
        ],
    ])


# ─── CORE LOGIC ───────────────────────────────────────────────────────────────

async def _generate_and_send(
    message: Message,
    state: FSMContext,
    subject: str,
    scene: str,
    lang: str,
) -> None:
    """
    Генерація + відправка результату + збереження стану для кнопок.
    Викликається з on_subject і cb_regen.
    """
    # ── Step 1 ────────────────────────────────────────────────────────────
    if _is_ready_prompt(subject):
        logger.info("Ready prompt detected — skipping Groq")
        positive = subject
        negative = ""
        wait_msg = await message.answer(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )
    else:
        wait_msg = await message.answer(
            "⏳ Генерую промпт…" if lang == "ua" else "⏳ Generating prompt…"
        )
        try:
            result = await groq_generate({
                "subject": subject, "scene": scene,
                "style": "photorealistic", "lighting": "Cinematic",
                "mood": "", "genre": "", "subject_type": "none", "lang": lang,
            }, GROQ_API_KEY)
        except Exception as e:
            logger.exception("groq_generate failed")
            await wait_msg.edit_text(
                f"❌ Помилка промпту: {str(e)[:120]}" if lang == "ua"
                else f"❌ Prompt error: {str(e)[:120]}"
            )
            return
        positive = result.get("positive", "")
        negative = result.get("negative", "")
        await wait_msg.edit_text(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )

    # ── Step 2 ────────────────────────────────────────────────────────────
    try:
        image_bytes = await generate_image(positive, scene=scene)
    except Exception as e:
        logger.exception("generate_image failed")
        await wait_msg.edit_text(
            f"❌ Помилка зображення: {str(e)[:120]}" if lang == "ua"
            else f"❌ Image error: {str(e)[:120]}"
        )
        return

    await wait_msg.delete()

    # ── Step 3 — зберігаємо + відправляємо ───────────────────────────────
    await state.set_state(ImageFSM.result)
    await state.update_data(
        subject=subject, positive=positive,
        negative=negative, scene=scene, lang=lang,
    )

    caption = (
        f"🎯 <b>{subject}</b>\n\n"
        f"✦ <b>POSITIVE</b>\n<code>{positive}</code>\n\n"
        f"✦ <b>NEGATIVE</b>\n<code>{negative}</code>"
    )
    if len(caption) > 1024:
        caption = caption[:1020] + "…"

    await message.answer_photo(
        photo=BufferedInputFile(image_bytes, filename="image.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=_result_keyboard(lang),
    )


# ─── /image ENTRY ────────────────────────────────────────────────────────────

@router.message(Command("image"))
async def cmd_image(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    await state.set_state(ImageFSM.subject)
    await state.update_data(lang=lang)

    await message.answer(
        "🖼 <b>Зображення за темою</b>\n\n"
        "Введи тему або готовий EN промпт.\n"
        "Можна українською — переведу автоматично.\n\n"
        "<i>Наприклад: дівчина під дощем у Токіо</i>"
        if lang == "ua" else
        "🖼 <b>Image from subject</b>\n\n"
        "Enter a subject or a ready EN prompt.\n"
        "Any language works — I'll translate.\n\n"
        "<i>Example: girl in the rain in Tokyo</i>"
    )


# ─── SUBJECT INPUT ───────────────────────────────────────────────────────────

@router.message(ImageFSM.subject)
async def on_subject(message: Message, state: FSMContext) -> None:
    subject = message.text.strip() if message.text else ""
    data = await state.get_data()
    lang = data.get("lang", "ua")

    if not subject:
        await message.answer(
            "⚠️ Введи текстову тему" if lang == "ua"
            else "⚠️ Please enter a text subject"
        )
        return

    await _generate_and_send(message, state, subject, "portrait", lang)


# ─── RESULT CALLBACKS ────────────────────────────────────────────────────────

@router.callback_query(ImageFSM.result, F.data == _CB_NEW)
async def cb_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Повний reset — просимо нову тему."""
    data = await state.get_data()
    lang = data.get("lang", "ua")
    await state.set_state(ImageFSM.subject)
    await callback.answer()
    await callback.message.answer(
        "🖼 Введи нову тему:" if lang == "ua" else "🖼 Enter new subject:"
    )


@router.callback_query(ImageFSM.result, F.data == _CB_REGEN)
async def cb_regen(callback: CallbackQuery, state: FSMContext) -> None:
    """Той самий промпт → новий запит до image генератора."""
    data = await state.get_data()
    lang     = data.get("lang", "ua")
    subject  = data.get("subject", "")
    scene    = data.get("scene", "portrait")

    await callback.answer()
    await _generate_and_send(callback.message, state, subject, scene, lang)


@router.callback_query(ImageFSM.result, F.data == _CB_COPY)
async def cb_copy(callback: CallbackQuery, state: FSMContext) -> None:
    """Відправляє positive як окреме повідомлення — юзер може скопіювати."""
    data     = await state.get_data()
    lang     = data.get("lang", "ua")
    positive = data.get("positive", "")

    await callback.answer(
        "Промпт надіслано ↓" if lang == "ua" else "Prompt sent ↓",
        show_alert=False,
    )
    await callback.message.answer(
        f"<code>{positive}</code>",
        parse_mode="HTML",
    )
