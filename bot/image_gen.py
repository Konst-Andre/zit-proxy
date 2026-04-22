"""
ZIT Bot — Image Generation via Pollinations.ai
Free, no API key required for basic use.
Endpoint: https://image.pollinations.ai/prompt/{prompt}
"""

import asyncio
import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 60.0

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


def _build_url(prompt: str, width: int, height: int) -> str:
    encoded = urllib.parse.quote(prompt)
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&nologo=true&model=flux"
    )


async def generate_image(prompt: str, scene: str = "portrait") -> bytes:
    """
    Async GET → Pollinations.ai → повертає PNG bytes.
    Raises: httpx.HTTPError при помилці мережі або сервера.
    """
    width, height = SCENE_RESOLUTION.get(scene, DEFAULT_RESOLUTION)
    url = _build_url(prompt, width, height)

    logger.info(
        "Pollinations | scene=%s | %dx%d | prompt: %s…",
        scene, width, height, prompt[:60],
    )

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
