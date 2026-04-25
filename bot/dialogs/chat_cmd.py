"""
ZIT Bot — /chat Agent Handler
Fixes v2:
  - strip <think> blocks from Qwen3 responses
  - /search works without /chat (standalone)
  - prompt detection → <code> formatting
  - safe HTML send (strip markdown asterisks)
  - SDXL/Flux removed from system prompt
"""

import json
import logging
import os
import re
import time
from datetime import datetime

import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import ChatFSM
from bot.redis_client import redis_get, redis_set, redis_delete

logger = logging.getLogger(__name__)
router = Router(name="chat_cmd")

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_URL     = "https://api.tavily.com/search"
CHAT_MODEL     = "qwen/qwen3-32b"

MAX_HISTORY    = 20
AUTO_RESET_MIN = 30
HISTORY_TTL    = 86400


# ─── SYSTEM PROMPT ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Prompt Assistant — a smart, helpful AI agent built into the LLM Prompt Generator Bot.

Your primary context:
- This Telegram bot generates structured prompts for AI image generation
- You know the bot's commands: /prompt (FSM generator), /random, /image (text→image), /vision (photo→prompt), inline mode
- You help users craft better prompts, explain AI image generation concepts, and answer general questions

Your capabilities:
- Answer questions on any topic
- Search the web for current information when needed (you have a search tool)
- Summarize conversations and analyze context
- Help with prompt engineering for AI image generation
- Act as a general-purpose assistant

Behavior rules:
- Be concise but thorough — Telegram messages have limits
- Use Ukrainian when user writes in Ukrainian, English otherwise
- For factual/current questions → use the search tool
- For creative/generative questions → answer from knowledge
- Never mention that you're "just an AI" in a dismissive way
- When generating image prompts → always output them in this exact format:
  POSITIVE: <prompt text>
  NEGATIVE: <negative prompt text>
- Do NOT mention specific model names like SDXL, Flux, Stable Diffusion — just say "AI image generator"
- Do NOT output <think> tags or reasoning blocks — respond directly

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
    """Remove Qwen3 <think>...</think> blocks from response."""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<think>[\s\S]*", "", text, flags=re.IGNORECASE)  # unclosed
    return text.strip()


def _format_reply(text: str) -> str:
    """
    Format reply for Telegram plain text (no parse_mode).
    Detects POSITIVE/NEGATIVE prompt format and wraps in code-style markers.
    """
    # Detect prompt format → format nicely
    if "POSITIVE:" in text and "NEGATIVE:" in text:
        pos_match = re.search(r"POSITIVE:\s*(.+?)(?=NEGATIVE:|$)", text, re.DOTALL)
        neg_match = re.search(r"NEGATIVE:\s*(.+?)$", text, re.DOTALL)
        pos = pos_match.group(1).strip() if pos_match else ""
        neg = neg_match.group(1).strip() if neg_match else ""
        return (
            "✦ POSITIVE\n"
            f"{pos}\n\n"
            "✦ NEGATIVE\n"
            f"{neg}"
        )
    return text


def _safe_split(text: str, limit: int = 4096) -> list[str]:
    """Split long text into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


# ─── TAVILY SEARCH ────────────────────────────────────────────────────────────

async def tavily_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return "Search unavailable — TAVILY_API_KEY not set."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                TAVILY_URL,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": 4,
                    "search_depth": "basic",
                    "include_answer": True,
                },
            )
        data = r.json()
        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")
        for res in data.get("results", [])[:3]:
            title   = res.get("title", "")
            content = res.get("content", "")[:250]
            url     = res.get("url", "")
            parts.append(f"• {title}\n  {content}\n  {url}")
        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        logger.warning("Tavily error: %s", e)
        return f"Search error: {str(e)[:100]}"


# ─── GROQ WITH TOOL USE ───────────────────────────────────────────────────────

TOOLS = [{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information, news, facts, prices, events. "
            "Use when the user asks about something recent or requiring up-to-date data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query in English"}
            },
            "required": ["query"],
        },
    },
}]


async def groq_chat(messages: list[dict]) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(GROQ_URL, json=payload, headers=headers)
    r.raise_for_status()
    response = r.json()
    choice   = response["choices"][0]
    msg      = choice["message"]

    if choice.get("finish_reason") == "tool_calls" and msg.get("tool_calls"):
        tool_call = msg["tool_calls"][0]
        func_args = json.loads(tool_call["function"]["arguments"])
        search_result = await tavily_search(func_args.get("query", ""))
        logger.info("Tavily search: %s", func_args.get("query"))

        messages_with_tool = messages + [
            msg,
            {"role": "tool", "tool_call_id": tool_call["id"], "content": search_result},
        ]
        async with httpx.AsyncClient(timeout=45.0) as client:
            r2 = await client.post(
                GROQ_URL,
                json={"model": CHAT_MODEL, "messages": messages_with_tool, "max_tokens": 1024},
                headers=headers,
            )
        r2.raise_for_status()
        raw = r2.json()["choices"][0]["message"]["content"] or ""
        return _strip_think(raw)

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
        "🤖 Prompt Assistant\n\n"
        "Привіт! Можу відповідати на питання, шукати актуальну інфо, "
        "створювати промпти для генерації зображень.\n\n"
        "/stop — завершити чат\n"
        "/search запит — пошук в інтернеті"
        if lang == "ua" else
        "🤖 Prompt Assistant\n\n"
        "Hey! I can answer questions, search for current info, "
        "and help with image generation prompts.\n\n"
        "/stop — end chat\n"
        "/search query — web search"
    )


# ─── /stop ───────────────────────────────────────────────────────────────────

@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    current = await state.get_state()
    if current == ChatFSM.active:
        await _clear_history(message.from_user.id)
        await state.clear()
        await message.answer(
            "👋 Чат завершено. Історію очищено." if lang == "ua"
            else "👋 Chat ended. History cleared."
        )
    else:
        await message.answer(
            "Активного чату немає." if lang == "ua"
            else "No active chat session."
        )


# ─── /search — працює і без /chat ────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    lang  = _detect_lang(message)
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

    text = f"🔍 {query}\n\n{result}"
    for chunk in _safe_split(text):
        await message.answer(chunk)


# ─── MAIN MESSAGE HANDLER ────────────────────────────────────────────────────

@router.message(ChatFSM.active)
async def on_chat_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        return

    data    = await state.get_data()
    lang    = data.get("lang", "ua")
    last_ts = data.get("last_ts", time.time())
    user_id = message.from_user.id

    # Авто-скид
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
    messages += history
    messages.append({"role": "user", "content": message.text})

    wait = await message.answer("💭")

    try:
        reply = await groq_chat(messages)
    except Exception as e:
        logger.exception("groq_chat failed")
        await wait.delete()
        await message.answer(
            f"❌ Помилка: {str(e)[:120]}" if lang == "ua"
            else f"❌ Error: {str(e)[:120]}"
        )
        return

    await wait.delete()

    history.append({"role": "user",      "content": message.text})
    history.append({"role": "assistant", "content": reply})
    await _save_history(user_id, history)

    formatted = _format_reply(reply)
    for chunk in _safe_split(formatted):
        await message.answer(chunk)
