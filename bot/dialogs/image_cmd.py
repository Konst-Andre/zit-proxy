"""
ZIT Bot — /image Command Handler
Flow: /image → subject → Groq → Pollinations → photo + buttons

FSM: ImageFSM.subject → ImageFSM.result
Buttons:
  Row 1: [🔄 Нова тема] [↺ Повтор]
  Row 2: [📋 Копіювати промпт]
"""

import os
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, BufferedInputFile, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.states import ImageFSM
from prompts import groq_generate
from bot.image_gen import generate_image

logger = logging.getLogger(__name__)
router = Router(name="image_cmd")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _detect_lang_cb(callback: CallbackQuery) -> str:
    lc = (callback.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _is_ready_prompt(text: str) -> bool:
    if len(text) <= 150:
        return False
    return sum(1 for c in text if c.isascii()) / len(text) > 0.85


def _detect_scene(subject: str) -> str:
    s = subject.lower()
    if any(w in s for w in ["landscape", "пейзаж", "ліс", "forest", "гори", "mountain", "море", "ocean", "sea", "місто", "city", "вулиця", "поле", "field", "річка", "озеро", "природа", "nature"]):
        return "landscape"
    if any(w in s for w in ["full body", "на повний зріст", "стоїть", "standing", "іде", "йде", "walking", "running", "біжить", "танцює", "dancing"]):
        return "full_body"
    if any(w in s for w in ["interior", "кімната", "room", "cafe", "кафе", "office", "офіс", "library", "бібліотека", "kitchen", "кухня"]):
        return "interior"
    if any(w in s for w in ["animal", "тварина", "кіт", "cat", "пес", "dog", "кінь", "horse", "вовк", "wolf", "птах", "bird"]):
        return "animal"
    if any(w in s for w in ["urban", "alley", "провулок", "downtown", "subway", "метро"]):
        return "urban"
    if any(w in s for w in ["product", "продукт", "watch", "годинник", "perfume", "парфум", "bottle", "пляшка"]):
        return "product"
    return "portrait"


def _result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Нова тема" if lang == "ua" else "🔄 New topic", callback_data="img:new"),
            InlineKeyboardButton(text="↺ Повтор"    if lang == "ua" else "↺ Repeat",    callback_data="img:regen"),
        ],
        [
            InlineKeyboardButton(text="📋 Копіювати промпт" if lang == "ua" else "📋 Copy prompt", callback_data="img:copy"),
        ],
    ])


async def _run_image(message: Message, subject: str, lang: str, state: FSMContext) -> None:
    """Core pipeline: subject → Groq → Pollinations → photo + buttons."""
    scene = _detect_scene(subject)

    # ── Step 1: prompt ────────────────────────────────────────────────────
    if _is_ready_prompt(subject):
        logger.info("Detected ready prompt — skipping Groq")
        positive, negative, notes = subject, "", ""
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
            logger.exception("groq_generate failed in /image")
            await wait_msg.edit_text(
                f"❌ Помилка генерації промпту: {str(e)[:120]}" if lang == "ua"
                else f"❌ Prompt generation error: {str(e)[:120]}"
            )
            return
        positive = result.get("positive", "")
        negative = result.get("negative", "")
        notes    = result.get("notes", "")
        await wait_msg.edit_text(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )

    # ── Step 2: image ─────────────────────────────────────────────────────
    try:
        image_bytes = await generate_image(positive, scene=scene)
    except Exception as e:
        logger.exception("generate_image failed in /image")
        await wait_msg.edit_text(
            f"❌ Помилка зображення: {str(e)[:120]}" if lang == "ua"
            else f"❌ Image error: {str(e)[:120]}"
        )
        return

    await wait_msg.delete()

    # ── Step 3: зберегти стан + відправити ───────────────────────────────
    await state.set_state(ImageFSM.result)
    await state.update_data(subject=subject, positive=positive, scene=scene, lang=lang)

    caption = (
        f"🎯 <b>{subject}</b>\n\n"
        f"✦ <b>POSITIVE</b>\n<code>{positive}</code>\n\n"
        f"✦ <b>NEGATIVE</b>\n<code>{negative}</code>"
    )
    if notes:
        caption += f"\n\n💡 {notes}"
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
        "🖼 <b>Зображення за темою</b>\n\nВведи тему — опиши що намалювати.\nМожна українською — переведу автоматично.\n\n<i>Наприклад: дівчина під дощем у Токіо</i>"
        if lang == "ua" else
        "🖼 <b>Image from subject</b>\n\nEnter a subject — describe what to generate.\nAny language works.\n\n<i>Example: girl in the rain in Tokyo</i>"
    )


# ─── SUBJECT INPUT ───────────────────────────────────────────────────────────

@router.message(ImageFSM.subject)
async def on_subject(message: Message, state: FSMContext) -> None:
    subject = message.text.strip() if message.text else ""
    data = await state.get_data()
    lang = data.get("lang", "ua")
    if not subject:
        await message.answer("⚠️ Введи текстову тему" if lang == "ua" else "⚠️ Please enter a text subject")
        return
    await _run_image(message, subject, lang, state)


# ─── CALLBACKS ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "img:new")
async def cb_img_new(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _detect_lang_cb(callback)
    await state.set_state(ImageFSM.subject)
    await state.update_data(lang=lang)
    try:
        await callback.answer()
    except Exception:
        pass
    await callback.message.answer(
        "🖼 Введи нову тему:" if lang == "ua" else "🖼 Enter a new subject:"
    )


@router.callback_query(F.data == "img:regen")
async def cb_img_regen(callback: CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    subject = data.get("subject", "")
    lang    = data.get("lang", "ua")
    try:
        await callback.answer()
    except Exception:
        pass
    if not subject:
        await callback.message.answer("Немає теми для повтору" if lang == "ua" else "No subject to repeat")
        return
    await _run_image(callback.message, subject, lang, state)


@router.callback_query(F.data == "img:copy")
async def cb_img_copy(callback: CallbackQuery, state: FSMContext) -> None:
    data     = await state.get_data()
    positive = data.get("positive", "")
    lang     = data.get("lang", "ua")
    if not positive:
        try:
            await callback.answer("Промпт недоступний" if lang == "ua" else "Prompt not available")
        except Exception:
            pass
        return
    await callback.message.answer(
        f"📋 <b>Positive prompt:</b>\n\n<code>{positive}</code>",
        parse_mode="HTML",
    )
    try:
        await callback.answer("✓" )
    except Exception:
        pass
