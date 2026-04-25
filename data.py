"""
ZIT Bot — Data Layer
All parameter dictionaries extracted from ZIT Prompt Engine v3.8.0
"""

# ─── UI STRINGS ───────────────────────────────────────────────────────────────

UI = {
    "ua": {
        "welcome": (
            "👋 Привіт, <b>{name}</b>!\n\n"
            "Я <b>LLM Prompt Generator</b> — генерую структуровані промпти та виконую AI-запити.\n\n"
            "<b>Команди:</b>\n"
            "📝 /prompt — згенерувати промпт\n"
            "🎲 /random — рандомний промпт\n"
            "🖼 /image — зображення за темою\n"
            "🤖 /chat — AI асистент\n"
            "🔍 /search — пошук в інтернеті\n"
            "❓ /help — довідка\n"
            "👋 /stop — завершити чат з AI асистентом\n\n"
            "Працюй через команди або відкрий повний генератор:"
     ),
        "help": (
            "📖 <b>LLM Prompt Generator — Довідка</b>\n\n"
            "<b>Команди:</b>\n"
            "📝 /prompt — створити промпт з параметрами\n"
            "🎲 /random — випадковий промпт\n"
            "🖼 /image — згенерувати зображення\n"
            "🤖 /chat — AI асистент\n"
            "🔍 /search — пошук в інтернеті\n"
            "❓ /help — ця довідка\n"
            "👋 /stop — завершити чат з AI асистентом\n\n"
            "<b>Як користуватись:</b>\n"
            "• /prompt — коли потрібен контроль (сцена, стиль, світло, настрій)\n"
            "• /random — коли потрібна ідея або швидкий старт\n"
            "• /image — щоб одразу отримати зображення за темою\n"
            "• /chat — для діалогу з AI (питання, тексти, допомога)\n"
            "• /search — коли потрібна актуальна інформація з інтернету\n"
            "• /stop — щоб завершити чат з AI асистентом\n\n"
            "Для розширених налаштувань відкрий повний генератор:"
),
        "subject_prompt": "✍️ <b>Введи тему</b>\n\nОпиши що зобразити. Можна українською — LLM перекладе автоматично.",
        "scene_prompt": "🎬 <b>Сцена</b>\n\nОбери тип кадрування:",
        "style_group_prompt": "🎨 <b>Стиль — група</b>\n\nОбери категорію стилю:",
        "style_prompt": "🎨 <b>Стиль</b>\n\nОбери стиль зображення:",
        "lighting_prompt": "💡 <b>Освітлення</b>\n\nОбери тип світла:",
        "mood_prompt": "🌙 <b>Настрій</b>\n\nОбери або пропусти:",
        "genre_prompt": "🌐 <b>Жанр</b>\n\nОбери або пропусти:",
        "generating": "⏳ Генерація промпту...",
        "skip": "— Пропустити —",
        "none": "— Без освітлення —",
        "back": "◀ Назад",
        "again": "🔄 Ще раз",
        "change": "✏️ Змінити",
        "share": "⤴ Поділитись",
        "error": "❌ Помилка генерації: {err}",
        "open_app": "🫧 Відкрити генератор",
    },
    "en": {
        "welcome": (
            "👋 Hi, <b>{name}</b>!\n\n"
            "I'm <b>LLM Prompt Generator</b> — I generate structured prompts and execute AI queries.\n\n"
            "<b>Commands:</b>\n"
            "📝 /prompt — generate a prompt\n"
            "🎲 /random — random prompt\n"
            "🖼 /image — generate an image\n"
            "🤖 /chat — AI assistant\n"
            "🔍 /search — web search\n"
            "❓ /help — guide\n"
            "👋 /stop — end chat with AI assistant\n\n"
            "Use commands or open the full generator:"
        ),
        "help": (
            "📖 <b>LLM Prompt Generator — Guide</b>\n\n"
            "<b>Commands:</b>\n"
            "• /prompt — interactive generator (scene, style, lighting, mood, genre)\n"
            "• /random — random subject + parameters → instant generation\n"
            "• /help — this guide\n\n"
            "<b>Model:</b> qwen/qwen3-32b via Groq API\n"
            "<b>Architecture:</b> Lumina2 / ZIT (CFG 1.5, Steps 12)\n\n"
            "For advanced settings — open the full generator:"
        ),
        "subject_prompt": "✍️ <b>Enter subject</b>\n\nDescribe what to generate. Any language — LLM will translate.",
        "scene_prompt": "🎬 <b>Scene</b>\n\nSelect framing type:",
        "style_group_prompt": "🎨 <b>Style — group</b>\n\nSelect style category:",
        "style_prompt": "🎨 <b>Style</b>\n\nSelect image style:",
        "lighting_prompt": "💡 <b>Lighting</b>\n\nSelect light type:",
        "mood_prompt": "🌙 <b>Mood</b>\n\nSelect or skip:",
        "genre_prompt": "🌐 <b>Genre</b>\n\nSelect or skip:",
        "generating": "⏳ Generating prompt...",
        "skip": "— Skip —",
        "none": "— No lighting —",
        "back": "◀ Back",
        "again": "🔄 Again",
        "change": "✏️ Change",
        "share": "⤴ Share",
        "error": "❌ Generation error: {err}",
        "open_app": "🫧 Open Generator",
    },
}


