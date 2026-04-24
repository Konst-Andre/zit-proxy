"""
ZIT Bot — Upstash Redis Client (HTTP REST)
No redis-py needed — uses httpx which is already in requirements.
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

UPSTASH_URL   = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

TIMEOUT = 5.0


def _headers() -> dict:
    return {"Authorization": f"Bearer {UPSTASH_TOKEN}"}


async def redis_get(key: str) -> Any | None:
    """Get value by key. Returns None if not found or error."""
    if not UPSTASH_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{UPSTASH_URL}/get/{key}", headers=_headers())
        result = r.json().get("result")
        return json.loads(result) if result else None
    except Exception as e:
        logger.warning("redis_get error key=%s: %s", key, e)
        return None


async def redis_set(key: str, value: Any, ex: int = 86400) -> bool:
    """Set key with TTL in seconds (default 24h)."""
    if not UPSTASH_URL:
        return False
    try:
        payload = json.dumps(value, ensure_ascii=False)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{UPSTASH_URL}/pipeline",
                headers=_headers(),
                json=[["SET", key, payload, "EX", ex]],
            )
        return r.status_code == 200
    except Exception as e:
        logger.warning("redis_set error key=%s: %s", key, e)
        return False


async def redis_delete(key: str) -> bool:
    if not UPSTASH_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.get(f"{UPSTASH_URL}/del/{key}", headers=_headers())
        return True
    except Exception as e:
        logger.warning("redis_delete error key=%s: %s", key, e)
        return False
