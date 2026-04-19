"""
LLM Prompt Generator Bot — Prompt Engine
SYSTEM_PROMPT + buildUser() + groq_generate()
Based on engine v4.0 (model-agnostic rebranding)
"""

import re
import httpx
from data import SCENES, STYLES, LIGHTINGS, MOODS, GENRES, SCENE_NEGATIVES, SUBJECTS

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
BOT_MODEL = "qwen/qwen3-32b"
MAX_TOKENS = 2048
TIMEOUT = 45.0

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are an expert prompt engineer for AI image generation.
Your task: build precise, layered, natural-language prompts
that work across modern generative models — diffusion (Flux, SDXL, Stable Diffusion 3,
Z-Image Turbo, Z-Image Base) and multimodal (Gemini Imagen, Qwen-VL, Midjourney-style).

=== PROMPT QUALITY RULES ===
- Write in natural English prose — avoid comma-spam tag lists
- Forbidden tokens: masterpiece, best quality, highres, 8k, ultra-detailed
  (These are SDXL-era artifacts that degrade modern model output)
- Be specific and visual — describe what the eye sees, not abstract quality claims
- One strong specific detail beats three vague quality adjectives

=== LAYER SYSTEM — PRIORITY ORDER ===
Build the prompt in this layer order (highest to lowest priority):

  SCENE > SUBJECT > STYLE > LIGHTING > GENRE > MOOD

Rules:
1. Higher layer always takes precedence
2. Lower layer must NOT duplicate, NOT contradict the layer above it
3. Lower layer either adapts to the higher layer OR is omitted
4. If STYLE already defines lighting conditions → reduce or omit LIGHTING layer content
5. If GENRE duplicates STYLE → GENRE becomes a descriptive modifier phrase only
6. If SUBJECT duplicates STYLE descriptors → keep the more specific instance, rephrase or remove the other

=== CONFLICT RESOLUTION ===
Lighting ↔ Mood conflict:
  IF Lighting and Mood presets are semantically incompatible:
  → Lighting description ADAPTS to harmonize with Mood (Lighting is not cancelled)
  → Example: "harsh midday sunlight" + Mood "serene & peaceful"
    → Write: "harsh midday sunlight softened by atmospheric haze, calm open sky"
    → NOT: "harsh midday sunlight, strong shadows, calm peaceful mood, soft light"

Genre ↔ Style conflict:
  IF Genre contradicts Style (e.g. Anime style + Photorealistic genre):
  → Style takes priority, Genre becomes a thematic modifier only
  → Example: "Anime cel-shading with subtle cyberpunk neon color palette"

=== GENRE MODS — NATURAL PROSE FORMAT ===
When Genre modifier is provided, integrate it as a flowing phrase — NOT as comma-list tokens.
Use natural connectors: "with", "featuring", "infused with", "blending", "defined by", "steeped in", "shrouded in", "woven with".

=== NEGATIVE PROMPT RULES ===
Base: use the suggested negative from the user message as your starting point.
Length: 10–18 words MAXIMUM — no exceptions.
Focus: concrete visual errors only — anatomy, hands, face distortion, artifacts.
Forbidden in negative: low quality, worst quality, oversharpened, noisy (unless specifically needed).

Scene adaptation:
  portrait / half_body / full_body → anatomy, bad hands, face distortion
  landscape / urban / interior → compression artifacts, overexposed, noise
  product / macro → distortion, reflection artifacts, uneven lighting
  concept / animal → anatomy, deformed, extra limbs

=== LANGUAGE RULE — CRITICAL ===
Always translate non-English subject input to English.
All prompt output (positive, negative) MUST be English only.
IMPORTANT: <notes> MUST be written in the UI language specified in the user message.
If UI language is Ukrainian — write <notes> in Ukrainian. This is mandatory.

=== OUTPUT STRUCTURE — NON-NEGOTIABLE XML CONTRACT ===
Output ONLY the XML tags below — no other text before, between, or after them.
All tags must always be present, even if content is minimal.
Do not include greetings, explanations, markdown, or any text outside the XML tags.
Do not nest XML tags — tag content is plain text only.
If generation fails, still return all tags with minimal valid content.
Do not output <think> blocks or reasoning — output XML only.

<positive>
60–120 word natural English prompt. Layers integrated as flowing prose in priority order:
SCENE → SUBJECT → STYLE → LIGHTING → GENRE (as prose phrase) → MOOD (as light modifier).
</positive>
<negative>
Scene-appropriate negative, 10–18 words maximum, concrete errors only.
</negative>
<notes>
Exactly 2 short tips specific to THIS generated prompt. Separate with a blank line.

Tip 1 — WHY: explain why one specific element of this prompt works well visually.
  Reference the actual content (lighting choice, style, mood combination, etc.)

Tip 2 — ENHANCE: suggest one concrete improvement to make the image stronger.
  Focus on whichever is most relevant:
    COMPOSITION — framing, rule of thirds, negative space, leading lines, depth
    ATMOSPHERE  — strengthen mood through light quality or environmental detail
    STYLE TECHNIQUE — technique that would reinforce this particular style
    COLOR PALETTE — dominant tones, contrast, or color harmony to add or adjust
    SUBJECT FOCUS — how to better draw attention to the subject in this scene

Rules for both tips:
- Each tip: 1–2 sentences, direct and specific
- NO mention of CFG, steps, schedulers, LoRA weights, or any technical parameters
- Both tips must reference THIS prompt's actual content — no generic advice

LANGUAGE: write both tips in {NOTES_LANG}.
</notes>