# ─── SCENES ───────────────────────────────────────────────────────────────────

SCENES: dict[str, dict] = {
    "portrait": {
        "label": "Portrait",
        "camera": "85mm portrait lens",
        "detail": "a tight portrait framing focused on the face and head with minimal background presence",
    },
    "half_body": {
        "label": "Half-body",
        "camera": "50mm lens",
        "detail": "a medium shot showing the upper body with natural proportions and balanced composition",
    },
    "full_body": {
        "label": "Full body",
        "camera": "35mm lens",
        "detail": "a full body composition where the entire figure is visible within the surrounding environment",
    },
    "landscape": {
        "label": "Landscape",
        "camera": "wide angle lens",
        "detail": "an expansive scene emphasizing layered depth with foreground, midground, and background separation",
    },
    "urban": {
        "label": "Urban",
        "camera": "35mm lens",
        "detail": "a street-level view capturing urban structures, perspective lines, and environmental context",
    },
    "interior": {
        "label": "Interior",
        "camera": "24mm wide lens",
        "detail": "an indoor composition showing spatial layout, depth, and object relationships within the environment",
    },
    "architecture": {
        "label": "Architect.",
        "camera": "35mm tilt-shift",
        "detail": "a structured architectural view with corrected perspective and emphasis on geometry and vertical lines",
    },
    "macro": {
        "label": "Macro",
        "camera": "macro lens",
        "detail": "an extreme close-up focusing on fine surface details with the subject filling the frame",
    },
    "animal": {
        "label": "Animal",
        "camera": "85mm portrait lens",
        "detail": "a subject-focused framing where the animal is clearly visible and separated from the background",
    },
    "product": {
        "label": "Product",
        "camera": "85mm macro lens",
        "detail": "a clean and centered composition that isolates the product and presents its form clearly",
    },
    "concept": {
        "label": "Concept",
        "camera": "dynamic framing, artistic composition",
        "detail": "a composition driven by visual concept and narrative, with flexible perspective and structure",
    },
    "manual": {
        "label": "Manual",
        "camera": "intentional composition, creative perspective",
        "detail": "",
    },
}


# ─── STYLE GROUPS ─────────────────────────────────────────────────────────────

STYLE_GROUPS: dict[str, dict] = {
    "Real": {
        "label": "Realistic",
        "styles": ["photorealistic", "cinematic", "documentary", "fashion", "analog", "monochrome"],
    },
    "Illustrated": {
        "label": "Illustrated",
        "styles": ["digital_art", "concept_art", "illustration", "oil_painting", "watercolor", "pencil_sketch", "impressionism"],
    },
    "Stylized": {
        "label": "Stylized",
        "styles": ["anime", "manga", "comic", "ink_wash", "ukiyo_e"],
    },
    "3D/Render": {
        "label": "3D / Render",
        "styles": ["3d_render", "low_poly", "isometric"],
    },
    "Digital": {
        "label": "Digital",
        "styles": ["pixel_art", "flat_design", "glitch"],
    },
}


# ─── STYLES ───────────────────────────────────────────────────────────────────

