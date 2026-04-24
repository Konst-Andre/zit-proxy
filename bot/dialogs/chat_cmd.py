"""
ZIT Bot — /chat Agent Handler

Features:
- Groq qwen3-32b with Tavily web search (function calling)
- Persistent history via Upstash Redis (TTL 24h)
- Auto-reset after 30 min inactivity
- /stop to reset manually
- Personalized system prompt (знає контекст ZIT бота)
- /search <query> — примусовий пошук

FSM: ChatFSM.active
"""

import json
import logging
import os
import time
from datetime import datetime

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import ChatFSM
from bot.redis_client import redis_get, redis_set, redis_delete

logger = logging.getLogger(__name__)
router = Router(name="chat_cmd")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

GROQ_URL  = "https://api.groq.com/openai/v1/chat/completions"
CHAT_MODEL = "qwen/qwen3-32b"

TAVILY_URL = "https://api.tavily.com/search"

MAX_HISTORY   = 20       # максимум повідомлень в history
AUTO_RESET_MIN = 30      # хвилин до авто-скиду
HISTORY_TTL   = 86400   # 24h в Redis

# ─── SYSTEM PROMPT ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are ZIT Assistant — a smart, helpful AI agent built into the LLM Prompt Generator Bot.

Your primary context:
- This is a Telegram bot that generates structured prompts for AI image generation (Flux, SDXL, etc.)
- You know the bot's commands: /prompt (FSM generator), /random, /image (text→image), /vision (photo→prompt), inline mode
- You can help users craft better prompts, explain AI image generation concepts, and answer general questions

Your capabilities:
- Answer questions on any topic
- Search the web for current information when needed (you have a search tool)
- Summarize conversations and analyze context
- Help with prompt engineering for AI images
- Act as a general-purpose assistant

Behavior rules:
- Be concise but thorough — Telegram messages have limits
- Use Ukrainian when user writes in Ukrainian, English otherwise
- For factual/current questions → use the search tool
- For creative/generative questions → answer from knowledge
- Never mention that you're "just an AI" in a dismissive way
- If asked to generate an image prompt → provide it directly in the chat

