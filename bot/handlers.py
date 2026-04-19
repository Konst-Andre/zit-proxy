"""
ZIT Bot — Static Command Handlers
/start, /help — no FSM.
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from data import UI
from bot.states import ZitFSM

logger = logging.getLogger(__name__)
router = Router(name="static")

MINI_APP_URL = "https://konst-andre.github.io/zit-prompt-tg/"


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


def _open_app_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=UI[lang]["open_app"],
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
    ]])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    lang = _detect_lang(message)
    name = message.from_user.first_name or "User"
    text = UI[lang]["welcome"].format(name=name)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_open_app_markup(lang),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    lang = _detect_lang(message)
    await message.answer(
        UI[lang]["help"],
        parse_mode="HTML",
        reply_markup=_open_app_markup(lang),
    )
