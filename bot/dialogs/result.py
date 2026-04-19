"""
ZIT Bot — Result Formatter
Shared utility for formatting generation results as Telegram HTML messages.
Used by both prompt dialog and random handler.
"""

from data import SCENES, STYLES, LIGHTINGS, MOODS, GENRES, UI


def format_result_message(state: dict, result: dict, lang: str) -> str:
    """
    Format a generation result into a Telegram HTML message string.

    Args:
        state:  dict with scene, style, lighting, mood, genre, subject keys
        result: dict with positive, negative, notes keys (or error key)
        lang:   "ua" or "en"

    Returns:
        Formatted HTML string ready for sendMessage.
    """
    scene_id  = state.get("scene", "portrait")
    style_id  = state.get("style", "photorealistic")
    lighting  = state.get("lighting", "")
    mood      = state.get("mood", "")
    genre     = state.get("genre", "")
    subject   = state.get("subject", "")

    scene_label    = SCENES.get(scene_id, {}).get("label", scene_id)
    style_label    = STYLES.get(style_id, {}).get("label", style_id)
    lighting_label = LIGHTINGS.get(lighting, {}).get("label", "—") if lighting else "—"
    mood_label     = MOODS.get(mood, {}).get("label", "—") if mood else "—"
    genre_label    = GENRES.get(genre, {}).get("label", "—") if genre else "—"

    params_line = (
        f"📐 {scene_label} · 🎨 {style_label} · "
        f"💡 {lighting_label} · 🌙 {mood_label} · 🌐 {genre_label}"
    )

    if "error" in result:
        return (
            f"🎯 <b>Тема:</b> {subject}\n"
            f"{params_line}\n\n"
            f"{UI[lang]['error'].format(err=result['error'])}"
        )

    positive = result.get("positive", "")
    negative = result.get("negative", "")
    notes    = result.get("notes", "")

    body = (
        f"🎯 <b>Тема:</b> {subject}\n"
        f"{params_line}\n\n"
        f"✦ <b>POSITIVE</b>\n"
        f"<code>{positive}</code>\n\n"
        f"✦ <b>NEGATIVE</b>\n"
        f"<code>{negative}</code>"
    )
    if notes:
        body += f"\n\n💡 {notes}"

    return body
