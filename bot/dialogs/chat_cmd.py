"""
ZIT Bot — /chat Agent Handler v4
Model: Llama 4 Scout (30K TPM, multimodal, better creative/chat)
Tools: web_search, generate_prompt, generate_image, get_weather, get_exchange_rate, summarize_url
Prompt output → окреме повідомлення з <code> для легкого копіювання
Image output → окреме повідомлення з фото
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from urllib.parse import quote

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile

from bot.states import ChatFSM
from bot.redis_client import redis_get, redis_set, redis_delete

logger = logging.getLogger(__name__)
router = Router(name="chat_cmd")

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_URL     = "https://api.tavily.com/search"
CHAT_MODEL     = "meta-llama/llama-4-scout-17b-16e-instruct"  # 30K TPM, better chat/creative

MAX_HISTORY    = 20      # Scout має 30K TPM — можна зберігати більше history
AUTO_RESET_MIN = 30
HISTORY_TTL    = 86400


# ─── SYSTEM PROMPT ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Prompt Assistant — a smart, helpful AI agent built into the LLM Prompt Generator Bot.

Your primary context:
- This Telegram bot generates structured prompts for AI image generation
- Commands available: /prompt (FSM generator), /random, /image (text→image), /vision (photo→prompt), inline mode
- You help users craft better prompts, explain AI image generation concepts, answer any questions

Your tools:
- web_search: search the internet for current info
- generate_prompt: create a structured image generation prompt (POSITIVE + NEGATIVE)
- generate_image: generate an actual image from a prompt
- get_weather: get current weather for a city
- get_exchange_rate: get currency exchange rate
- summarize_url: fetch and summarize a webpage

Behavior rules:
- Be concise but thorough — Telegram messages have limits
- Use Ukrainian when user writes in Ukrainian, English otherwise
- For factual/current info → use web_search tool
- For image prompt requests → use generate_prompt tool (NOT plain text)
- For "draw", "generate image", "намалюй", "зроби зображення" → use generate_image tool
- For weather questions → use get_weather tool
- For currency/exchange → use get_exchange_rate tool
- For URLs → use summarize_url tool
- Do NOT mention SDXL, Flux, Stable Diffusion — say "AI image generator"
- Keep responses focused and natural — no unnecessary padding

Current date: {date}
"""


def _get_system_prompt() -> str:
    return SYSTEM_PROMPT.format(date=datetime.now().strftime("%d.%m.%Y"))


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _redis_key(user_id: int) -> str:
    return f"chat:history:{user_id}"


# ─── RESPONSE PROCESSING ─────────────────────────────────────────────────────

def _strip_think(text: str) -> str:
    # Закриті блоки
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    # Незакриті — до 3000 символів включно з переносами
    text = re.sub(r"<think>(?:(?!</think>)[\s\S]){0,3000}", "", text, flags=re.IGNORECASE)
    return text.strip()


def _safe_split(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────

async def tavily_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return "Search unavailable."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(TAVILY_URL, json={
                "api_key": TAVILY_API_KEY, "query": query,
                "max_results": 4, "search_depth": "basic", "include_answer": True,
            })
        data = r.json()
        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")
        for res in data.get("results", [])[:3]:
            parts.append(f"• {res.get('title','')}\n  {res.get('content','')[:250]}\n  {res.get('url','')}")
        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search error: {str(e)[:100]}"


async def tool_generate_prompt(subject: str, style: str = "", scene: str = "portrait") -> dict:
    """Call groq_generate with simplified state."""
    from prompts import groq_generate
    state = {
        "subject": subject, "scene": scene,
        "style": style or "photorealistic", "lighting": "Cinematic",
        "mood": "", "genre": "", "subject_type": "none", "lang": "en",
    }
    try:
        return await groq_generate(state, GROQ_API_KEY)
    except Exception as e:
        return {"error": str(e)[:120]}


async def tool_generate_image(prompt: str, scene: str = "portrait") -> bytes | None:
    """Generate image via Pollinations."""
    from bot.image_gen import generate_image
    try:
        return await generate_image(prompt, scene=scene)
    except Exception as e:
        logger.warning("tool_generate_image failed: %s", e)
        return None


async def tool_get_weather(city: str) -> str:
    """Get weather via wttr.in (free, no API key)."""
    try:
        city_enc = quote(city)
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"https://wttr.in/{city_enc}?format=3",
                headers={"User-Agent": "curl/7.68.0"},
            )
        return r.text.strip()
    except Exception as e:
        return f"Weather error: {str(e)[:100]}"