=== VALIDATION BEFORE OUTPUT ===
Check all before returning:
✔ No duplicate descriptors across layers
✔ No layer conflicts
✔ Negative ≤18 words
✔ Genre mods written as prose phrase, not comma list
✔ No forbidden tokens (masterpiece, best quality, highres, 8k, ultra-detailed)
✔ All XML tags present
✔ No text outside XML tags
✔ <notes> contains exactly 2 tips, NO technical model parameters
IF any check fails → regenerate once → if still fails → return minimal valid XML"""


def get_system_prompt(lang: str) -> str:
    notes_lang = "Ukrainian" if lang == "ua" else "English"
    return SYSTEM_PROMPT_TEMPLATE.replace("{NOTES_LANG}", notes_lang)


# ─── NEGATIVE BUILDER ─────────────────────────────────────────────────────────

def build_negative(scene: str) -> str:
    tokens = SCENE_NEGATIVES.get(scene, SCENE_NEGATIVES["manual"])
    return ", ".join(tokens[:14])


# ─── USER MESSAGE BUILDER ─────────────────────────────────────────────────────

def build_user(state: dict) -> str:
    scene_id     = state.get("scene", "portrait")
    style_id     = state.get("style", "photorealistic")
    lighting     = state.get("lighting", "Cinematic")
    mood         = state.get("mood", "")
    genre        = state.get("genre", "")
    subject      = state.get("subject", "")
    subject_type = state.get("subject_type", "none")
    lang         = state.get("lang", "ua")

    sc = SCENES.get(scene_id, SCENES["portrait"])
    st = STYLES.get(style_id, STYLES["photorealistic"])
    li = LIGHTINGS.get(lighting, LIGHTINGS["Cinematic"])
    mo = MOODS.get(mood, MOODS[""])
    ge = GENRES.get(genre, GENRES[""])
    su = SUBJECTS.get(subject_type, SUBJECTS["none"])

    lang_str  = "Ukrainian" if lang == "ua" else "English"
    neg_hint  = build_negative(scene_id)
    genre_mod = ge.get("mod", "") or "none"
    subj_detail = su.get("value", "") or "none"

    lines = [
        "Generate ZIT prompt:",
        f"Subject (translate to English if needed): {subject}",
        f"UI language: {lang_str}",
        f"Subject detail: {subj_detail}",
        f"Scene: {sc['label']} | Detail: {sc['detail']}",
        f"Style: {st['label']} — {st['detail']}",
        f"Camera: {sc['camera']}",
        f"Lighting: {li['value'] or 'none'}",
        f"Mood: {mo['value'] or 'none'}",
        f"Genre: {ge['value'] or 'none'} | Genre modifier (integrate as prose phrase): {genre_mod}",
        "Resolution: 896×1152 (portrait)",
        f"Suggested negative (adapt if needed): {neg_hint}",
    ]
    return "\n".join(lines)


# ─── RESPONSE PARSER ──────────────────────────────────────────────────────────

def strip_think(text: str) -> str:
    """Remove Qwen3 thinking blocks."""
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Thought:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'\[Thinking[^\]]*\][\s\S]*?\[/Thinking[^\]]*\]', '', text, flags=re.IGNORECASE)
    return text.strip()


def extract_tag(text: str, tag: str) -> str:
    m = re.search(rf'<{tag}[^>]*>([\s\S]*?)</{tag}>', text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def parse_response(raw: str) -> dict:
    cleaned = strip_think(raw)

    # XML primary
    positive = extract_tag(cleaned, "positive")
    negative = extract_tag(cleaned, "negative")
    notes    = extract_tag(cleaned, "notes")

    if positive:
        return {"positive": positive, "negative": negative, "notes": notes}

    # XML retry — strip markdown fences
    cleaned2 = re.sub(r'```xml|```', '', cleaned).strip()
    positive = extract_tag(cleaned2, "positive")
    negative = extract_tag(cleaned2, "negative")
    notes    = extract_tag(cleaned2, "notes")
    if positive:
        return {"positive": positive, "negative": negative, "notes": notes}

    # JSON fallback
    m = re.search(r'\{[\s\S]+\}', cleaned)
    if m:
        try:
            import json
            data = json.loads(m.group(0))
            return {
                "positive": data.get("positive", ""),
                "negative": data.get("negative", ""),
                "notes":    data.get("notes", ""),
            }
        except Exception:
            pass

    # Plaintext fallback
    if len(cleaned) > 40:
        return {"positive": cleaned[:800], "negative": "", "notes": ""}

    return {"positive": "Failed to parse — check debug", "negative": "", "notes": ""}


# ─── GROQ GENERATE ────────────────────────────────────────────────────────────

async def groq_generate(state: dict, api_key: str) -> dict:
    """
    Async call to Groq API.
    Returns dict with keys: positive, negative, notes
    Raises httpx.HTTPStatusError on API errors.
    """
    system_prompt = get_system_prompt(state.get("lang", "ua"))
    user_message  = build_user(state)
    # Append /no_think for Qwen3
    user_message += "\n\n/no_think"

    payload = {
        "model": BOT_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    GROQ_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            if resp.status_code == 429:
                import asyncio
                await asyncio.sleep(3 * (attempt + 1))
                continue
            if resp.status_code >= 500:
                import asyncio
                await asyncio.sleep(2)
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return parse_response(raw)
        except httpx.TimeoutException:
            if attempt == 2:
                raise
    raise RuntimeError("Groq API: max retries exceeded")
