"""
ZIT Prompt Generator — Render Server v2.0
==========================================
Endpoints:
  GET  /health        — warm-up ping
  POST /proxy/groq    — проксі до Groq API (з Mini App / сайту)
  POST /webhook       — Telegram bot webhook
  GET  /set_webhook   — реєстрація webhook (викликати один раз)

Команди бота:
  /start   — привітання + кнопка відкрити Mini App
  /prompt  — згенерувати промпт
  /random  — рандомний промпт
  /help    — гайд
"""

import os
import re
import json
import random
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="ZIT Server", version="2.0.0")

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
TG_BOT_TOKEN  = os.environ.get("TG_BOT_TOKEN", "")
MINI_APP_URL  = "https://konst-andre.github.io/zit-prompt-tg/"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
TG_API        = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
BOT_MODEL     = "qwen/qwen3-32b"

ALLOWED_ORIGINS = ["https://konst-andre.github.io"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)

RANDOM_SUBJECTS = [
    "a lone samurai standing in heavy rain at dusk",
    "an astronaut floating above a neon city at night",
    "a fox spirit in ancient Japanese forest, glowing lanterns",
    "a cyberpunk street vendor under pink holographic signs",
    "an elderly fisherman on a misty lake at sunrise",
    "a ballerina frozen mid-leap in a crumbling theater",
    "a child discovering a glowing portal in an old library",
    "a wolf howling on a cliff under the northern lights",
    "a futuristic greenhouse on Mars, warm golden light",
    "a medieval alchemist surrounded by glowing potions",
    "a street photographer in 1970s Tokyo during golden hour",
    "a mermaid resting on sea rocks, stormy ocean behind",
    "a desert wanderer approaching an ancient ruined city",
    "twin sisters in identical outfits on a foggy rooftop",
    "a robot tending a flower garden in post-apocalyptic world",
]

BOT_SYSTEM = """You are ZIT — an expert AI prompt engineer for image generation (Lumina2, SDXL, ComfyUI).

Generate a structured image prompt. Reply ONLY in this exact XML format, no other text:

<positive>detailed positive prompt here, comma separated tags and phrases</positive>
<negative>negative prompt here, comma separated</negative>

Rules:
- Positive: subject, style, lighting, mood, camera, quality tags
- Negative: keep short, 6-10 terms max
- No markdown, no explanations, only XML
- English only"""


def extract_tag(text: str, tag: str) -> str:
    m = re.search(rf'<{tag}[^>]*>([\s\S]*?)</{tag}>', text, re.I)
    return m.group(1).strip() if m else ""


async def groq_generate(subject: str) -> dict:
    payload = {
        "model": BOT_MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": BOT_SYSTEM},
            {"role": "user",   "content": f"Create a prompt for: {subject}"},
        ],
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            GROQ_URL,
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return {
        "positive": extract_tag(raw, "positive") or raw,
        "negative": extract_tag(raw, "negative") or "blurry, watermark, text",
    }


async def tg_send(chat_id: int, text: str, reply_markup: dict = None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"{TG_API}/sendMessage", json=payload)


async def tg_typing(chat_id: int):
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(f"{TG_API}/sendChatAction",
                          json={"chat_id": chat_id, "action": "typing"})


async def handle_start(chat_id: int, first_name: str):
    text = (
        f"👋 Привіт, <b>{first_name}</b>!\n\n"
        f"Я <b>ZIT Prompt Generator</b> — генерую промпти для ComfyUI, Lumina2 та SDXL.\n\n"
        f"<b>Команди:</b>\n"
        f"🎨 /prompt [ідея] — згенерувати промпт\n"
        f"🎲 /random — рандомний промпт\n"
        f"❓ /help — довідка\n\n"
        f"Або відкрий повний генератор:"
    )
    markup = {"inline_keyboard": [[
        {"text": "🎨 Відкрити ZIT Generator", "web_app": {"url": MINI_APP_URL}}
    ]]}
    await tg_send(chat_id, text, markup)


async def handle_prompt(chat_id: int, subject: str):
    if not subject.strip():
        await tg_send(chat_id,
            "⚠️ Вкажи тему після команди.\n"
            "Приклад: <code>/prompt cyberpunk girl in rain</code>")
        return
    await tg_typing(chat_id)
    try:
        r = await groq_generate(subject)
        text = (
            f"✦ <b>PROMPT</b>\n<code>{r['positive']}</code>\n\n"
            f"✦ <b>NEGATIVE</b>\n<code>{r['negative']}</code>"
        )
    except Exception as e:
        text = f"❌ Помилка: {str(e)[:120]}"
    await tg_send(chat_id, text)


async def handle_random(chat_id: int):
    subject = random.choice(RANDOM_SUBJECTS)
    await tg_typing(chat_id)
    try:
        r = await groq_generate(subject)
        text = (
            f"🎲 <b>Тема:</b> {subject}\n\n"
            f"✦ <b>PROMPT</b>\n<code>{r['positive']}</code>\n\n"
            f"✦ <b>NEGATIVE</b>\n<code>{r['negative']}</code>"
        )
    except Exception as e:
        text = f"❌ Помилка: {str(e)[:120]}"
    await tg_send(chat_id, text)


async def handle_help(chat_id: int):
    text = (
        "📖 <b>ZIT Prompt Generator — Гайд</b>\n\n"
        "<b>Команди:</b>\n"
        "• /prompt [тема] — генерує позитивний та негативний промпт\n"
        "• /random — рандомна тема + промпт\n"
        "• /help — ця довідка\n\n"
        "<b>Приклади:</b>\n"
        "<code>/prompt portrait of a warrior in golden armor</code>\n"
        "<code>/prompt foggy japanese street at night</code>\n\n"
        "Для розширених налаштувань — відкрий повний генератор:"
    )
    markup = {"inline_keyboard": [[
        {"text": "🎨 Відкрити ZIT Generator", "web_app": {"url": MINI_APP_URL}}
    ]]}
    await tg_send(chat_id, text, markup)


@app.get("/health")
def health():
    return {"status": "ok", "service": "zit-server", "version": "2.0.0"}


@app.get("/set_webhook")
async def set_webhook(request: Request):
    if not TG_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TG_BOT_TOKEN not configured")
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{TG_API}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]},
        )
    return resp.json()


@app.post("/webhook")
async def webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message", {})
    if not message:
        return {"ok": True}

    chat_id    = message.get("chat", {}).get("id")
    text       = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "")

    if not chat_id or not text:
        return {"ok": True}

    parts   = text.split(None, 1)
    command = parts[0].split("@")[0].lower()
    args    = parts[1] if len(parts) > 1 else ""

    if   command == "/start":  await handle_start(chat_id, first_name)
    elif command == "/prompt": await handle_prompt(chat_id, args)
    elif command == "/random": await handle_random(chat_id)
    elif command == "/help":   await handle_help(chat_id)

    return {"ok": True}


@app.post("/proxy/groq")
async def proxy_groq(request: Request):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GROQ_URL, content=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {GROQ_API_KEY}"},
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Groq API timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Groq API unreachable: {str(e)}")
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid JSON from Groq API")
    return JSONResponse(content=data, status_code=resp.status_code)
