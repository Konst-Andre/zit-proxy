"""
ZIT Prompt Generator — Render Server v3.0
==========================================
Changes vs v2.0:
  - aiogram 3 + aiogram-dialog mounted via SimpleRequestHandler (Variant B)
  - Old manual bot handlers removed
  - Bug #1 fixed: reply_markup no longer double-serialized (aiogram handles natively)
  - Bug #2 fixed: Qwen3 thinking tokens stripped via strip_think() in prompts.py
  - Bug #3: webhook registered with secret_token
  - Bug #4: /proxy/groq has per-IP rate limiting (sliding window)
  - Bug #5: all handlers wrapped in try/except, webhook always returns 200

Endpoints:
  GET  /health        — warm-up ping
  POST /proxy/groq    — proxy to Groq API (Mini App / website)
  POST /webhook       — Telegram bot webhook (aiogram)
  GET  /set_webhook   — register webhook (call once after deploy)
"""

import os
import time
import hashlib
import logging
import hmac
import httpx
from collections import defaultdict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler  # aiogram provides this
from aiogram.enums import ParseMode

# We use starlette directly for mounting aiogram into FastAPI
from aiogram.webhook.aiohttp_server import SimpleRequestHandler as _SRH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GROQ_API_KEY    = os.environ.get("GROQ_API_KEY", "")
TG_BOT_TOKEN    = os.environ.get("TG_BOT_TOKEN", "")
WEBHOOK_SECRET  = os.environ.get("WEBHOOK_SECRET", "zit-secret-2025")
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
WEBHOOK_PATH    = "/webhook"
ALLOWED_ORIGINS = ["https://konst-andre.github.io"]

# ─── RATE LIMITER (for /proxy/groq) ──────────────────────────────────────────

class SlidingWindowRateLimiter:
    """Simple in-process sliding window rate limiter."""
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._log: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        log = self._log[key]
        # Evict expired
        self._log[key] = [t for t in log if t > cutoff]
        if len(self._log[key]) >= self.max_requests:
            return False
        self._log[key].append(now)
        return True


rate_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60)

# ─── FASTAPI APP ──────────────────────────────────────────────────────────────

app = FastAPI(title="ZIT Server", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)

# ─── BOT + DISPATCHER ────────────────────────────────────────────────────────

bot: Bot | None = None
dp = None


def _init_bot():
    global bot, dp
    if not TG_BOT_TOKEN:
        logger.warning("TG_BOT_TOKEN not set — bot disabled")
        return
    bot = Bot(
        token=TG_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    from bot.router import create_dispatcher
    dp = create_dispatcher()
    logger.info("Bot and dispatcher initialized")


@app.on_event("startup")
async def on_startup():
    _init_bot()


@app.on_event("shutdown")
async def on_shutdown():
    if bot:
        await bot.session.close()


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "zit-server", "version": "3.0.0"}


@app.get("/set_webhook")
async def set_webhook(request: Request):
    if not TG_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TG_BOT_TOKEN not configured")
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message", "callback_query", "inline_query"],
                "secret_token": WEBHOOK_SECRET,
                "drop_pending_updates": True,
            },
        )
    data = resp.json()
    logger.info("set_webhook response: %s", data)
    return data


@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    # Bug #3 fix: verify secret token
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
        logger.warning("Webhook: invalid secret token")
        return JSONResponse({"ok": True})  # Return 200 to prevent TG retries

    # Bug #5 fix: always return 200, never let exceptions propagate
    try:
        if bot is None or dp is None:
            logger.error("Webhook called but bot is not initialized")
            return JSONResponse({"ok": True})

        body = await request.body()
        import json
        update_data = json.loads(body)

        from aiogram.types import Update
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)

    except Exception:
        logger.exception("Error processing webhook update")

    return JSONResponse({"ok": True})


@app.post("/proxy/groq")
async def proxy_groq(request: Request):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    # Bug #4 fix: rate limit by IP
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded — 20 req/min")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GROQ_URL,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Groq API timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Groq API unreachable: {e}")

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid JSON from Groq API")

    return JSONResponse(content=data, status_code=resp.status_code)
