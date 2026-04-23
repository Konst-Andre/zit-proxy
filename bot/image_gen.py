"""
ZIT Bot — Image Generation via Pollinations.ai
Free, no API key required.
Auto-retry: 3 attempts with exponential backoff for rate limits.
"""

import asyncio
import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 60.0
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5]

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
    Авто-retry 3 спроби з паузою при 429 або помилці мережі.
    """
    width, height = SCENE_RESOLUTION.get(scene, DEFAULT_RESOLUTION)
    url = _build_url(prompt, width, height)

    logger.info(
        "Pollinations | scene=%s | %dx%d | prompt: %s…",
        scene, width, height, prompt[:60],
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)

                if resp.status_code == 429:
                    delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                    logger.warning("Pollinations 429 — attempt %d/%d, retry in %ds", attempt, MAX_RETRIES, delay)
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()
                return resp.content

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning("Pollinations timeout — attempt %d/%d", attempt, MAX_RETRIES)
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning("Pollinations HTTP %d — attempt %d/%d", e.response.status_code, attempt, MAX_RETRIES)
        except Exception as e:
            last_error = e
            logger.exception("Pollinations unexpected error — attempt %d/%d", attempt, MAX_RETRIES)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])

    raise Exception(f"Pollinations failed after {MAX_RETRIES} attempts: {last_error}")
