"""
ZIT Bot — /prompt FSM Dialog
Windows: subject → scene → style_group → style → lighting → mood → genre → [generate] → result
"""

import os
import logging
from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import (
    Button, Select, ScrollingGroup, Row, Back, Cancel,
)
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput, ManagedTextInput

from bot.states import ZitFSM
from bot.getters import (
    subject_getter, scene_getter, style_group_getter,
    style_getter, lighting_getter, mood_getter, genre_getter,
    result_getter,
)
from prompts import groq_generate

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


# ─── CALLBACKS ────────────────────────────────────────────────────────────────

async def on_subject_entered(
    message: Message,
    widget: ManagedTextInput,
    manager: DialogManager,
    value: str,
) -> None:
    manager.dialog_data["subject"] = value.strip()
    await manager.next()


async def on_scene_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["scene"] = item_id
    await manager.next()


async def on_style_group_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["style_group"] = item_id
    await manager.next()


async def on_style_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["style"] = item_id
    await manager.next()


async def on_lighting_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["lighting"] = item_id
    await manager.next()


async def on_lighting_none(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    manager.dialog_data["lighting"] = ""
    await manager.next()


async def on_mood_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["mood"] = item_id
    await manager.switch_to(ZitFSM.genre)


async def on_mood_skip(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    manager.dialog_data["mood"] = ""
    await manager.switch_to(ZitFSM.genre)


async def _do_generate(callback: CallbackQuery, manager: DialogManager) -> None:
    """Common generation logic: show typing, call API, store result, switch to result."""
    await callback.message.answer("⏳ Generating prompt…")
    state = dict(manager.dialog_data)
    try:
        result = await groq_generate(state, GROQ_API_KEY)
        manager.dialog_data["result"] = result
    except Exception as e:
        logger.exception("groq_generate failed")
        manager.dialog_data["result"] = {"error": str(e)[:200]}
    await manager.switch_to(ZitFSM.result)


async def on_genre_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["genre"] = item_id
    await _do_generate(callback, manager)


async def on_genre_skip(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    manager.dialog_data["genre"] = ""
    await _do_generate(callback, manager)


# ─── RESULT CALLBACKS ─────────────────────────────────────────────────────────

async def on_again(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    """Reset to subject input, keep language."""
    lang = manager.dialog_data.get("lang", "ua")
    manager.dialog_data.clear()
    manager.dialog_data["lang"] = lang
    await manager.switch_to(ZitFSM.subject)


async def on_change(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    """Go back to scene selection to change parameters."""
    # Clear result and generation, keep subject and lang
    for k in ["result", "scene", "style_group", "style", "lighting", "mood", "genre"]:
        manager.dialog_data.pop(k, None)
    await manager.switch_to(ZitFSM.scene)


async def on_share(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    """Send prompt as copyable message."""
    result = manager.dialog_data.get("result", {})
    if "error" in result or not result.get("positive"):
        await callback.answer("Немає промпту для копіювання")
        return
    share_text = (
        f"<b>ZIT PROMPT</b>\n\n"
        f"<b>+</b> <code>{result['positive']}</code>\n\n"
        f"<b>–</b> <code>{result['negative']}</code>"
    )
    await callback.message.answer(share_text)
    await callback.answer()


# ─── DIALOG ───────────────────────────────────────────────────────────────────

prompt_dialog = Dialog(
    # ── 1. SUBJECT ──────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        TextInput(
            id="subject_input",
            on_success=on_subject_entered,
        ),
        Cancel(Const("✖ Скасувати")),
        state=ZitFSM.subject,
        getter=subject_getter,
    ),

    # ── 2. SCENE ────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="scene_select",
                item_id_getter=lambda x: x["id"],
                items="scenes",
                on_click=on_scene_selected,
            ),
            id="scenes_sg",
            width=2,
            height=6,
        ),
        Back(Const("◀ Назад")),
        state=ZitFSM.scene,
        getter=scene_getter,
    ),

    # ── 3. STYLE GROUP ──────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Select(
            Format("{item[label]}"),
            id="style_group_select",
            item_id_getter=lambda x: x["id"],
            items="style_groups",
            on_click=on_style_group_selected,
        ),
        Back(Const("◀ Назад")),
        state=ZitFSM.style_group,
        getter=style_group_getter,
    ),

    # ── 4. STYLE ────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="style_select",
                item_id_getter=lambda x: x["id"],
                items="styles",
                on_click=on_style_selected,
            ),
            id="styles_sg",
            width=2,
            height=5,
        ),
        Back(Const("◀ Назад")),
        state=ZitFSM.style,
        getter=style_getter,
    ),

    # ── 5. LIGHTING ─────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="lighting_select",
                item_id_getter=lambda x: x["id"],
                items="lightings",
                on_click=on_lighting_selected,
            ),
            id="lightings_sg",
            width=2,
            height=5,
        ),
        Row(
            Button(Format("{none_label}"), id="lighting_none", on_click=on_lighting_none),
            Back(Const("◀ Назад")),
        ),
        state=ZitFSM.lighting,
        getter=lighting_getter,
    ),

    # ── 6. MOOD ─────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Select(
            Format("{item[label]}"),
            id="mood_select",
            item_id_getter=lambda x: x["id"],
            items="moods",
            on_click=on_mood_selected,
        ),
        Row(
            Button(Format("{skip_label}"), id="mood_skip", on_click=on_mood_skip),
            Back(Const("◀ Назад")),
        ),
        state=ZitFSM.mood,
        getter=mood_getter,
    ),

    # ── 7. GENRE ────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="genre_select",
                item_id_getter=lambda x: x["id"],
                items="genres",
                on_click=on_genre_selected,
            ),
            id="genres_sg",
            width=2,
            height=6,
        ),
        Row(
            Button(Format("{skip_label}"), id="genre_skip", on_click=on_genre_skip),
            Back(Const("◀ Назад")),
        ),
        state=ZitFSM.genre,
        getter=genre_getter,
    ),

    # ── 8. RESULT ───────────────────────────────────────────────────────────
    Window(
        Format("🎯 <b>Тема:</b> {subject}\n{params}\n\n{body}"),
        Row(
            Button(Format("{again_label}"),  id="again",  on_click=on_again),
            Button(Format("{change_label}"), id="change", on_click=on_change),
            Button(Format("{share_label}"),  id="share",  on_click=on_share),
        ),
        state=ZitFSM.result,
        getter=result_getter,
    ),
)
