"""
ZIT Bot — /vision Handler
User sends photo → Llama-4-Scout analyzes it → extracts ZIT params →
shows detected params → generates prompt via qwen3-32b.

Model: meta-llama/llama-4-scout-17b-16e-instruct (hardcoded, as per engine v3.8.0)
Max tokens: 512
Max file size: 4 MB
Formats: JPEG, PNG, WEBP
"""

import os
import re
import html
import logging

import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, PhotoSize

from prompts import groq_generate, strip_think
from bot.dialogs.result import format_result_message
from data import SCENES, STYLES, LIGHTINGS, MOODS, GENRES

logger = logging.getLogger(__name__)
router = Router(name="vision")

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"
TG_BOT_TOKEN   = os.environ.get("TG_BOT_TOKEN", "")
MAX_VISION_MB  = 4
MAX_VISION_B   = MAX_VISION_MB * 1024 * 1024

VISION_SYSTEM = """You analyze images and extract visual parameters for a diffusion model prompt generator.
Use strict factual visual analysis. Only describe what is clearly visible.
Avoid subjective or interpretive adjectives.
Return ONLY a valid XML block — no prose, no markdown, no explanation before or after.

Respond with this exact XML structure:
<vision>
  <scene>VALUE</scene>
  <style>VALUE</style>
  <subjectType>VALUE</subjectType>
  <lighting>VALUE</lighting>
  <mood>VALUE</mood>
  <genre>VALUE</genre>
  <subject>TEXT</subject>
</vision>

=== FIELD RULES ===
scene — camera FRAMING of the subject.
  portrait = only face/head visible | half_body = torso visible | full_body = knees/feet visible
  Non-person: landscape | urban | interior | architecture | macro | animal | product | concept
  Allowed: portrait | half_body | full_body | landscape | urban | interior | architecture | macro | animal | product | concept

style — visual rendering style only.
  Allowed: photorealistic | cinematic | documentary | fashion | analog | monochrome |
           digital_art | concept_art | illustration | oil_painting | watercolor | pencil_sketch |
           impressionism | anime | manga | comic | ink_wash | ukiyo_e |
           3d_render | low_poly | isometric | pixel_art | flat_design | glitch

subjectType — person | animal | product | object | environment

lighting — Cinematic | Soft Natural | Golden Hour | Blue Hour | Overcast |
           Rim Light | Neon / LED | Volumetric Rays | Studio Softbox | Candlelight | Moonlight | Harsh Midday
  Always assign lighting — never leave empty.

mood — ONLY if CLEARLY present, else EMPTY.
  Allowed: Moody & atmospheric | Ethereal & dreamy | Tense & dramatic | Serene & peaceful |
           Mysterious | Epic & grand | Melancholic | Joyful & vibrant | Gritty & raw

genre — ONLY if UNMISTAKABLY present, else EMPTY.
  Allowed: Cyberpunk | Fantasy | Dark Fantasy | Sci-Fi | Solarpunk | Noir |
           Post-Apocalyptic | Historical | Mythological | Surreal | Horror | Futuristic

subject — factual English description of main subject, 40–70 words. What is VISIBLE only."""


def _extract_vision_tag(text: str, tag: str) -> str:
    # (?=[>\s]) — після назви тегу має йти > або пробіл
    # Це виключає <subjectType> при пошуку <subject>
    pattern = rf'<{re.escape(tag)}(?=[>\s])[^>]*>([\s\S]*?)</{re.escape(tag)}>'
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _normalize_scene(val: str) -> str:
    return val if val in SCENES else "portrait"


def _normalize_style(val: str) -> str:
    return val if val in STYLES else "photorealistic"


def _normalize_lighting(val: str) -> str:
    return val if val in LIGHTINGS else "Cinematic"


def _normalize_mood(val: str) -> str:
    return val if val in MOODS else ""


def _normalize_genre(val: str) -> str:
    return val if val in GENRES else ""