STYLES: dict[str, dict] = {
    # Real
    "photorealistic": {
        "label": "Photorealistic",
        "group": "Real",
        "detail": "rendered with realistic material response, accurate color reproduction, and natural surface detail with sharp focus",
    },
    "cinematic": {
        "label": "Cinematic",
        "group": "Real",
        "detail": "rendered as a cinematic film still with controlled depth of field, subtle anamorphic bokeh, and balanced color grading",
    },
    "documentary": {
        "label": "Documentary",
        "group": "Real",
        "detail": "captured with candid unposed framing, preserving raw realistic tones and minimal staging",
    },
    "fashion": {
        "label": "Fashion Editorial",
        "group": "Real",
        "detail": "styled as a high-contrast editorial composition with deliberate posing and a polished magazine aesthetic",
    },
    "analog": {
        "label": "Analog Film",
        "group": "Real",
        "detail": "rendered with visible film grain, subtle color shifts, soft contrast, and vintage tonal characteristics",
    },
    "monochrome": {
        "label": "Monochrome",
        "group": "Real",
        "detail": "rendered in strict black and white using only neutral grayscale tones with strong tonal contrast, deep blacks, and clean whites",
    },
    # Illustrated
    "digital_art": {
        "label": "Digital Art",
        "group": "Illustrated",
        "detail": "rendered with clean digital techniques featuring smooth gradients, stylized shading, crisp edges, and a controlled color palette",
    },
    "concept_art": {
        "label": "Concept Art",
        "group": "Illustrated",
        "detail": "painted with loose expressive strokes, dynamic composition, and strong atmospheric depth focused on visual storytelling",
    },
    "illustration": {
        "label": "Illustration",
        "group": "Illustrated",
        "detail": "drawn with clear line art, simplified stylized forms, and strong graphic clarity",
    },
    "oil_painting": {
        "label": "Oil Painting",
        "group": "Illustrated",
        "detail": "painted with thick textured brushwork and visible impasto layers, using rich saturated color and traditional painterly techniques",
    },
    "watercolor": {
        "label": "Watercolor",
        "group": "Illustrated",
        "detail": "painted with soft wet-on-wet washes, visible pigment diffusion, paper texture, and transparent layered color",
    },
    "pencil_sketch": {
        "label": "Pencil Sketch",
        "group": "Illustrated",
        "detail": "drawn with graphite lines and cross-hatching, using light shading and a raw sketch-like quality with minimal fill",
    },
    "impressionism": {
        "label": "Impressionism",
        "group": "Illustrated",
        "detail": "painted with loose dappled brushstrokes, soft edges, and a painterly texture that captures a fleeting moment",
    },
    # Stylized
    "anime": {
        "label": "Anime",
        "group": "Stylized",
        "detail": "rendered with cel shading, clean line art, expressive eyes, flat color fills, and stylized character proportions",
    },
    "manga": {
        "label": "Manga",
        "group": "Stylized",
        "detail": "drawn in black and white with ink lines and screentone shading, using high contrast and graphic storytelling composition",
    },
    "comic": {
        "label": "Comic Book",
        "group": "Stylized",
        "detail": "illustrated with bold ink outlines, halftone shading, and dynamic composition with strong visual contrast",
    },
    "ink_wash": {
        "label": "Ink Wash",
        "group": "Stylized",
        "detail": "painted with diluted black ink using expressive brushwork, negative space, and spontaneous strokes in a traditional aesthetic",
    },
    "ukiyo_e": {
        "label": "Ukiyo-e",
        "group": "Stylized",
        "detail": "rendered in traditional woodblock print style with flat bold outlines, limited color bands, and decorative patterns",
    },
    # 3D/Render
    "3d_render": {
        "label": "3D Render",
        "group": "3D/Render",
        "detail": "rendered using physically based rendering with global illumination, realistic reflections, and accurate material response",
    },
    "low_poly": {
        "label": "Low Poly 3D",
        "group": "3D/Render",
        "detail": "modeled with low polygon geometry, flat shading per face, sharp edges, and simplified visual detail",
    },
    "isometric": {
        "label": "Isometric",
        "group": "3D/Render",
        "detail": "constructed in strict isometric perspective with clean geometry, even spatial layout, and stylized structure",
    },
    # Digital
    "pixel_art": {
        "label": "Pixel Art",
        "group": "Digital",
        "detail": "rendered on a visible pixel grid with limited resolution, dithering patterns, and a restricted retro color palette",
    },
    "flat_design": {
        "label": "Flat Design",
        "group": "Digital",
        "detail": "designed with flat solid colors, no gradients or shadows, and simple geometric shapes with strong contrast",
    },
    "glitch": {
        "label": "Glitch Art",
        "group": "Digital",
        "detail": "distorted with RGB channel shifts, digital noise bands, scanlines, and fragmented image artifacts",
    },
}


