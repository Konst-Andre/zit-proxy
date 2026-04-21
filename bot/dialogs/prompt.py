"""
ZIT Bot — /prompt FSM Dialog  (iteration loop patch)
Adds 4 iteration buttons to result Window:
  ↺ Повтор     — regenerate same params
  ↑ Покращити  — improve detail/atmosphere
  📷 Реально   — make more photorealistic
  💡 Світло    — enhance lighting description
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
    subject_getter, scene_getter, subject_type_getter,
    style_group_getter, style_getter, lighting_getter,
    mood_getter, genre_getter, result_getter,
)
from prompts import groq_generate, groq_iterate

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


async def on_subject_type_selected(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["subject_type"] = item_id
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
    """Full restart — clear all state, go to subject."""
    lang = manager.dialog_data.get("lang", "ua")
    manager.dialog_data.clear()
    manager.dialog_data["lang"] = lang
    await manager.switch_to(ZitFSM.subject)


async def on_change(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    """Keep subject, restart from scene."""
    for k in ["result", "scene", "subject_type", "style_group", "style",
              "lighting", "mood", "genre"]:
        manager.dialog_data.pop(k, None)
    await manager.switch_to(ZitFSM.scene)


async def on_share(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    result = manager.dialog_data.get("result", {})
    if "error" in result or not result.get("positive"):
        await callback.answer("Немає промпту для копіювання")
        return
    share_text = (
        f"<b>PROMPT</b>\n\n"
        f"<b>+</b> <code>{result['positive']}</code>\n\n"
        f"<b>–</b> <code>{result['negative']}</code>"
    )
    await callback.message.answer(share_text)
    await callback.answer()


# ─── ITERATION CALLBACKS ──────────────────────────────────────────────────────

async def _do_iterate(
    callback: CallbackQuery,
    manager: DialogManager,
    action: str,
) -> None:
    """
    Core iteration handler.
    Takes current positive → calls groq_iterate(action) → updates result.
    Shows toast while processing (Telegram non-blocking answer).
    """
    result = manager.dialog_data.get("result", {})
    positive = result.get("positive", "")

    if not positive:
        await callback.answer("Немає промпту для ітерації")
        return

    lang = manager.dialog_data.get("lang", "ua")

    # Notify user — toast stays visible ~5s while Groq processes
    wait_labels = {
        "improve":   ("⏳ Покращую...",  "⏳ Improving..."),
        "realistic": ("⏳ Роблю реальніше...", "⏳ Making realistic..."),
        "lighting":  ("⏳ Змінюю освітлення...", "⏳ Adjusting lighting..."),
    }
    ua_txt, en_txt = wait_labels.get(action, ("⏳ Обробляю...", "⏳ Processing..."))
    # Send temporary chat message (visible during processing)
    wait_msg = await callback.message.answer(ua_txt if lang == "ua" else en_txt)

    try:
        new_result = await groq_iterate(positive, action, lang, GROQ_API_KEY)
        manager.dialog_data["result"] = new_result
    except Exception as e:
        logger.exception("groq_iterate failed (action=%s)", action)
        manager.dialog_data["result"] = {"error": str(e)[:200]}
    finally:
        try:
            await wait_msg.delete()
        except Exception:
            pass

    await manager.switch_to(ZitFSM.result)
    await callback.answer()


async def on_regen(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    """Regenerate with exactly the same params — new Groq call."""
    lang = manager.dialog_data.get("lang", "ua")
    wait_msg = await callback.message.answer(
        "⏳ Перегенеровую..." if lang == "ua" else "⏳ Regenerating..."
    )
    state = dict(manager.dialog_data)
    try:
        result = await groq_generate(state, GROQ_API_KEY)
        manager.dialog_data["result"] = result
    except Exception as e:
        logger.exception("groq_generate (regen) failed")
        manager.dialog_data["result"] = {"error": str(e)[:200]}
    finally:
        try:
            await wait_msg.delete()
        except Exception:
            pass
    await manager.switch_to(ZitFSM.result)
    await callback.answer()


async def on_improve(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    await _do_iterate(callback, manager, "improve")


async def on_realistic(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    await _do_iterate(callback, manager, "realistic")


async def on_lighting_iter(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
) -> None:
    await _do_iterate(callback, manager, "lighting")


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

    # ── 3. SUBJECT TYPE ─────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="subject_type_select",
                item_id_getter=lambda x: x["id"],
                items="subject_types",
                on_click=on_subject_type_selected,
            ),
            id="subject_type_sg",
            width=1,
            height=6,
        ),
        Back(Const("◀ Назад")),
        state=ZitFSM.subject_type,
        getter=subject_type_getter,
    ),

    # ── 4. STYLE GROUP ──────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="style_group_select",
                item_id_getter=lambda x: x["id"],
                items="style_groups",
                on_click=on_style_group_selected,
            ),
            id="style_group_sg",
            width=1,
            height=5,
        ),
        Back(Const("◀ Назад")),
        state=ZitFSM.style_group,
        getter=style_group_getter,
    ),

    # ── 5. STYLE ────────────────────────────────────────────────────────────
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

    # ── 6. LIGHTING ─────────────────────────────────────────────────────────
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

    # ── 7. MOOD ─────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="mood_select",
                item_id_getter=lambda x: x["id"],
                items="moods",
                on_click=on_mood_selected,
            ),
            id="moods_sg",
            width=2,
            height=5,
        ),
        Row(
            Button(Format("{skip_label}"), id="mood_skip", on_click=on_mood_skip),
            Back(Const("◀ Назад")),
        ),
        state=ZitFSM.mood,
        getter=mood_getter,
    ),

    # ── 8. GENRE ────────────────────────────────────────────────────────────
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

    # ── 9. RESULT ───────────────────────────────────────────────────────────
    # Row 1 — navigation: повний рестарт / змінити / поділитись
    # Row 2 — iteration:  повтор / покращити / реалістично / світло
    Window(
        Format("🎯 <b>Тема:</b> {subject}\n{params}\n\n{body}"),
        Row(
            Button(Format("{again_label}"),  id="again",  on_click=on_again),
            Button(Format("{change_label}"), id="change", on_click=on_change),
            Button(Format("{share_label}"),  id="share",  on_click=on_share),
        ),
        Row(
            Button(Format("{regen_label}"),     id="regen",     on_click=on_regen),
            Button(Format("{improve_label}"),   id="improve",   on_click=on_improve),
            Button(Format("{realistic_label}"), id="realistic", on_click=on_realistic),
            Button(Format("{lighting_label}"),  id="light_iter", on_click=on_lighting_iter),
        ),
        state=ZitFSM.result,
        getter=result_getter,
    ),
)
