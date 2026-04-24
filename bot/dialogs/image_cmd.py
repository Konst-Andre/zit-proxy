"""
ZIT Bot — /image Command Handler
Flow: /image → subject → scene selection → generate → photo + buttons

FSM: ImageFSM.subject → ImageFSM.scene → ImageFSM.result

Scene keyboard:
  [ 👤 Portrait ] [ 🧍 Full body ] [ 🏞 Landscape ]
  [ 📦 Product  ] [ 🐾 Animal    ] [ 💡 Concept   ]
  [        🎯 Авто-визначити         ]

Result keyboard:
  [ 🔄 Нова тема ] [ ↺ Повтор ]
  [   📋 Копіювати промпт      ]
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

# ─── SCENE CONFIG ─────────────────────────────────────────────────────────────

SCENE_BUTTONS = [
    # (callback_data, label_ua, label_en)
    ("portrait",  "👤 Портрет",    "👤 Portrait"),
    ("full_body", "🧍 Повний зріст","🧍 Full body"),
    ("landscape", "🏞 Пейзаж",     "🏞 Landscape"),
    ("product",   "📦 Продукт",    "📦 Product"),
    ("animal",    "🐾 Тварина",    "🐾 Animal"),
    ("concept",   "💡 Концепт",    "💡 Concept"),
]


def _scene_keyboard(lang: str) -> InlineKeyboardMarkup:
    idx = 2 if lang == "ua" else 1  # label index
    buttons = [
        InlineKeyboardButton(
            text=s[idx],
            callback_data=f"img_scene:{s[0]}",
        )
        for s in SCENE_BUTTONS
    ]
    auto_label = "🎯 Авто-визначити" if lang == "ua" else "🎯 Auto-detect"
    return InlineKeyboardMarkup(inline_keyboard=[
        [buttons[0], buttons[1]],   # Portrait    | Full body
        [buttons[2], buttons[3]],   # Landscape   | Product
        [buttons[4], buttons[5]],   # Animal      | Concept
        [InlineKeyboardButton(text=auto_label, callback_data="img_scene:auto")],
    ])


def _result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Нова тема" if lang == "ua" else "🔄 New topic",
                callback_data="img:new",
            ),
            InlineKeyboardButton(
                text="↺ Повтор" if lang == "ua" else "↺ Repeat",
                callback_data="img:regen",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Копіювати промпт" if lang == "ua" else "📋 Copy prompt",
                callback_data="img:copy",
            ),
        ],
    ])


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _is_ready_prompt(text: str) -> bool:
    """Готовий EN промпт (з /prompt або Mini App) — пропустити Groq."""
    if len(text) <= 150:
        return False
    return sum(1 for c in text if c.isascii()) / len(text) > 0.85


def _detect_scene(subject: str) -> str:
    """Авто-визначення сцени по ключових словах."""
    s = subject.lower()
    if any(w in s for w in ["landscape", "пейзаж", "ліс", "forest", "гори", "mountain",
                             "море", "ocean", "sea", "місто", "city", "вулиця", "поле",
                             "field", "річка", "озеро", "природа", "nature"]):
        return "landscape"
    if any(w in s for w in ["full body", "на повний зріст", "стоїть", "standing",
                             "іде", "йде", "walking", "running", "біжить", "танцює", "dancing"]):
        return "full_body"
    if any(w in s for w in ["interior", "кімната", "room", "cafe", "кафе",
                             "office", "офіс", "library", "бібліотека", "kitchen", "кухня"]):
        return "interior"
    if any(w in s for w in ["animal", "тварина", "кіт", "cat", "пес", "dog",
                             "кінь", "horse", "вовк", "wolf", "птах", "bird"]):
        return "animal"
    if any(w in s for w in ["urban", "alley", "провулок", "downtown", "subway", "метро"]):
        return "urban"
    if any(w in s for w in ["морозиво", "ice cream", "торт", "cake", "піца", "pizza",
                             "кава", "coffee", "їжа", "food", "напій", "drink", "juice",
                             "сік", "бургер", "burger", "суші", "sushi", "десерт", "dessert",
                             "шоколад", "chocolate", "печиво", "cookie", "хліб", "bread"]):
        return "product"
    if any(w in s for w in ["product", "продукт", "watch", "годинник",
                             "perfume", "парфум", "bottle", "пляшка"]):
        return "product"
    return "portrait"


# ─── CORE GENERATION ──────────────────────────────────────────────────────────

async def _run_image(
    message: Message,
    state: FSMContext,
    subject: str,
    scene: str,
    lang: str,
) -> None:
    """Groq (якщо потрібно) → image → зберегти стан → відправити з кнопками."""

    # Step 1 — prompt
    if _is_ready_prompt(subject):
        logger.info("Ready prompt — skipping Groq | scene=%s", scene)
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
            logger.exception("groq_generate failed")
            await wait_msg.edit_text(
                f"❌ Помилка промпту: {str(e)[:120]}" if lang == "ua"
                else f"❌ Prompt error: {str(e)[:120]}"
            )
            return
        positive = result.get("positive", "")
        negative = result.get("negative", "")
        notes    = result.get("notes", "")
        await wait_msg.edit_text(
            "🎨 Генерую зображення…" if lang == "ua" else "🎨 Generating image…"
        )

    # Step 2 — image
    try:
        image_bytes = await generate_image(positive, scene=scene)
    except Exception as e:
        logger.exception("generate_image failed | scene=%s", scene)
        await wait_msg.edit_text(
            f"❌ Помилка зображення: {str(e)[:120]}" if lang == "ua"
            else f"❌ Image error: {str(e)[:120]}"
        )
        return

    await wait_msg.delete()

    # Step 3 — save state + send
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


# ─── STEP 1 — SUBJECT INPUT ───────────────────────────────────────────────────

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

    # Зберігаємо тему → переходимо до вибору сцени
    await state.set_state(ImageFSM.scene)
    await state.update_data(subject=subject)

    prompt_line = (
        "🎬 <b>Обери тип сцени</b>\n\n"
        f"Тема: <i>{subject[:80]}</i>\n\n"
        "Або натисни «Авто» — визначу автоматично."
        if lang == "ua" else
        "🎬 <b>Choose scene type</b>\n\n"
        f"Subject: <i>{subject[:80]}</i>\n\n"
        "Or tap «Auto» — I'll detect automatically."
    )
    await message.answer(prompt_line, reply_markup=_scene_keyboard(lang))


# ─── STEP 2 — SCENE SELECTION ────────────────────────────────────────────────

@router.callback_query(ImageFSM.scene, F.data.startswith("img_scene:"))
async def on_scene_selected(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await callback.answer()
    except Exception:
        pass

    data    = await state.get_data()
    lang    = data.get("lang", "ua")
    subject = data.get("subject", "")
    scene_val = callback.data.split(":", 1)[1]

    # Авто-визначення якщо юзер натиснув "Авто"
    scene = _detect_scene(subject) if scene_val == "auto" else scene_val

    # Видаляємо повідомлення з кнопками сцен
    try:
        await callback.message.delete()
    except Exception:
        pass

    await _run_image(callback.message, state, subject, scene, lang)


# ─── RESULT CALLBACKS ────────────────────────────────────────────────────────

@router.callback_query(ImageFSM.result, F.data == "img:new")
async def cb_new(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "ua")
    await state.set_state(ImageFSM.subject)
    try:
        await callback.answer()
    except Exception:
        pass
    await callback.message.answer(
        "🖼 Введи нову тему:" if lang == "ua" else "🖼 Enter new subject:"
    )


@router.callback_query(ImageFSM.result, F.data == "img:regen")
async def cb_regen(callback: CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    lang    = data.get("lang", "ua")
    subject = data.get("subject", "")
    scene   = data.get("scene", "portrait")
    try:
        await callback.answer()
    except Exception:
        pass
    await _run_image(callback.message, state, subject, scene, lang)


@router.callback_query(ImageFSM.result, F.data == "img:copy")
async def cb_copy(callback: CallbackQuery, state: FSMContext) -> None:
    data     = await state.get_data()
    lang     = data.get("lang", "ua")
    positive = data.get("positive", "")
    if not positive:
        try:
            await callback.answer(
                "Промпт недоступний" if lang == "ua" else "Prompt not available"
            )
        except Exception:
            pass
        return
    await callback.message.answer(
        f"📋 <b>Positive prompt:</b>\n\n<code>{positive}</code>",
        parse_mode="HTML",
    )
    try:
        await callback.answer("✓")
    except Exception:
        pass