# ─── LIGHTINGS ────────────────────────────────────────────────────────────────

LIGHTINGS: dict[str, dict] = {
    "": {
        "label": "— none —",
        "value": "",
    },
    "Cinematic": {
        "label": "Cinematic",
        "value": "lit with dramatic cinematic lighting that creates strong contrast and clearly defined shadows",
    },
    "Soft Natural": {
        "label": "Soft Natural",
        "value": "lit with soft diffused natural daylight that produces even and gentle illumination",
    },
    "Golden Hour": {
        "label": "Golden Hour",
        "value": "lit by warm golden hour sunlight with long soft shadows and a subtle atmospheric glow",
    },
    "Blue Hour": {
        "label": "Blue Hour",
        "value": "lit by cool ambient blue hour light with soft twilight tones and low contrast",
    },
    "Overcast": {
        "label": "Overcast",
        "value": "lit under an overcast sky with soft shadowless light and evenly distributed illumination",
    },
    "Rim Light": {
        "label": "Rim Light",
        "value": "lit with strong rim lighting that creates bright edge highlights and clear subject separation from the background",
    },
    "Neon / LED": {
        "label": "Neon / LED",
        "value": "lit with neon and LED sources that create luminous colored glow and reflective highlights on surfaces",
    },
    "Volumetric Rays": {
        "label": "Volumetric Rays",
        "value": "lit with volumetric light beams that create visible atmospheric rays and enhance depth",
    },
    "Studio Softbox": {
        "label": "Studio Softbox",
        "value": "lit with studio softbox lighting that produces controlled highlights and soft directional shadows",
    },
    "Candlelight": {
        "label": "Candlelight",
        "value": "lit by warm candlelight that produces soft flickering shadows in a low-light environment",
    },
    "Moonlight": {
        "label": "Moonlight",
        "value": "lit by cold moonlight that creates a quiet night atmosphere with subtle natural blue tones",
    },
    "Harsh Midday": {
        "label": "Harsh Midday",
        "value": "lit by harsh midday sunlight that produces strong shadows, high contrast, and crisp highlights",
    },
}


# ─── MOODS ────────────────────────────────────────────────────────────────────

MOODS: dict[str, dict] = {
    "": {"label": "— none —", "value": ""},
    "Tense & dramatic": {
        "label": "Tense & dramatic",
        "value": "with a tense and dramatic feeling that conveys intensity and emotional pressure",
    },
    "Serene & peaceful": {
        "label": "Serene & peaceful",
        "value": "with a calm and peaceful feeling that conveys stillness and quiet balance",
    },
    "Mysterious": {
        "label": "Mysterious",
        "value": "with a mysterious feeling that obscures clarity and invites interpretation",
    },
    "Epic & grand": {
        "label": "Epic & grand",
        "value": "with an epic and grand feeling that emphasizes scale and significance",
    },
    "Melancholic": {
        "label": "Melancholic",
        "value": "with a melancholic feeling that conveys quiet sadness and reflection",
    },
    "Joyful & vibrant": {
        "label": "Joyful & vibrant",
        "value": "with a joyful and lively feeling that conveys energy and positivity",
    },
    "Gritty & raw": {
        "label": "Gritty & raw",
        "value": "with a gritty and raw feeling that emphasizes realism and rough intensity",
    },
    "Moody & atmospheric": {
        "label": "Moody & atmospheric",
        "value": "with a moody and atmospheric feeling that emphasizes depth and emotional weight",
    },
    "Ethereal & dreamy": {
        "label": "Ethereal & dreamy",
        "value": "with an ethereal and dreamlike feeling that softens reality and creates a sense of lightness",
    },
}


# ─── GENRES ───────────────────────────────────────────────────────────────────

