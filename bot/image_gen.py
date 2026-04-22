"""
ZIT Bot — Image Generation Service
Uses HuggingFace Inference Providers (fal-ai) to generate images via Z-Image-Turbo.
Async-safe: wraps synchronous InferenceClient in asyncio.to_thread().
"""

import asyncio
import io
import logging
import os

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

HF_TOKEN   = os.environ.get("HF_TOKEN", "")
MODEL_ID   = "Tongyi-MAI/Z-Image-Turbo"
PROVIDER   = "fal-ai"

# Singleton client — ініціалізується один раз при імпорті
_client: InferenceClient | None = None


def get_client() -> InferenceClient:
    global _client
    if _client is None:
        _client = InferenceClient(provider=PROVIDER, api_key=HF_TOKEN)
        logger.info("Z-Image-Turbo client initialized (provider=%s)", PROVIDER)
    return _client


def _generate_sync(prompt: str) -> bytes:
    """
    Синхронна генерація — викликається через asyncio.to_thread().
    Повертає PNG bytes.
    """
    client = get_client()
    image = client.text_to_image(prompt=prompt, model=MODEL_ID)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


async def generate_image(prompt: str) -> bytes:
    """
    Async wrapper — не блокує event loop aiogram.
    Raises: будь-який Exception від fal-ai / huggingface_hub.
    """
    logger.info("Generating image | prompt: %s…", prompt[:60])
    return await asyncio.to_thread(_generate_sync, prompt)