async def _get_tg_file_url(bot_token: str, file_id: str) -> str:
    """Get direct Telegram CDN URL for a file — no download needed."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"https://api.telegram.org/bot{bot_token}/getFile",
            params={"file_id": file_id},
        )
        r.raise_for_status()
        file_path = r.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"


async def _vision_analyze(image_url: str) -> dict:
    """Call Llama-4-Scout with image URL (no base64), return parsed params dict."""
    payload = {
        "model": VISION_MODEL,
        "max_tokens": 512,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
                {"type": "text", "text": VISION_SYSTEM},
            ],
        }],
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    cleaned = strip_think(raw)
    logger.info("Vision raw response: %s", cleaned[:300])

    return {
        "scene":        _normalize_scene(_extract_vision_tag(cleaned, "scene")),
        "style":        _normalize_style(_extract_vision_tag(cleaned, "style")),
        "subject_type": _extract_vision_tag(cleaned, "subjectType") or "none",
        "lighting":     _normalize_lighting(_extract_vision_tag(cleaned, "lighting")),
        "mood":         _normalize_mood(_extract_vision_tag(cleaned, "mood")),
        "genre":        _normalize_genre(_extract_vision_tag(cleaned, "genre")),
        "subject":      _extract_vision_tag(cleaned, "subject"),
    }


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _format_detected(params: dict, lang: str) -> str:
    scene_label   = SCENES.get(params["scene"], {}).get("label", params["scene"])
    style_label   = STYLES.get(params["style"], {}).get("label", params["style"])
    lighting_label = LIGHTINGS.get(params["lighting"], {}).get("label", "—")
    mood_label    = MOODS.get(params["mood"], {}).get("label", "—") if params["mood"] else "—"
    genre_label   = GENRES.get(params["genre"], {}).get("label", "—") if params["genre"] else "—"

    if lang == "ua":
        return (
            f"🔍 <b>Розпізнані параметри:</b>\n\n"
            f"📐 Сцена: <b>{scene_label}</b>\n"
            f"🎨 Стиль: <b>{style_label}</b>\n"
            f"💡 Освітлення: <b>{lighting_label}</b>\n"
            f"🌙 Настрій: <b>{mood_label}</b>\n"
            f"🌐 Жанр: <b>{genre_label}</b>\n\n"
            f"📝 Субʼєкт:\n<i>{html.escape(params['subject'])}</i>\n\n"
            f"⏳ Генерую промпт…"
        )
    return (
        f"🔍 <b>Detected parameters:</b>\n\n"
        f"📐 Scene: <b>{scene_label}</b>\n"
        f"🎨 Style: <b>{style_label}</b>\n"
        f"💡 Lighting: <b>{lighting_label}</b>\n"
        f"🌙 Mood: <b>{mood_label}</b>\n"
        f"🌐 Genre: <b>{genre_label}</b>\n\n"
        f"📝 Subject:\n<i>{html.escape(params['subject'])}</i>\n\n"
        f"⏳ Generating prompt…"
    )


@router.message(Command("vision"))
async def cmd_vision_hint(message: Message) -> None:
    lang = _detect_lang(message)
    if lang == "ua":
        await message.answer(
            "📸 <b>Vision режим</b>\n\n"
            "Надішли фото — я розпізнаю параметри і згенерую промпт.\n\n"
            "<i>Формати: JPEG, PNG, WEBP. Розмір до 4 МБ.</i>"
        )
    else:
        await message.answer(
            "📸 <b>Vision mode</b>\n\n"
            "Send a photo — I'll detect parameters and generate a prompt.\n\n"
            "<i>Formats: JPEG, PNG, WEBP. Max size 4 MB.</i>"
        )


async def _vision_pipeline(message: Message, photo: PhotoSize, lang: str, wait_msg) -> None:
    """
    Full vision pipeline: download → analyze → generate.
    Runs as background task so webhook returns immediately (avoids Render 30s timeout).
    """
    try:
        image_url = await _get_tg_file_url(TG_BOT_TOKEN, photo.file_id)
    except Exception as e:
        logger.exception("Failed to get file URL")
        await wait_msg.edit_text(f"❌ Не вдалося отримати фото: {str(e)[:100]}")
        return

    try:
        params = await _vision_analyze(image_url)
    except Exception as e:
        logger.exception("Vision analysis failed")
        await wait_msg.edit_text(f"❌ Помилка аналізу: {str(e)[:100]}")
        return

    detected_text = _format_detected(params, lang)
    await wait_msg.edit_text(detected_text, parse_mode="HTML")

    state = {**params, "lang": lang}

    try:
        result = await groq_generate(state, GROQ_API_KEY)
    except Exception as e:
        logger.exception("groq_generate failed in vision")
        result = {"error": str(e)[:200]}

    text = format_result_message(state, result, lang)
    await message.answer(text, parse_mode="HTML")


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """
    Handle any photo. Immediately acks, then runs pipeline as background task —
    prevents Render Free 30s webhook timeout from killing the request.
    """
    import asyncio

    lang = _detect_lang(message)
    photo: PhotoSize = message.photo[-1]

    if photo.file_size and photo.file_size > MAX_VISION_B:
        err = "Файл завеликий. Максимум 4 МБ." if lang == "ua" else "File too large. Max 4 MB."
        await message.answer(err)
        return

    wait_msg = await message.answer(
        "📸 Аналізую зображення…" if lang == "ua" else "📸 Analyzing image…"
    )

    # Fire-and-forget: webhook returns immediately, pipeline continues in background
    asyncio.create_task(_vision_pipeline(message, photo, lang, wait_msg))