Current date: {date}
"""


def _get_system_prompt() -> str:
    return SYSTEM_PROMPT.format(date=datetime.now().strftime("%d.%m.%Y"))


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _redis_key(user_id: int) -> str:
    return f"chat:history:{user_id}"


# ─── TAVILY SEARCH ────────────────────────────────────────────────────────────

async def tavily_search(query: str) -> str:
    """Search web via Tavily. Returns formatted results string."""
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

        for res in data.get("results", [])[:4]:
            title   = res.get("title", "")
            url     = res.get("url", "")
            content = res.get("content", "")[:300]
            parts.append(f"• {title}\n  {content}\n  {url}")

        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        logger.warning("Tavily search error: %s", e)
        return f"Search error: {str(e)[:100]}"


# ─── GROQ WITH TOOL USE ───────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information, news, facts, prices, events. "
                "Use when the user asks about something that may have changed recently "
                "or requires up-to-date data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in English for best results",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


async def groq_chat(messages: list[dict]) -> str:
    """
    Call Groq with tool use support.
    Handles one round of tool calls (search) then final response.
    """
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

    choice  = response["choices"][0]
    message = choice["message"]

    # ── Tool call handling ────────────────────────────────────────────────
    if choice.get("finish_reason") == "tool_calls" and message.get("tool_calls"):
        tool_call  = message["tool_calls"][0]
        func_name  = tool_call["function"]["name"]
        func_args  = json.loads(tool_call["function"]["arguments"])

        if func_name == "web_search":
            search_result = await tavily_search(func_args["query"])
            logger.info("Tavily search: %s", func_args["query"])
        else:
            search_result = "Unknown tool."

        # Second call with tool result
        messages_with_tool = messages + [
            message,
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": search_result,
            },
        ]

        payload2 = {
            "model": CHAT_MODEL,
            "messages": messages_with_tool,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            r2 = await client.post(GROQ_URL, json=payload2, headers=headers)
        r2.raise_for_status()
        return r2.json()["choices"][0]["message"]["content"].strip()

    return message.get("content", "").strip()


# ─── HISTORY MANAGEMENT ───────────────────────────────────────────────────────

async def _load_history(user_id: int) -> list[dict]:
    data = await redis_get(_redis_key(user_id))
    return data if isinstance(data, list) else []


async def _save_history(user_id: int, history: list[dict]) -> None:
    # Обрізаємо до MAX_HISTORY
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await redis_set(_redis_key(user_id), history, ex=HISTORY_TTL)


async def _clear_history(user_id: int) -> None:
    await redis_delete(_redis_key(user_id))


# ─── COMMANDS ────────────────────────────────────────────────────────────────

@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    await state.set_state(ChatFSM.active)
    await state.update_data(lang=lang, last_ts=time.time())

    if lang == "ua":
        text = (
            "🤖 <b>ZIT Assistant</b>\n\n"
            "Привіт! Я твій AI асистент.\n"
            "Можу відповідати на питання, шукати актуальну інфо, "
            "допомагати з промптами для генерації зображень.\n\n"
            "📌 <b>Команди:</b>\n"
            "/stop — завершити чат\n"
            "/search &lt;запит&gt; — примусовий пошук\n\n"
            "<i>Про що поговоримо?</i>"
        )
    else:
        text = (
            "🤖 <b>ZIT Assistant</b>\n\n"
            "Hey! I'm your AI assistant.\n"
            "I can answer questions, search for current info, "
            "and help with image generation prompts.\n\n"
            "📌 <b>Commands:</b>\n"
            "/stop — end chat\n"
            "/search &lt;query&gt; — force web search\n\n"
            "<i>What's on your mind?</i>"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext) -> None:
    lang = _detect_lang(message)
    current = await state.get_state()
    if current == ChatFSM.active:
        user_id = message.from_user.id
        await _clear_history(user_id)
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


@router.message(Command("search"), ChatFSM.active)
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Force web search regardless of agent decision."""
    data  = await state.get_data()
    lang  = data.get("lang", "ua")
    query = (message.text or "").replace("/search", "").strip()

    if not query:
        await message.answer(
            "Вкажи запит: /search що шукати" if lang == "ua"
            else "Provide query: /search what to find"
        )
        return

    wait = await message.answer("🔍 Шукаю…" if lang == "ua" else "🔍 Searching…")
    result = await tavily_search(query)
    await wait.delete()
    await message.answer(
        f"🔍 <b>{query}</b>\n\n{result[:2000]}",
        parse_mode="HTML",
    )


# ─── MAIN MESSAGE HANDLER ────────────────────────────────────────────────────

@router.message(ChatFSM.active)
async def on_chat_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        return

    data    = await state.get_data()
    lang    = data.get("lang", "ua")
    last_ts = data.get("last_ts", time.time())
    user_id = message.from_user.id

    # ── Авто-скид після AUTO_RESET_MIN хвилин мовчання ───────────────────
    if time.time() - last_ts > AUTO_RESET_MIN * 60:
        await _clear_history(user_id)
        if lang == "ua":
            await message.answer(
                "⏰ Сесія скинута через тривалу паузу. Починаємо з чистого аркуша."
            )
        else:
            await message.answer(
                "⏰ Session reset due to inactivity. Starting fresh."
            )

    await state.update_data(last_ts=time.time())

    # ── Load history ──────────────────────────────────────────────────────
    history = await _load_history(user_id)

    # ── Build messages ────────────────────────────────────────────────────
    messages = [{"role": "system", "content": _get_system_prompt()}]
    messages += history
    messages.append({"role": "user", "content": message.text})

    # ── Typing indicator ──────────────────────────────────────────────────
    wait = await message.answer("💭" if lang == "ua" else "💭")

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

    # ── Save history ──────────────────────────────────────────────────────
    history.append({"role": "user",      "content": message.text})
    history.append({"role": "assistant", "content": reply})
    await _save_history(user_id, history)

    # ── Send reply ────────────────────────────────────────────────────────
    # Telegram message limit 4096 — split if needed
    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await message.answer(reply[i:i+4096])
    else:
        await message.answer(reply)
