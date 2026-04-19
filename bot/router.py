"""
ZIT Bot — Router / Dispatcher Setup
Creates and returns the configured aiogram Dispatcher.
"""

import logging

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram_dialog import setup_dialogs, DialogManager, StartMode

from bot.states import ZitFSM
from bot.dialogs.prompt import prompt_dialog
from bot.dialogs.random import router as random_router
from bot.dialogs.vision import router as vision_router
from bot.handlers import router as static_router

logger = logging.getLogger(__name__)


def _detect_lang(message: Message) -> str:
    lc = (message.from_user.language_code or "").lower()
    return "ua" if lc.startswith("uk") else "en"


# ─── /prompt entry ────────────────────────────────────────────────────────────

prompt_entry_router = Router(name="prompt_entry")


@prompt_entry_router.message(Command("prompt"))
async def cmd_prompt(message: Message, dialog_manager: DialogManager) -> None:
    lang = _detect_lang(message)
    await dialog_manager.start(
        ZitFSM.subject,
        mode=StartMode.RESET_STACK,
        data={"lang": lang},
    )


# ─── Dispatcher factory ───────────────────────────────────────────────────────

def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers (order matters — dialogs must be registered via setup_dialogs)
    dp.include_router(static_router)
    dp.include_router(random_router)
    dp.include_router(vision_router)
    dp.include_router(prompt_entry_router)

    # Register aiogram-dialog dialogs
    dp.include_router(prompt_dialog)
    setup_dialogs(dp)

    return dp