GENRES: dict[str, dict] = {
    "": {"label": "— none —", "value": "", "mod": ""},
    "Cyberpunk": {
        "label": "Cyberpunk",
        "value": "in a cyberpunk world with advanced technology, dense urban environments, and a dystopian futuristic aesthetic",
        "mod": "with neon lights reflecting on wet streets, rain-slicked surfaces, and holographic digital overlays",
    },
    "Fantasy": {
        "label": "Fantasy",
        "value": "in a fantasy world with magical elements and an otherworldly environment",
        "mod": "infused with magical atmosphere, mystical elements, and otherworldly beauty",
    },
    "Dark Fantasy": {
        "label": "Dark Fantasy",
        "value": "in a dark fantasy world with gothic elements and stylized dark themes",
        "mod": "shrouded in dark gothic atmosphere, ominous shadows, and cursed imagery",
    },
    "Sci-Fi": {
        "label": "Sci-Fi",
        "value": "in a science fiction setting featuring advanced technology and futuristic concepts",
        "mod": "featuring advanced technology, space-age aesthetic, and clean futurism",
    },
    "Solarpunk": {
        "label": "Solarpunk",
        "value": "in a solarpunk world combining ecological design, sustainable technology, and harmonious environments",
        "mod": "blending lush greenery, sustainable technology, and warm optimistic light",
    },
    "Noir": {
        "label": "Noir",
        "value": "in a noir-inspired setting with a 1940s aesthetic and classic cinematic styling",
        "mod": "defined by high-contrast black shadows, 1940s atmosphere, and moral ambiguity",
    },
    "Post-Apocalyptic": {
        "label": "Post-Apocalyptic",
        "value": "in a post-apocalyptic world with ruins, decay, and signs of survival",
        "mod": "filled with ruins, overgrown decay, dust and ash, and survival aesthetic",
    },
    "Historical": {
        "label": "Historical",
        "value": "in a historically accurate environment reflecting a specific past time period",
        "mod": "enriched with period-accurate details, aged textures, and historical authenticity",
    },
    "Mythological": {
        "label": "Mythological",
        "value": "based on mythological themes featuring ancient gods, legends, and symbolic elements",
        "mod": "elevated by divine scale, ancient symbols, and timeless mythic power",
    },
    "Surreal": {
        "label": "Surreal",
        "value": "presented with surreal visual logic and unconventional spatial relationships",
        "mod": "woven with dreamlike logic, impossible geometry, and uncanny atmosphere",
    },
    "Horror": {
        "label": "Horror",
        "value": "in a horror-themed environment with unsettling visual elements",
        "mod": "steeped in dread atmosphere, unsettling shadows, and psychological tension",
    },
    "Contemporary": {
        "label": "Contemporary",
        "value": "in a modern contemporary environment reflecting present-day reality",
        "mod": "",
    },
    "Futuristic": {
        "label": "Futuristic",
        "value": "in a futuristic environment featuring advanced design and forward-looking technology",
        "mod": "showcasing sleek minimalist future tech, chrome and light, and utopian scale",
    },
}


# ─── SUBJECTS ─────────────────────────────────────────────────────────────────

SUBJECTS: dict[str, dict] = {
    "none": {
        "label": "— None —",
        "value": "",
    },
    "person": {
        "label": "Human",
        "value": "a human subject with natural body proportions and a clear anatomical structure",
    },
    "animal": {
        "label": "Animal",
        "value": "an animal subject with species-specific anatomy and recognizable physical traits",
    },
    "product": {
        "label": "Product",
        "value": "a product with a recognizable design, defined shape, and clear structural form",
    },
    "object": {
        "label": "Object",
        "value": "a single object with a clear shape, solid structure, and identifiable form",
    },
    "environment": {
        "label": "Environment",
        "value": "an environment composed of spatial elements with a defined layout and relationships between structures",
    },
}




SCENE_NEGATIVES: dict[str, list[str]] = {
    "portrait":     ["bad anatomy", "bad hands", "distorted face", "deformed fingers", "extra limbs", "blurry", "watermark", "text"],
    "half_body":    ["bad anatomy", "bad hands", "distorted face", "deformed fingers", "extra limbs", "blurry", "watermark", "text"],
    "full_body":    ["bad anatomy", "bad hands", "distorted face", "deformed fingers", "extra limbs", "blurry", "watermark", "text"],
    "landscape":    ["compression artifacts", "overexposed", "noise", "blurry", "watermark", "text"],
    "urban":        ["compression artifacts", "overexposed", "noise", "blurry", "watermark", "text"],
    "interior":     ["compression artifacts", "distortion", "noise", "blurry", "watermark", "text"],
    "architecture": ["distorted perspective", "converging verticals", "blurry", "watermark", "text"],
    "macro":        ["distortion", "reflection artifacts", "uneven lighting", "blurry", "watermark", "text"],
    "animal":       ["bad anatomy", "deformed", "extra limbs", "blurry", "watermark", "text"],
    "product":      ["distortion", "reflection artifacts", "uneven lighting", "blurry", "watermark", "text"],
    "concept":      ["bad anatomy", "deformed", "extra limbs", "blurry", "watermark", "text"],
    "manual":       ["blurry", "watermark", "text", "noise", "artifacts"],
}


