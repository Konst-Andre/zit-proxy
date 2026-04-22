"""
ZIT Bot — Image Generation Service
Uses Google Gemini API (gemini-2.0-flash-exp-image-generation) for free image generation.
Free tier: ~500 images/day, no credit card required.
Async-safe: wraps synchronous call in asyncio.to_thread().
"""

import asyncio
import base64
import io
import logging
import os

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_ID       = "gemini-2.0-flash-exp-image-generation"

# Resolution map per scene (width, height)
SCENE_RESOLUTION: dict[str, tuple[int, int]] = {
    "portrait":     (896, 1152),
    "half_body":    (896, 1152),
    "full_body":    (768, 1280),
    "landscape":    (1280, 768),
    "urban":        (1152, 896),
    "interior":     (1152, 896),
    "architecture": (1152, 896),
    "macro":        (1024, 1024),
    "animal":       (1024, 1024),
    "product":      (1024, 1024),
    "concept":      (1152, 896),
    "manual":       (1024, 1024),
}

DEFAULT_RESOLUTION = (1024, 1024)

# Singleton model
_model = None


def get_model():
    global _model
    if _model is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set in environment variables")
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name=MODEL_ID,
            generation_config=genai.GenerationConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        logger.info("Gemini image model initialized (model=%s)", MODEL_ID)
    return _model


def _generate_sync(prompt: str) -> bytes:
    """
    Синхронна генерація — викликається через asyncio.to_thread().
    Повертає PNG bytes.
    """
    model = get_model()
    response = model.generate_content(prompt)

    # Шукаємо image part у відповіді
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data.data
                mime_type  = part.inline_data.mime_type

                # data може бути bytes або base64 string
                if isinstance(image_data, str):
                    image_bytes = base64.b64decode(image_data)
                else:
                    image_bytes = image_data

                # Конвертуємо в PNG через PIL якщо потрібно
                if mime_type != "image/png":
                    from PIL import Image
                    buf_in  = io.BytesIO(image_bytes)
                    buf_out = io.BytesIO()
                    Image.open(buf_in).save(buf_out, format="PNG")
                    return buf_out.getvalue()

                return image_bytes

    raise RuntimeError("Gemini returned no image in response")


async def generate_image(prompt: str, scene: str = "portrait") -> bytes:
    """
    Async wrapper — не блокує event loop aiogram.
    scene використовується для логування (resolution у Gemini задається через prompt).
    Raises: RuntimeError, google_exceptions.ResourceExhausted (429)
    """
    width, height = SCENE_RESOLUTION.get(scene, DEFAULT_RESOLUTION)
    logger.info(
        "Generating image | scene: %s | res: %dx%d | prompt: %s…",
        scene, width, height, prompt[:60],
    )

    # Додаємо resolution hint в промпт — Gemini враховує це
    full_prompt = f"{prompt}\n\nImage dimensions: {width}x{height} pixels."

    try:
        return await asyncio.to_thread(_generate_sync, full_prompt)
    except google_exceptions.ResourceExhausted:
        raise RuntimeError("Gemini rate limit reached — try again in a minute")