async def tool_get_exchange_rate(from_cur: str, to_cur: str) -> str:
    """Get exchange rate via frankfurter.dev v2 (free, no API key, 54 central banks)."""
    try:
        url = f"https://api.frankfurter.dev/v2/rate/{from_cur.upper()}/{to_cur.upper()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        if r.status_code == 404:
            return f"Currency pair {from_cur.upper()}/{to_cur.upper()} not found."
        r.raise_for_status()
        data = r.json()
        rate = data.get("rate")
        if rate:
            return f"1 {from_cur.upper()} = {rate} {to_cur.upper()} (frankfurter.dev)"
        return f"Rate not found for {from_cur}/{to_cur}"
    except Exception as e:
        return f"Exchange error: {str(e)[:100]}"


async def tool_summarize_url(url: str) -> str:
    """Fetch URL content and return first 2000 chars for summarization."""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            r = await client.get(url)
        # Strip HTML tags roughly
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000]
    except Exception as e:
        return f"URL fetch error: {str(e)[:100]}"


# ─── TOOLS DEFINITION ────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current info, news, facts, prices.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_prompt",
            "description": "Generate a structured AI image prompt (POSITIVE + NEGATIVE). Use when user asks to create/write a prompt for image generation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Main subject in English"},
                    "style":   {"type": "string", "description": "Art style (optional)"},
                    "scene":   {"type": "string", "description": "Scene type: portrait/landscape/product/animal/full_body/concept", "default": "portrait"},
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an actual image. Use when user says 'draw', 'generate image', 'намалюй', 'зроби зображення'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Image prompt in English"},
                    "scene":  {"type": "string", "description": "Scene type: portrait/landscape/product/animal/full_body/concept", "default": "portrait"},
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "Get currency exchange rate between two currencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_currency": {"type": "string", "description": "e.g. USD"},
                    "to_currency":   {"type": "string", "description": "e.g. UAH"},
                },
                "required": ["from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_url",
            "description": "Fetch and summarize content from a URL/webpage.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


# ─── TOOL DISPATCHER ─────────────────────────────────────────────────────────

async def _dispatch_tool(name: str, args: dict) -> tuple[str, dict | None]:
    """
    Execute tool by name.
    Returns (result_text, extra) where extra can contain image_bytes, prompt_data etc.
    """
    if name == "web_search":
        result = await tavily_search(args.get("query", ""))
        return result, None

    if name == "generate_prompt":
        data = await tool_generate_prompt(
            subject=args.get("subject", ""),
            style=args.get("style", ""),
            scene=args.get("scene", "portrait"),
        )
        if "error" in data:
            return f"Prompt error: {data['error']}", None
        result_text = (
            f"POSITIVE: {data.get('positive','')}\n"
            f"NEGATIVE: {data.get('negative','')}"
        )
        return result_text, {"type": "prompt", "data": data}

    if name == "generate_image":
        prompt = args.get("prompt", "")
        scene  = args.get("scene", "portrait")
        image_bytes = await tool_generate_image(prompt, scene)
        if image_bytes:
            return f"Image generated for: {prompt[:60]}", {"type": "image", "bytes": image_bytes, "prompt": prompt}
        return "Image generation failed — try again.", None

    if name == "get_weather":
        result = await tool_get_weather(args.get("city", ""))
        return result, None

    if name == "get_exchange_rate":
        result = await tool_get_exchange_rate(
            args.get("from_currency", "USD"),
            args.get("to_currency", "UAH"),
        )
        return result, None

    if name == "summarize_url":
        content = await tool_summarize_url(args.get("url", ""))
        return content, None

    return "Unknown tool.", None


# ─── GROQ WITH MULTI-TOOL ────────────────────────────────────────────────────

async def groq_chat(messages: list[dict], message: Message | None = None) -> str:
    """
    Call Groq with tool use. Handles tool execution and sends side-effects
    (images, code blocks) directly via message if provided.
    Returns final text reply.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(GROQ_URL, json={
            "model": CHAT_MODEL, "messages": messages,
            "tools": TOOLS, "tool_choice": "auto", "max_tokens": 2048,
        }, headers=headers)
    r.raise_for_status()

    choice = r.json()["choices"][0]
    msg    = choice["message"]

    # ── Tool calls ────────────────────────────────────────────────────────
    if choice.get("finish_reason") == "tool_calls" and msg.get("tool_calls"):
        tool_messages = [msg]
        extra_results = []

        for tool_call in msg["tool_calls"]:
            name      = tool_call["function"]["name"]
            args      = json.loads(tool_call["function"]["arguments"])
            logger.info("Tool call: %s | args: %s", name, args)

            # Оновлюємо індикатор для довгих операцій
            if message and name == "generate_image":
                try:
                    await message.answer("🎨 Генерую зображення…")
                except Exception:
                    pass

            result_text, extra = await _dispatch_tool(name, args)
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result_text,
            })
            if extra:
                extra_results.append(extra)

        # Збираємо які side effects вже надіслано — щоб модель не галюцинувала
        sent_effects = []

        # Side effects — надсилаємо image/prompt ДО фінальної відповіді
        if message:
            for extra in extra_results:
                if extra["type"] == "image":
                    try:
                        photo = BufferedInputFile(extra["bytes"], filename="image.png")
                        await message.answer_photo(
                            photo=photo,
                            caption=f"🎨 {extra['prompt'][:200]}",
                        )
                        sent_effects.append("image_sent")
                    except Exception as e:
                        logger.warning("Failed to send image: %s", e)

                elif extra["type"] == "prompt":
                    data = extra["data"]
                    pos  = data.get("positive", "")
                    neg  = data.get("negative", "")
                    try:
                        await message.answer(
                            f"📋 <b>POSITIVE</b>\n<code>{pos[:900]}</code>\n\n"
                            f"📋 <b>NEGATIVE</b>\n<code>{neg[:300]}</code>",
                            parse_mode="HTML",
                        )
                        sent_effects.append("prompt_sent")
                    except Exception as e:
                        logger.warning("Failed to send prompt block: %s", e)

        # Фінальний виклик — повідомляємо модель що вже надіслано
        note = ""
        if "image_sent" in sent_effects:
            note = " The image has already been sent to the user as a photo message — do NOT mention file links or image.png."
        if "prompt_sent" in sent_effects:
            note += " The prompt has already been sent as a formatted code block — do NOT repeat it."

        final_messages = messages + tool_messages
        final_messages.append({
            "role": "user",
            "content": f"Based on the tool results above, give a concise reply.{note}",
        })
        async with httpx.AsyncClient(timeout=45.0) as client:
            r2 = await client.post(GROQ_URL, json={
                "model": CHAT_MODEL, "messages": final_messages, "max_tokens": 512,
            }, headers=headers)
        r2.raise_for_status()
        raw = r2.json()["choices"][0]["message"]["content"] or ""
        result = _strip_think(raw)

        # Retry якщо порожньо після strip
        if not result.strip():
            logger.warning("Empty reply after tool — retrying")
            async with httpx.AsyncClient(timeout=30.0) as client:
                r3 = await client.post(GROQ_URL, json={
                    "model": CHAT_MODEL, "messages": final_messages,
                    "max_tokens": 512, "temperature": 0.3,
                }, headers=headers)
            r3.raise_for_status()
            raw = r3.json()["choices"][0]["message"]["content"] or ""
            result = _strip_think(raw)

        return result

    raw = msg.get("content", "") or ""
    return _strip_think(raw)


# ─── HISTORY MANAGEMENT ───────────────────────────────────────────────────────

async def _load_history(user_id: int) -> list[dict]:
    data = await redis_get(_redis_key(user_id))
    return data if isinstance(data, list) else []


async def _save_history(user_id: int, history: list[dict]) -> None:
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await redis_set(_redis_key(user_id), history, ex=HISTORY_TTL)


async def _clear_history(user_id: int) -> None:
    await redis_delete(_redis_key(user_id))


# ─── /chat ───────────────────────────────────────────────────────────────────

@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    await state.set_state(ChatFSM.active)
    await state.update_data(lang=lang, last_ts=time.time())
    await message.answer(
        "🤖 <b>Prompt Assistant</b>\n\n"
        "Привіт! Я допоможу:\n"
        "— відповісти на запитання\n"
        "— знайти інформацію в інтернеті\n"
        "— створити промпт для зображення\n"
        "— згенерувати зображення\n"
        "— показати погоду або курс валют\n"
        "— стисло переказати статтю за URL\n\n"
        "💡 <b>Підказка</b>\n"
        "/search запит — пошук в інтернеті (у режимі /chat)\n\n"
        "👋 /stop — завершити чат"
        if lang == "ua" else
        "🤖 <b>Prompt Assistant</b>\n\n"
        "Hey! I can help you:\n"
        "— answer questions\n"
        "— find information on the web\n"
        "— create prompts for images\n"
        "— generate images\n"
        "— show weather and exchange rates\n"
        "— summarize articles by URL\n\n"
        "💡 <b>Tip</b>\n"
        "/search query — web search (in /chat mode)\n\n"
        "👋 /stop — end chat"
    )


# ─── /stop ───────────────────────────────────────────────────────────────────

@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    if await state.get_state() == ChatFSM.active:
        await _clear_history(message.from_user.id)
        await state.clear()
        await message.answer(
            "👋 Чат з AI асистентом завершено. Історію очищено." if lang == "ua"
            else "👋 Chat ended. History cleared."
        )
    else:
        await message.answer(
            "Активного чату немає." if lang == "ua"
            else "No active chat session."
        )


# ─── /search ─────────────────────────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    lang    = _detect_lang(message)
    current = await state.get_state()

    # Не перериваємо інші FSM (image, prompt, vision)
    if current and current != ChatFSM.active and "Chat" not in str(current):
        await message.answer(
            "⚠️ Завершти поточну команду перед пошуком." if lang == "ua"
            else "⚠️ Finish the current command before searching."
        )
        return

    query = (message.text or "").replace("/search", "", 1).strip()
    if not query:
        await message.answer(
            "Вкажи запит: /search що шукати" if lang == "ua"
            else "Provide query: /search what to find"
        )
        return

    wait = await message.answer("🔍 Шукаю…" if lang == "ua" else "🔍 Searching…")
    result = await tavily_search(query)
    await wait.delete()
    for chunk in _safe_split(f"🔍 {query}\n\n{result}"):
        await message.answer(chunk)


# ─── MAIN HANDLER ────────────────────────────────────────────────────────────

@router.message(ChatFSM.active)
async def on_chat_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        return

    data    = await state.get_data()
    lang    = data.get("lang", "ua")
    last_ts = data.get("last_ts", time.time())
    user_id = message.from_user.id

    # Авто-скид після AUTO_RESET_MIN хвилин
    if time.time() - last_ts > AUTO_RESET_MIN * 60:
        await _clear_history(user_id)
        await message.answer(
            "⏰ Сесія скинута через тривалу паузу. Починаємо з чистого аркуша."
            if lang == "ua" else
            "⏰ Session reset due to inactivity. Starting fresh."
        )

    await state.update_data(last_ts=time.time())

    history  = await _load_history(user_id)

    messages = [{"role": "system", "content": _get_system_prompt()}]
    messages += history[-MAX_HISTORY:]
    messages.append({"role": "user", "content": message.text})

    wait = await message.answer("💭")

    try:
        reply = await groq_chat(messages, message=message)
    except Exception as e:
        logger.exception("groq_chat failed")
        await wait.delete()
        err_str = str(e)
        if "413" in err_str:
            await message.answer(
                "⚠️ Історія чату завелика. Введи /stop щоб очистити і почати знову."
                if lang == "ua" else
                "⚠️ Chat history is too large. Type /stop to clear and start fresh."
            )
        else:
            await message.answer(
                f"❌ Помилка: {err_str[:120]}" if lang == "ua"
                else f"❌ Error: {err_str[:120]}"
            )
        return

    await wait.delete()

    history.append({"role": "user",      "content": message.text})
    history.append({"role": "assistant", "content": reply})
    await _save_history(user_id, history)

    # Відправляємо фінальну текстову відповідь
    if reply.strip():
        for chunk in _safe_split(reply):
            await message.answer(chunk)
