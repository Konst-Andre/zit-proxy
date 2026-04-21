"""
ZIT Bot — Dialog Getters
Provide data dictionaries to aiogram-dialog windows.
"""

from aiogram_dialog import DialogManager
from data import (
    SCENES, STYLE_GROUPS, STYLES, LIGHTINGS, MOODS, GENRES, SUBJECTS, UI
)


def _lang(manager: DialogManager) -> str:
    return manager.dialog_data.get("lang", "ua")


def _t(manager: DialogManager, key: str) -> str:
    return UI[_lang(manager)].get(key, key)


# ─── SUBJECT ──────────────────────────────────────────────────────────────────

async def subject_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    lang = _lang(dialog_manager)
    return {
        "text": _t(dialog_manager, "subject_prompt"),
        "lang": lang,
    }


# ─── SCENE ────────────────────────────────────────────────────────────────────

async def scene_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    scenes = [
        {"id": k, "label": v["label"]}
        for k, v in SCENES.items()
    ]
    current = dialog_manager.dialog_data.get("scene", "portrait")
    return {
        "text": _t(dialog_manager, "scene_prompt"),
        "scenes": scenes,
        "current_scene": current,
    }


# ─── SUBJECT TYPE ─────────────────────────────────────────────────────────────

async def subject_type_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    subject_types = [
        {"id": k, "label": v["label"]}
        for k, v in SUBJECTS.items()
    ]
    lang = _lang(dialog_manager)
    text = "👤 <b>Тип субʼєкта</b>\n\nОбери категорію головного обʼєкта:" if lang == "ua" \
        else "👤 <b>Subject type</b>\n\nSelect main subject category:"
    return {
        "text": text,
        "subject_types": subject_types,
    }


async def style_group_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    groups = [
        {"id": k, "label": v["label"]}
        for k, v in STYLE_GROUPS.items()
    ]
    return {
        "text": _t(dialog_manager, "style_group_prompt"),
        "style_groups": groups,
    }


# ─── STYLE ────────────────────────────────────────────────────────────────────

async def style_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    group_id = dialog_manager.dialog_data.get("style_group", "Real")
    group    = STYLE_GROUPS.get(group_id, STYLE_GROUPS["Real"])
    styles   = [
        {"id": sid, "label": STYLES[sid]["label"]}
        for sid in group["styles"]
        if sid in STYLES
    ]
    group_label = group["label"]
    return {
        "text": f"🎨 <b>Стиль — {group_label}</b>\n\nОбери стиль:",
        "styles": styles,
    }


# ─── LIGHTING ─────────────────────────────────────────────────────────────────

async def lighting_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    lightings = [
        {"id": k, "label": v["label"]}
        for k, v in LIGHTINGS.items()
        if k != ""
    ]
    return {
        "text": _t(dialog_manager, "lighting_prompt"),
        "lightings": lightings,
        "none_label": _t(dialog_manager, "none"),
    }


# ─── MOOD ─────────────────────────────────────────────────────────────────────

async def mood_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    moods = [
        {"id": k, "label": v["label"]}
        for k, v in MOODS.items()
        if k != ""
    ]
    return {
        "text": _t(dialog_manager, "mood_prompt"),
        "moods": moods,
        "skip_label": _t(dialog_manager, "skip"),
    }


# ─── GENRE ────────────────────────────────────────────────────────────────────

async def genre_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    genres = [
        {"id": k, "label": v["label"]}
        for k, v in GENRES.items()
        if k != ""
    ]
    return {
        "text": _t(dialog_manager, "genre_prompt"),
        "genres": genres,
        "skip_label": _t(dialog_manager, "skip"),
    }


# ─── RESULT ───────────────────────────────────────────────────────────────────

# Iteration button labels per language
_ITER_LABELS = {
    "ua": {
        "new":       "🔄 Нова тема",
        "regen":     "↺ Повтор",
        "improve":   "↑ Покращити",
        "realistic": "📷 Фотореал",
        "lighting":  "💡 Освітлення",
    },
    "en": {
        "new":       "🔄 New topic",
        "regen":     "↺ Regen",
        "improve":   "↑ Improve",
        "realistic": "📷 Realistic",
        "lighting":  "💡 Lighting",
    },
}


async def result_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    data    = dialog_manager.dialog_data
    result  = data.get("result", {})
    lang    = _lang(dialog_manager)

    scene_id  = data.get("scene", "portrait")
    style_id  = data.get("style", "photorealistic")
    lighting  = data.get("lighting", "")
    mood      = data.get("mood", "")
    genre     = data.get("genre", "")

    scene_label    = SCENES.get(scene_id, {}).get("label", scene_id)
    style_label    = STYLES.get(style_id, {}).get("label", style_id)
    lighting_label = LIGHTINGS.get(lighting, {}).get("label", "—") if lighting else "—"
    mood_label     = MOODS.get(mood, {}).get("label", "—") if mood else "—"
    genre_label    = GENRES.get(genre, {}).get("label", "—") if genre else "—"

    params = (
        f"<b>📐</b> {scene_label}  "
        f"<b>🎨</b> {style_label}  "
        f"<b>💡</b> {lighting_label}  "
        f"<b>🌙</b> {mood_label}  "
        f"<b>🌐</b> {genre_label}"
    )

    if "error" in result:
        body = UI[lang]["error"].format(err=result["error"])
    else:
        positive = result.get("positive", "")
        negative = result.get("negative", "")
        notes    = result.get("notes", "")
        body = (
            f"✦ <b>POSITIVE</b>\n"
            f"<code>{positive}</code>\n\n"
            f"✦ <b>NEGATIVE</b>\n"
            f"<code>{negative}</code>"
        )
        if notes:
            body += f"\n\n💡 {notes}"

    iter_lbl = _ITER_LABELS.get(lang, _ITER_LABELS["en"])

    return {
           "params":                  params,
           "subject":                data.get("subject", ""),
           "body":                     body,
           "new_label":             iter_lbl["new"],        # ← нова merged кнопка
           "regen_label":          iter_lbl["regen"],
           "improve_label":       iter_lbl["improve"],
           "realistic_label":    iter_lbl["realistic"],
           "lighting_label":      iter_lbl["lighting"],
           "share_label":           UI[lang]["share"],
           # again_label і change_label  більше не потрібні
    }