# ─── RANDOM POOL ──────────────────────────────────────────────────────────────

RANDOM_POOL: dict[str, list[str]] = {
    "portrait":     [
        "a young woman with silver hair in a neon-lit alley at night",
        "an elderly man with weathered face and deep eyes, warm library light",
        "a teenage girl with freckles staring into rain-streaked window",
        "a warrior woman with battle scars, stoic expression, dusk light",
    ],
    "half_body":    [
        "a jazz musician mid-performance, blue club lights, motion blur on hands",
        "a street artist with spray cans, paint-stained jacket, rooftop",
        "a female scientist in a glowing lab, holding a luminescent vial",
        "a fisherman mending nets at dawn, harbor background",
    ],
    "full_body":    [
        "a swordsman standing at the edge of a cliff above storm clouds",
        "a dancer frozen mid-leap in an abandoned theater, dust particles",
        "a knight in ornate armor walking through a misty forest",
        "a girl in a summer dress running through a wheat field at golden hour",
    ],
    "landscape":    [
        "volcanic coastline at sunset, black sand, sea foam, dramatic clouds",
        "misty mountain valley at dawn, pine forest, golden light shafts",
        "frozen tundra under aurora borealis, vast open sky",
        "desert dunes at blue hour, long shadows, endless horizon",
    ],
    "urban":        [
        "rainy Tokyo alley at night, neon reflections, vending machines",
        "New York fire escape at golden hour, laundry, pigeons",
        "wet cobblestone street in Prague at dusk, lanterns glowing",
        "Hong Kong night market, crowded, steam, neon signs",
    ],
    "interior":     [
        "a Victorian study with leather chairs, fireplace, globe, dim amber light",
        "a cozy Tokyo ramen shop at night, steam, worn wooden counter",
        "a cathedral interior with stained glass, morning light rays",
        "an abandoned greenhouse, overgrown plants, cracked glass roof",
    ],
    "architecture": [
        "a Gothic cathedral exterior in heavy fog, dawn light on stone",
        "brutalist concrete apartment block at golden hour, long shadows",
        "a suspension bridge in rain, city lights reflecting on water",
        "ancient Roman ruins at dusk, warm stone, dramatic sky",
    ],
    "macro":        [
        "a dewdrop on a spider web with city lights reflected inside",
        "eye of a morpho butterfly, iridescent scales in sunlight",
        "old compass rose on aged parchment, extreme detail",
        "frost crystals on a window forming intricate geometric patterns",
    ],
    "animal":       [
        "a snow leopard crouching on a Himalayan ridge in blizzard light",
        "a fox kit peering from a burrow entrance at dawn",
        "a barn owl in flight, spread wings, moonlight forest",
        "a wolf howling on a cliff under the northern lights",
    ],
    "product":      [
        "a high-end mechanical watch on dark slate, macro details",
        "a luxury perfume bottle with soft studio light, bokeh background",
        "a handcrafted leather journal on aged oak table",
        "a ceramic tea bowl with imperfect glaze, morning light",
    ],
    "concept":      [
        "a lone wanderer discovering a vast mechanical heart buried in a glacier",
        "a lighthouse keeper who collects lost ships in glass bottles",
        "gravity reversed in a crumbling city, debris floating upward",
        "a library where the books are made of pressed light",
    ],
    "manual":       [
        "a solarpunk village in the canopy of a megaforest at golden hour",
        "a floating island monastery above clouds, rope bridges, waterfalls",
        "a futuristic greenhouse on Mars, warm golden light, astronaut tending plants",
        "ancient map room, explorer studying glowing cartography, candlelight",
    ],
}

RANDOM_SCENES = list(SCENES.keys())
RANDOM_LIGHTINGS = [k for k in LIGHTINGS if k != ""]
RANDOM_STYLES = list(STYLES.keys())
RANDOM_MOODS = [k for k in MOODS if k != ""]
RANDOM_GENRES = [k for k in GENRES if k != ""]
