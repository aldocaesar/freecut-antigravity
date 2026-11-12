"""
Editorial Engine & Workspace v2 Pre-Warmer for FreeCut (walterlow/freecut Schema v15)
=====================================================================================
Provides:
1. Curated editorial typography palettes, inline/stacked multi-span highlights (`textSpans`),
   and GPU glyph-atlas `textMotion` animations matching `walterlow/freecut`.
2. Handcrafted randomized Pillow image framing (8 distinct physical/editorial frame styles
   with anti-repetition, organic paper grain, sprockets, masking tape, chamfered corners,
   stacked prints, double mats, and frosted glass bevels).
3. Analytical procedural `motionModifiers`, spring/bezier card entrances, native `ShapeItem`
   editorial accents, and film-stock LUT adjustment layers.
4. Instant-load Workspace v2 cache pre-generation (`thumbnail.jpg`, 1fps `cache/filmstrip/`
   v2 frames + `meta.json`, and binary `WFORM` v1 `cache/waveform/multi-res.bin`).
"""

from __future__ import annotations

import array
import concurrent.futures
import glob
import hashlib
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

CANVAS_W = 1920
CANVAS_H = 1080
FPS = 30

# Exact constants from walterlow/freecut/src/features/timeline/constants.ts
# MAX_TRACK_HEIGHT (140) - CLIP_LABEL_ROW_HEIGHT (24) = 116; round(116 * 16 / 9) = 206
FILMSTRIP_EXTRACT_HEIGHT = 116
FILMSTRIP_EXTRACT_WIDTH = 206
WAVEFORM_LEVELS = (500, 100, 25, 10)

# Exact font catalog & weight support from walterlow/freecut/src/shared/typography/font-catalog.ts
SINGLE_WEIGHT_FONTS = {
    "Anton",
    "Archivo Black",
    "Bebas Neue",
    "Bungee",
    "Changa One",
    "DM Serif Display",
    "Fjalla One",
    "Gravitas One",
    "Alfa Slab One",
    "Pacifico",
    "Lobster",
    "Share Tech",
    "Abel",
    "Satisfy",
    "Shadows Into Light",
}

FREECUT_VALID_FONTS = {
    "Inter", "Inter Tight", "Plus Jakarta Sans", "Bricolage Grotesque", "Space Grotesk",
    "Sora", "Urbanist", "Outfit", "Manrope", "DM Sans", "Work Sans", "Rubik", "Archivo",
    "Archivo Black", "Bebas Neue", "Anton", "Oswald", "Barlow", "Barlow Condensed",
    "Barlow Semi Condensed", "Playfair Display", "DM Serif Display", "Cormorant Garamond",
    "Lora", "Libre Baskerville", "EB Garamond", "Merriweather", "Crimson Text", "Bitter",
    "Source Serif 4", "PT Serif", "Domine", "Arvo", "IBM Plex Sans", "Source Sans 3",
    "Source Code Pro", "Inconsolata", "Montserrat", "Poppins", "Raleway", "Nunito",
    "Nunito Sans", "Figtree", "Fira Sans", "Jost", "Libre Franklin", "Public Sans",
    "Schibsted Grotesk", "Red Hat Display", "Lexend", "Lexend Deca", "Rajdhani", "Teko",
    "Orbitron", "Kanit", "Fjalla One", "Cairo", "Tajawal", "Almarai", "Noto Sans Arabic",
    "Caveat", "Shadows Into Light", "PT Sans", "PT Sans Narrow", "Roboto", "Open Sans",
}

VALID_FONT_WEIGHTS = ("normal", "medium", "semibold", "bold")

TEXT_MOTION_IN_PRESETS = (
    "typewriter",
    "fade-up",
    "rise",
    "cascade",
    "pop",
    "blur-in",
    "slide-mask",
    "wave-in",
)

TEXT_MOTION_OUT_PRESETS = (
    "fade-down",
    "sink",
    "pop-out",
    "blur-out",
    "typewriter-erase",
)

# ── 1. Curated Cohesive Editorial Typography Palettes ─────────────────────────

EDITORIAL_FONT_PALETTES: Dict[str, Dict[str, Any]] = {
    "editorial_documentary": {
        "name": "Editorial Documentary",
        "body_font": "Inter Tight",
        "body_weight": "bold",
        "display_font": "Oswald",
        "display_weight": "bold",
        "serif_font": "Playfair Display",
        "serif_weight": "semibold",
        "body_tracking": -0.6,
        "display_tracking": 1.6,
        "accents": ["#FBBF24", "#FDE68A", "#FB7185", "#38BDF8"],
        "pill_bg": "rgba(10, 12, 18, 0.72)",
        "lut_presets": ["kodak-2383-d65", "warm-film", "cinematic"],
    },
    "modern_grotesk": {
        "name": "Modern Grotesk Essay",
        "body_font": "Space Grotesk",
        "body_weight": "bold",
        "display_font": "Archivo Black",
        "display_weight": "normal",
        "serif_font": "DM Serif Display",
        "serif_weight": "normal",
        "body_tracking": -0.8,
        "display_tracking": 0.8,
        "accents": ["#38BDF8", "#34D399", "#FACC15", "#F472B6"],
        "pill_bg": "rgba(9, 13, 22, 0.74)",
        "lut_presets": ["cinematic", "cool-film", "teal-orange"],
    },
    "pop_cinema": {
        "name": "Pop & Cinema Dynamic",
        "body_font": "Bricolage Grotesque",
        "body_weight": "bold",
        "display_font": "Bebas Neue",
        "display_weight": "normal",
        "serif_font": "Sora",
        "serif_weight": "bold",
        "body_tracking": -0.5,
        "display_tracking": 2.2,
        "accents": ["#FACC15", "#FB7185", "#22D3EE", "#A78BFA"],
        "pill_bg": "rgba(12, 10, 20, 0.72)",
        "lut_presets": ["teal-orange", "fuji-3513-d65", "cinematic"],
    },
    "investigative_press": {
        "name": "Investigative Dossier",
        "body_font": "Plus Jakarta Sans",
        "body_weight": "bold",
        "display_font": "Barlow Condensed",
        "display_weight": "bold",
        "serif_font": "Libre Baskerville",
        "serif_weight": "bold",
        "body_tracking": -0.4,
        "display_tracking": 1.8,
        "accents": ["#F87171", "#FBBF24", "#93C5FD", "#FDE047"],
        "pill_bg": "rgba(12, 14, 18, 0.76)",
        "lut_presets": ["kodak-2383-d60", "bleach-bypass", "cinematic"],
    },
    "literary_chronicle": {
        "name": "Literary & Historical Chronicle",
        "body_font": "Manrope",
        "body_weight": "bold",
        "display_font": "Cormorant Garamond",
        "display_weight": "bold",
        "serif_font": "Lora",
        "serif_weight": "semibold",
        "body_tracking": -0.3,
        "display_tracking": 1.2,
        "accents": ["#FDE68A", "#FDBA74", "#FCA5A5", "#E2E8F0"],
        "pill_bg": "rgba(14, 12, 10, 0.72)",
        "lut_presets": ["warm-film", "fade-vintage", "kodak-2383-d55"],
    },
    "clean_swiss": {
        "name": "Clean Swiss Studio",
        "body_font": "Urbanist",
        "body_weight": "bold",
        "display_font": "Anton",
        "display_weight": "normal",
        "serif_font": "Playfair Display",
        "serif_weight": "semibold",
        "body_tracking": -0.4,
        "display_tracking": 1.8,
        "accents": ["#FCD34D", "#7DD3FC", "#FDA4AF", "#6EE7B7"],
        "pill_bg": "rgba(10, 10, 12, 0.70)",
        "lut_presets": ["fuji-3513-d65", "cinematic", "warm-film"],
    },
    "cyrillic_editorial": {
        "name": "Cyrillic Editorial",
        "body_font": "Rubik",
        "body_weight": "bold",
        "display_font": "Oswald",
        "display_weight": "bold",
        "serif_font": "PT Serif",
        "serif_weight": "bold",
        "body_tracking": -0.3,
        "display_tracking": 1.4,
        "accents": ["#FBBF24", "#F87171", "#38BDF8", "#FDE68A"],
        "pill_bg": "rgba(10, 12, 16, 0.72)",
        "lut_presets": ["kodak-2383-d65", "cinematic", "cool-film"],
    },
    "arabic_editorial": {
        "name": "Arabic Editorial",
        "body_font": "Tajawal",
        "body_weight": "bold",
        "display_font": "Cairo",
        "display_weight": "bold",
        "serif_font": "Almarai",
        "serif_weight": "bold",
        "body_tracking": 0.0,
        "display_tracking": 0.0,
        "accents": ["#FBBF24", "#38BDF8", "#FB7185", "#FDE68A"],
        "pill_bg": "rgba(10, 12, 16, 0.74)",
        "lut_presets": ["warm-film", "kodak-2383-d65", "cinematic"],
    },
}


def sanitize_font_and_weight(font_family: str, font_weight: str = "bold") -> Tuple[str, str]:
    """Ensures fontFamily exists in FreeCut's catalog and fontWeight is Zod-valid."""
    fam = font_family if font_family in FREECUT_VALID_FONTS else "Inter Tight"
    w_map = {
        "black": "bold",
        "extrabold": "bold",
        "heavy": "bold",
        "800": "bold",
        "900": "bold",
        "700": "bold",
        "600": "semibold",
        "500": "medium",
        "400": "normal",
        "regular": "normal",
    }
    w = w_map.get(str(font_weight).lower().strip(), str(font_weight).lower().strip())
    if w not in VALID_FONT_WEIGHTS:
        w = "bold"
    if fam in SINGLE_WEIGHT_FONTS:
        w = "normal"
    return fam, w


def select_project_typography_palette(
    project_seed: str,
    title: str = "",
    mode: str = "default",
    universe: str = "",
    sample_text: str = "",
    explicit_theme: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Selects ONE cohesive typography palette per project so fonts feel curated by a human editor."""
    if explicit_theme and explicit_theme in EDITORIAL_FONT_PALETTES:
        return explicit_theme, EDITORIAL_FONT_PALETTES[explicit_theme]

    if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", sample_text):
        return "arabic_editorial", EDITORIAL_FONT_PALETTES["arabic_editorial"]
    if re.search(r"[\u0400-\u04FF]", sample_text):
        return "cyrillic_editorial", EDITORIAL_FONT_PALETTES["cyrillic_editorial"]

    ctx = f"{title} {mode} {universe} {sample_text[:600]}".lower()
    rng = random.Random(hashlib.md5(f"{project_seed}_{title}_{universe}".encode("utf-8")).hexdigest())

    if mode == "pop" or any(k in ctx for k in ["anime", "manga", "pokemon", "luffy", "goku", "hogwarts", "marvel", "star wars", "filme", "serie", "game"]):
        candidates = ["pop_cinema", "modern_grotesk", "clean_swiss"]
    elif any(k in ctx for k in ["stf", "senador", "presidente", "ministro", "governo", "crime", "investig", "dossi", "processo", "policia", "guerra"]):
        candidates = ["investigative_press", "editorial_documentary", "clean_swiss"]
    elif any(k in ctx for k in ["história", "historia", "século", "seculo", "império", "imperio", "antigo", "filosofia", "livro", "era uma vez"]):
        candidates = ["literary_chronicle", "editorial_documentary"]
    elif any(k in ctx for k in ["ia", "inteligência", "tecnologia", "futuro", "ciência", "ciencia", "espaço", "dados", "algoritmo"]):
        candidates = ["modern_grotesk", "editorial_documentary", "clean_swiss"]
    else:
        candidates = [
            "editorial_documentary",
            "modern_grotesk",
            "pop_cinema",
            "investigative_press",
            "literary_chronicle",
            "clean_swiss",
        ]

    chosen_key = rng.choice(candidates)
    return chosen_key, EDITORIAL_FONT_PALETTES[chosen_key]


STOPWORDS_ACCENT = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "um", "uma",
    "uns", "umas", "o", "a", "os", "as", "e", "ou", "mas", "que", "se", "por",
    "para", "com", "sem", "sob", "sobre", "entre", "até", "ate", "como", "mais",
    "foi", "era", "são", "sao", "ser", "está", "esta", "estão", "tem", "tinha",
    "ele", "ela", "eles", "elas", "isso", "isto", "esse", "essa", "este", "esta",
    "the", "and", "for", "with", "that", "this", "from", "into", "was", "were",
    "are", "una", "del", "los", "las", "con", "por",
}

DRAMATIC_ACCENT_TRIGGERS = {
    "urgente", "exclusivo", "grave", "prisão", "denúncia", "operação", "provas",
    "revelação", "documento", "sigilo", "relatório", "verdade", "segredo", "nunca",
    "sempre", "impossível", "bilhões", "milhões", "morte", "vida", "fim", "início",
    "poder", "colapso", "vitória", "derrota", "histórico", "fatal", "decisão",
}


def build_editorial_spans(
    text: str,
    palette: Dict[str, Any],
    base_color: str,
    rng: random.Random,
    layout_style: str = "full_screen",
    is_light_bg: bool = False,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Constructs rich FreeCut `textSpans` + `spanLayout` for organic manual-editor typography:
    - For `text_only` multi-word dramatic cards: 2-tier `'stack'` layout (eyebrow + display punchline).
    - For regular 2-5 word chunks (~55% rate): `'inline'` keyword color/italic emphasis.
    """
    clean = text.strip()
    if not clean:
        return None, None

    words = clean.split()
    accents = palette.get("accents", ["#FBBF24", "#38BDF8", "#FB7185"])
    accent_color = "#B91C1C" if is_light_bg else rng.choice(accents)

    # 1. Dramatic `text_only` stacked title card (2-6 words -> small lead-in + big display hit)
    if layout_style == "text_only" and 2 <= len(words) <= 7:
        split_at = 1 if len(words) <= 3 else max(1, len(words) // 2)
        top_line = " ".join(words[:split_at]).upper()
        bot_line = " ".join(words[split_at:]).upper()
        body_font, body_weight = sanitize_font_and_weight(palette["body_font"], "semibold")
        disp_font, disp_weight = sanitize_font_and_weight(palette["display_font"], palette["display_weight"])
        return (
            [
                {
                    "text": top_line,
                    "fontFamily": body_font,
                    "fontWeight": body_weight,
                    "fontSize": rng.randint(30, 36),
                    "letterSpacing": 4.5,
                    "color": "#CBD5E1",
                },
                {
                    "text": bot_line,
                    "fontFamily": disp_font,
                    "fontWeight": disp_weight,
                    "fontSize": rng.randint(78, 96),
                    "letterSpacing": float(palette.get("display_tracking", 1.5)),
                    "color": accent_color if rng.random() < 0.65 else "#FFFFFF",
                },
            ],
            "stack",
        )

    # 2. Inline keyword accent on multi-word subtitle chunks
    if len(words) < 2 or len(words) > 6:
        return None, None

    # ~58% of multi-word chunks get a tasteful keyword highlight (human editors don't highlight every single line)
    has_number = any(re.search(r"\d", w) for w in words)
    has_trigger = any(re.sub(r"\W+", "", w).lower() in DRAMATIC_ACCENT_TRIGGERS for w in words)
    if not has_number and not has_trigger and rng.random() > 0.52:
        return None, None

    target_idx = -1
    for i, w in enumerate(words):
        w_bare = re.sub(r"\W+", "", w).lower()
        if re.search(r"\d", w) or w_bare in DRAMATIC_ACCENT_TRIGGERS:
            target_idx = i
            break

    if target_idx < 0:
        candidates = [
            (len(re.sub(r"\W+", "", w)), i)
            for i, w in enumerate(words)
            if re.sub(r"\W+", "", w).lower() not in STOPWORDS_ACCENT and len(re.sub(r"\W+", "", w)) >= 4
        ]
        if not candidates:
            return None, None
        candidates.sort(reverse=True)
        target_idx = candidates[0][1]

    spans: List[Dict[str, Any]] = []
    before = " ".join(words[:target_idx])
    focus = words[target_idx]
    after = " ".join(words[target_idx + 1 :])

    if before:
        spans.append({"text": before + " ", "color": base_color})

    focus_span: Dict[str, Any] = {"text": focus + (" " if after else ""), "color": accent_color}
    if rng.random() < 0.22 and not re.search(r"[\u0600-\u06FF]", focus):
        focus_span["fontStyle"] = "italic"
    if has_trigger and rng.random() < 0.20:
        focus_span["underline"] = True
    spans.append(focus_span)

    if after:
        spans.append({"text": after, "color": base_color})

    return spans, "inline"


def build_native_text_motion(
    entry_hint: str,
    exit_hint: str,
    dur_f: int,
    word_count: int,
    rng: random.Random,
    is_text_only: bool = False,
) -> Dict[str, Any]:
    """
    Builds a 100% `sanitizeTextMotion`-compliant `TextMotionSpec` for `walterlow/freecut`.
    """
    in_map = {
        "typewriter": "typewriter",
        "fade_in": "fade-up",
        "fade": "fade-up",
        "fade-up": "fade-up",
        "rise": "rise",
        "drop": "slide-mask",
        "slide_left": "slide-mask",
        "slide_right": "slide-mask",
        "slide-mask": "slide-mask",
        "cascade": "cascade",
        "pop": "pop",
        "blur": "blur-in",
        "blur-in": "blur-in",
        "wave-in": "wave-in",
    }
    out_map = {
        "fade_out": "fade-down",
        "fade": "fade-down",
        "fade-down": "fade-down",
        "sink": "sink",
        "drop": "sink",
        "rise": "fade-down",
        "pop": "pop-out",
        "pop-out": "pop-out",
        "blur": "blur-out",
        "blur-out": "blur-out",
    }

    in_preset = in_map.get(str(entry_hint).lower(), "fade-up")
    if in_preset not in TEXT_MOTION_IN_PRESETS:
        in_preset = "fade-up"

    out_preset = out_map.get(str(exit_hint).lower(), "fade-down")
    if out_preset not in TEXT_MOTION_OUT_PRESETS:
        out_preset = "fade-down"

    if is_text_only:
        in_dur = max(6, min(14, dur_f // 5))
        out_dur = max(6, min(12, dur_f // 6))
        unit = "word" if word_count > 1 else "character"
        stagger = 2 if unit == "word" else 1
        easing = "ease-out"
        order = "center" if rng.random() < 0.5 else "forward"
        intensity = round(rng.uniform(0.75, 1.0), 2)
    else:
        in_dur = max(3, min(8, dur_f // 4))
        out_dur = max(3, min(6, dur_f // 5))
        if in_preset in ("typewriter", "cascade"):
            unit = "character" if word_count <= 2 else "word"
            stagger = 1
        elif word_count == 1:
            unit = "whole-clip" if in_preset == "pop" else "character"
            stagger = 0 if unit == "whole-clip" else 1
        else:
            unit = "word"
            stagger = rng.choice([1, 2])
        easing = "overshoot" if in_preset == "pop" else "ease-out"
        order = "forward"
        intensity = round(rng.uniform(0.6, 0.9), 2)

    spec: Dict[str, Any] = {
        "in": {
            "presetId": in_preset,
            "durationFrames": int(in_dur),
            "staggerFrames": int(stagger),
            "intensity": float(intensity),
            "order": order,
            "easing": easing,
            "seed": int(rng.randint(1, 9999)),
            "unit": unit,
        }
    }
    if dur_f >= 14:
        spec["out"] = {
            "presetId": out_preset,
            "durationFrames": int(out_dur),
            "staggerFrames": 0,
            "intensity": 0.65,
            "order": "forward",
            "easing": "ease-in",
            "seed": int(rng.randint(1, 9999)),
            "unit": "whole-clip",
        }
    return spec


# ── 2. Handcrafted Multi-Style Pillow Image Frame Engine ─────────────────────

CARD_FRAME_STYLES: Tuple[str, ...] = (
    "polaroid_editorial",
    "torn_paper_scrapbook",
    "analog_film_35mm",
    "chamfer_dossier",
    "gallery_double_mat",
    "offset_stacked_print",
    "vintage_archival_stamp",
    "cinema_glass_bevel",
)


def select_card_frame_style(
    narration: str,
    query: str,
    mode: str,
    scene_idx: int,
    prev_styles: Sequence[str],
    rng: random.Random,
    explicit_style: str = "",
) -> str:
    """Chooses a contextual, non-repeating handcrafted frame style for card scenes."""
    if explicit_style and explicit_style in CARD_FRAME_STYLES:
        return explicit_style

    ctx = f"{narration} {query} {mode}".lower()
    weights: Dict[str, float] = {s: 1.0 for s in CARD_FRAME_STYLES}

    if any(k in ctx for k in ["documento", "processo", "dossie", "relatorio", "lei", "stf", "policia", "dados", "radar", "tech"]):
        weights["chamfer_dossier"] += 2.2
        weights["offset_stacked_print"] += 1.6
        weights["torn_paper_scrapbook"] += 1.2
    elif any(k in ctx for k in ["antigo", "história", "historia", "memória", "memoria", "carta", "passado", "filme", "cinema", "foto"]):
        weights["analog_film_35mm"] += 2.2
        weights["polaroid_editorial"] += 2.0
        weights["vintage_archival_stamp"] += 1.6
        weights["torn_paper_scrapbook"] += 1.3
    elif mode == "pop" or any(k in ctx for k in ["anime", "batalha", "herói", "poder", "game", "futuro"]):
        weights["cinema_glass_bevel"] += 2.0
        weights["chamfer_dossier"] += 1.5
        weights["offset_stacked_print"] += 1.5
        weights["analog_film_35mm"] += 1.2
    else:
        weights["polaroid_editorial"] += 0.6
        weights["gallery_double_mat"] += 0.7
        weights["offset_stacked_print"] += 0.6
        weights["cinema_glass_bevel"] += 0.5

    # Strict anti-repetition: zero chance of repeating the last 2 card styles
    recent = set(prev_styles[-2:]) if prev_styles else set()
    pool = [s for s in CARD_FRAME_STYLES if s not in recent] or list(CARD_FRAME_STYLES)
    pool_weights = [weights[s] for s in pool]
    return rng.choices(pool, weights=pool_weights, k=1)[0]


def _hex_to_rgb(hex_str: str, fallback: Tuple[int, int, int] = (251, 191, 36)) -> Tuple[int, int, int]:
    s = str(hex_str).strip().lstrip("#")
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    return fallback


def _make_paper_sheet(w: int, h: int, base_rgb: Tuple[int, int, int], grain_opacity: float = 0.05) -> Image.Image:
    """Fast C-accelerated subtle paper grain sheet using PIL.Image.effect_noise."""
    sheet = Image.new("RGB", (w, h), base_rgb)
    try:
        nw = max(16, w // 2)
        nh = max(16, h // 2)
        noise_l = Image.effect_noise((nw, nh), 22.0).resize((w, h), Image.Resampling.BILINEAR)
        noise_rgb = Image.merge("RGB", (noise_l, noise_l, noise_l))
        sheet = Image.blend(sheet, noise_rgb, grain_opacity)
    except Exception:
        pass
    return sheet.convert("RGBA")


def _polish_photo_rgba(img_rgba: Image.Image) -> Image.Image:
    """Applies gentle editorial micro-contrast and a soft corner vignette so scraped photos feel graded."""
    w, h = img_rgba.size
    rgb = img_rgba.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    rgb = ImageEnhance.Color(rgb).enhance(1.03)

    # Soft vignette via tiny blurred mask upscaled in C (runs in <1ms)
    vw, vh = 64, 64
    vig = Image.new("L", (vw, vh), 38)
    vdraw = ImageDraw.Draw(vig)
    vdraw.ellipse((6, 6, vw - 7, vh - 7), fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(10)).resize((w, h), Image.Resampling.BILINEAR)

    out = rgb.convert("RGBA")
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    out.paste(dark, (0, 0), mask=vig)
    out.putalpha(img_rgba.getchannel("A"))
    return out


def _compose_with_drop_shadow(
    card_rgba: Image.Image,
    pad: int = 72,
    offset: Tuple[int, int] = (0, 18),
    blur_radius: int = 26,
    shadow_alpha: int = 135,
) -> Image.Image:
    """Composites any arbitrary-shaped RGBA card (torn paper, sprockets, rotated stack) over a true alpha shadow."""
    cw, ch = card_rgba.size
    out_w = cw + 2 * pad
    out_h = ch + 2 * pad
    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))

    alpha = card_rgba.getchannel("A")
    shadow_mask = Image.new("L", (out_w, out_h), 0)
    scaled_alpha = alpha.point(lambda a: int(a * (shadow_alpha / 255.0)))
    shadow_mask.paste(scaled_alpha, (pad + offset[0], pad + offset[1]))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur_radius))

    canvas.paste((0, 0, 0, 255), (0, 0), mask=shadow_mask)
    canvas.paste(card_rgba, (pad, pad), mask=alpha)
    return canvas


def _build_torn_polygon(w: int, h: int, margin: int, amp: int, rng: random.Random) -> List[Tuple[int, int]]:
    """Generates a realistic multi-frequency jagged torn paper perimeter."""
    pts: List[Tuple[int, int]] = []
    step = 7
    # Top edge (left -> right)
    for x in range(margin, w - margin, step):
        jit = int(rng.uniform(-amp, amp) * 0.7 + rng.choice([-2, 0, 2]))
        pts.append((x, max(1, margin + jit)))
    # Right edge (top -> bottom)
    for y in range(margin, h - margin, step):
        jit = int(rng.uniform(-amp, amp) * 0.7 + rng.choice([-2, 0, 2]))
        pts.append((min(w - 2, w - margin + jit), y))
    # Bottom edge (right -> left)
    for x in range(w - margin, margin, -step):
        jit = int(rng.uniform(-amp, amp) * 0.8 + rng.choice([-3, 0, 3]))
        pts.append((x, min(h - 2, h - margin + jit)))
    # Left edge (bottom -> top)
    for y in range(h - margin, margin, -step):
        jit = int(rng.uniform(-amp, amp) * 0.7 + rng.choice([-2, 0, 2]))
        pts.append((max(1, margin + jit), y))
    return pts


def _make_masking_tape(length: int, thickness: int, rng: random.Random) -> Image.Image:
    """Creates a realistic semi-translucent warm masking tape strip with serrated torn ends."""
    tape = Image.new("RGBA", (length, thickness), (0, 0, 0, 0))
    mask = Image.new("L", (length, thickness), 0)
    mdraw = ImageDraw.Draw(mask)
    poly: List[Tuple[int, int]] = []
    # Serrated left end
    for y in range(0, thickness + 1, 5):
        poly.append((rng.randint(0, 6), min(thickness - 1, y)))
    # Bottom
    poly.append((length - 4, thickness - 1))
    # Serrated right end
    for y in range(thickness, -1, -5):
        poly.append((length - 1 - rng.randint(0, 6), max(0, y)))
    poly.append((4, 0))
    mdraw.polygon(poly, fill=208)

    body = _make_paper_sheet(length, thickness, (236, 224, 192), grain_opacity=0.07)
    bdraw = ImageDraw.Draw(body)
    bdraw.line([(4, 1), (length - 5, 1)], fill=(255, 252, 240, 230), width=1)
    bdraw.line([(4, thickness - 2), (length - 5, thickness - 2)], fill=(180, 165, 132, 190), width=1)
    tape.paste(body, (0, 0), mask=mask)
    return tape


def apply_handcrafted_card_frame(
    input_path: str,
    output_path: str,
    frame_style: str = "polaroid_editorial",
    accent_hex: str = "#FBBF24",
    seed: int = 42,
) -> bool:
    """
    Renders one of 8 handcrafted editorial frames onto `output_path` (RGBA PNG with organic shadow).
    Replaces rigid identical rounded-rectangle cards with tactile manual-editor variety.
    """
    try:
        raw_img = Image.open(input_path).convert("RGBA")
        orig_w, orig_h = raw_img.size
        aspect = orig_w / float(orig_h) if orig_h > 0 else 1.0

        max_dim = 940
        if aspect <= 1.0:
            pw = max(160, (int(max_dim * aspect) // 2) * 2)
            ph = max_dim
        else:
            pw = max_dim
            ph = max(160, (int(max_dim / aspect) // 2) * 2)

        photo = _polish_photo_rgba(raw_img.resize((pw, ph), Image.Resampling.LANCZOS))
        rng = random.Random(seed)
        accent_rgb = _hex_to_rgb(accent_hex)

        if frame_style == "polaroid_editorial":
            side_m = 28
            top_m = 28
            bot_m = rng.randint(76, 94)
            cw, ch = pw + 2 * side_m, ph + top_m + bot_m
            paper_tones = [(245, 240, 230), (242, 236, 224), (247, 244, 237)]
            sheet = _make_paper_sheet(cw, ch, rng.choice(paper_tones), grain_opacity=0.055)

            # Soft die-cut paper corner mask
            cmask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(cmask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=7, fill=255)
            sheet.putalpha(cmask)

            sheet.paste(photo, (side_m, top_m), mask=photo)
            draw = ImageDraw.Draw(sheet)
            # Subtle inner photo recess bevel
            draw.rectangle((side_m - 1, top_m - 1, side_m + pw, top_m + ph), outline=(32, 28, 24, 65), width=1)
            # Editorial rule + minimal registration marks on bottom chin
            rule_y = top_m + ph + (bot_m // 2)
            draw.line([(side_m + 2, rule_y), (cw - side_m - 36, rule_y)], fill=(120, 112, 102, 115), width=1)
            draw.rectangle(
                (cw - side_m - 22, rule_y - 4, cw - side_m - 14, rule_y + 4),
                fill=(*accent_rgb, 215),
            )
            draw.rectangle((cw - side_m - 8, rule_y - 4, cw - side_m - 2, rule_y + 4), fill=(90, 84, 76, 160))
            final = _compose_with_drop_shadow(sheet, pad=68, offset=(2, 18), blur_radius=26, shadow_alpha=145)

        elif frame_style == "torn_paper_scrapbook":
            pad_p = 30
            tape_headroom = 26
            cw, ch = pw + 2 * pad_p, ph + 2 * pad_p + tape_headroom
            card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

            paper_w, paper_h = cw, ch - tape_headroom
            outer_pts = _build_torn_polygon(paper_w, paper_h, margin=8, amp=6, rng=rng)
            inner_pts = _build_torn_polygon(paper_w, paper_h, margin=12, amp=4, rng=rng)

            # White fiber deckle outer layer
            fiber_sheet = _make_paper_sheet(paper_w, paper_h, (252, 250, 245), grain_opacity=0.04)
            fmask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(fmask).polygon(outer_pts, fill=255)
            fmask = fmask.filter(ImageFilter.GaussianBlur(0.8))
            fiber_sheet.putalpha(fmask)

            # Warm aged paper inner layer
            cream_sheet = _make_paper_sheet(paper_w, paper_h, (240, 233, 219), grain_opacity=0.065)
            cmask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(cmask).polygon(inner_pts, fill=255)
            cream_sheet.putalpha(cmask)

            paper_comp = Image.alpha_composite(fiber_sheet, cream_sheet)
            paper_comp.paste(photo, (pad_p, pad_p), mask=photo)
            ImageDraw.Draw(paper_comp).rectangle(
                (pad_p, pad_p, pad_p + pw - 1, pad_p + ph - 1),
                outline=(45, 38, 30, 50),
                width=1,
            )
            card.paste(paper_comp, (0, tape_headroom), mask=paper_comp)

            # Add 1 top-center OR 2 corner translucent masking tape strips
            if rng.random() < 0.55:
                tape = _make_masking_tape(rng.randint(170, 220), 40, rng)
                tape_rot = tape.rotate(rng.uniform(-6.5, 6.5), resample=Image.Resampling.BICUBIC, expand=True)
                tx = (cw - tape_rot.width) // 2 + rng.randint(-28, 28)
                ty = max(0, tape_headroom - 16)
                card.alpha_composite(tape_rot, (tx, ty))
            else:
                t1 = _make_masking_tape(145, 36, rng).rotate(34, resample=Image.Resampling.BICUBIC, expand=True)
                t2 = _make_masking_tape(145, 36, rng).rotate(32, resample=Image.Resampling.BICUBIC, expand=True)
                card.alpha_composite(t1, (6, tape_headroom - 10))
                card.alpha_composite(t2, (max(0, cw - t2.width - 8), max(0, ch - t2.height - 4)))

            final = _compose_with_drop_shadow(card, pad=64, offset=(3, 16), blur_radius=24, shadow_alpha=145)

        elif frame_style == "analog_film_35mm":
            horizontal_strip = aspect >= 0.95
            if horizontal_strip:
                rebate_tb, rebate_lr = 46, 22
            else:
                rebate_tb, rebate_lr = 22, 46
            cw, ch = pw + 2 * rebate_lr, ph + 2 * rebate_tb

            film = Image.new("RGBA", (cw, ch), (17, 18, 21, 255))
            rmask = Image.new("L", (cw, ch), 0)
            rdraw = ImageDraw.Draw(rmask)
            rdraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=10, fill=255)

            fdraw = ImageDraw.Draw(film)
            # Punch real transparent sprocket holes + subtle amber rebate ticks
            amber = (245, 158, 11, 145)
            if horizontal_strip:
                step_x = 42
                for sx in range(24, cw - 30, step_x):
                    for sy in (11, ch - 35):
                        rdraw.rounded_rectangle((sx, sy, sx + 18, sy + 24), radius=4, fill=0)
                        fdraw.rounded_rectangle((sx - 1, sy - 1, sx + 19, sy + 25), radius=4, outline=(255, 255, 255, 30), width=1)
                    if (sx // step_x) % 3 == 0:
                        fdraw.line([(sx + 25, ch - 14), (sx + 35, ch - 14)], fill=amber, width=2)
            else:
                step_y = 42
                for sy in range(24, ch - 30, step_y):
                    for sx in (11, cw - 35):
                        rdraw.rounded_rectangle((sx, sy, sx + 24, sy + 18), radius=4, fill=0)
                        fdraw.rounded_rectangle((sx - 1, sy - 1, sx + 25, sy + 19), radius=4, outline=(255, 255, 255, 30), width=1)
                    if (sy // step_y) % 3 == 0:
                        fdraw.line([(cw - 14, sy + 24), (cw - 14, sy + 34)], fill=amber, width=2)

            film.putalpha(rmask)
            film.paste(photo, (rebate_lr, rebate_tb), mask=photo)
            # Warm halation inner rim around exposure window
            ImageDraw.Draw(film).rectangle(
                (rebate_lr - 1, rebate_tb - 1, rebate_lr + pw, rebate_tb + ph),
                outline=(245, 158, 11, 95),
                width=1,
            )
            final = _compose_with_drop_shadow(film, pad=66, offset=(0, 18), blur_radius=26, shadow_alpha=155)

        elif frame_style == "chamfer_dossier":
            pad_m = 22
            cut = 30
            cw, ch = pw + 2 * pad_m, ph + 2 * pad_m
            diag_mode = rng.choice(["tl_br", "tr_bl", "all4"])

            def _chamfer_pts(x0: int, y0: int, x1: int, y1: int, c: int) -> List[Tuple[int, int]]:
                c_tl = c if diag_mode in ("tl_br", "all4") else 4
                c_tr = c if diag_mode in ("tr_bl", "all4") else 4
                c_br = c if diag_mode in ("tl_br", "all4") else 4
                c_bl = c if diag_mode in ("tr_bl", "all4") else 4
                return [
                    (x0 + c_tl, y0),
                    (x1 - c_tr, y0),
                    (x1, y0 + c_tr),
                    (x1, y1 - c_br),
                    (x1 - c_br, y1),
                    (x0 + c_bl, y1),
                    (x0, y1 - c_bl),
                    (x0, y0 + c_tl),
                ]

            mat = Image.new("RGBA", (cw, ch), (18, 21, 28, 248))
            mmask = Image.new("L", (cw, ch), 0)
            outer_poly = _chamfer_pts(0, 0, cw - 1, ch - 1, cut)
            ImageDraw.Draw(mmask).polygon(outer_poly, fill=255)
            mat.putalpha(mmask)

            # Clip photo to inner chamfer
            pmask = Image.new("L", (pw, ph), 0)
            inner_photo_poly = _chamfer_pts(0, 0, pw - 1, ph - 1, max(6, cut - 10))
            ImageDraw.Draw(pmask).polygon(inner_photo_poly, fill=255)
            clipped_photo = photo.copy()
            clipped_photo.putalpha(pmask)
            mat.paste(clipped_photo, (pad_m, pad_m), mask=clipped_photo)

            mdraw = ImageDraw.Draw(mat)
            mdraw.polygon(outer_poly, outline=(226, 232, 240, 145), width=2)
            inner_border_poly = _chamfer_pts(pad_m - 4, pad_m - 4, pad_m + pw + 3, pad_m + ph + 3, max(8, cut - 8))
            mdraw.polygon(inner_border_poly, outline=(*accent_rgb, 195), width=1)
            final = _compose_with_drop_shadow(mat, pad=66, offset=(0, 18), blur_radius=26, shadow_alpha=155)

        elif frame_style == "gallery_double_mat":
            frame_w = 10
            mat_w = 26
            total_m = frame_w + mat_w
            cw, ch = pw + 2 * total_m, ph + 2 * total_m

            gallery = Image.new("RGBA", (cw, ch), (24, 24, 27, 255))
            gmask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=5, fill=255)
            gallery.putalpha(gmask)

            gdraw = ImageDraw.Draw(gallery)
            # Dark museum passe-partout
            gdraw.rectangle((frame_w, frame_w, cw - frame_w - 1, ch - frame_w - 1), fill=(13, 14, 17, 255))
            # Outer champagne/gold fillet rule
            gdraw.rectangle((frame_w, frame_w, cw - frame_w - 1, ch - frame_w - 1), outline=(214, 199, 169, 155), width=1)
            gallery.paste(photo, (total_m, total_m), mask=photo)
            # Crisp cream inner bevel around photograph
            gdraw.rectangle(
                (total_m - 2, total_m - 2, total_m + pw + 1, total_m + ph + 1),
                outline=(237, 232, 220, 225),
                width=2,
            )
            final = _compose_with_drop_shadow(gallery, pad=68, offset=(0, 18), blur_radius=28, shadow_alpha=160)

        elif frame_style == "offset_stacked_print":
            border_p = 14
            front_w, front_h = pw + 2 * border_p, ph + 2 * border_p
            front = _make_paper_sheet(front_w, front_h, (246, 243, 236), grain_opacity=0.05)
            fmask = Image.new("L", (front_w, front_h), 0)
            ImageDraw.Draw(fmask).rounded_rectangle((0, 0, front_w - 1, front_h - 1), radius=6, fill=255)
            front.putalpha(fmask)
            front.paste(photo, (border_p, border_p), mask=photo)
            ImageDraw.Draw(front).rectangle(
                (border_p - 1, border_p - 1, border_p + pw, border_p + ph),
                outline=(30, 28, 25, 70),
                width=1,
            )

            # Secondary backing card tilted/offset underneath
            back_tones = [(217, 206, 184), (42, 48, 60), (*accent_rgb,)]
            chosen_back = rng.choice(back_tones)
            if chosen_back == accent_rgb:
                chosen_back = (
                    int(accent_rgb[0] * 0.78 + 30),
                    int(accent_rgb[1] * 0.78 + 30),
                    int(accent_rgb[2] * 0.78 + 30),
                )
            back = _make_paper_sheet(front_w, front_h, chosen_back, grain_opacity=0.05)
            back.putalpha(fmask)
            ImageDraw.Draw(back).rounded_rectangle(
                (0, 0, front_w - 1, front_h - 1),
                radius=6,
                outline=(255, 255, 255, 85),
                width=1,
            )
            tilt = rng.choice([-2.6, -2.0, 2.0, 2.6])
            back_rot = back.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True)

            off_x = rng.choice([-16, 16])
            off_y = 14
            comp_w = max(front_w, back_rot.width) + abs(off_x) + 24
            comp_h = max(front_h, back_rot.height) + off_y + 24
            stack = Image.new("RGBA", (comp_w, comp_h), (0, 0, 0, 0))

            bx = (comp_w - back_rot.width) // 2 + (off_x // 2)
            by = (comp_h - back_rot.height) // 2 + (off_y // 2)
            fx = (comp_w - front_w) // 2 - (off_x // 2)
            fy = (comp_h - front_h) // 2 - (off_y // 2)

            stack.alpha_composite(back_rot, (bx, by))
            # Soft contact shadow between top print and bottom print
            front_with_contact = _compose_with_drop_shadow(front, pad=16, offset=(0, 5), blur_radius=8, shadow_alpha=95)
            stack.alpha_composite(front_with_contact, (max(0, fx - 16), max(0, fy - 16)))
            final = _compose_with_drop_shadow(stack, pad=56, offset=(0, 18), blur_radius=26, shadow_alpha=145)

        elif frame_style == "vintage_archival_stamp":
            pad_s = 28
            cw, ch = pw + 2 * pad_s, ph + 2 * pad_s
            stamp = _make_paper_sheet(cw, ch, (239, 233, 216), grain_opacity=0.06)
            smask = Image.new("L", (cw, ch), 255)
            sdraw = ImageDraw.Draw(smask)

            if rng.random() < 0.5:
                # Perforated postage scallops around perimeter
                step = 28
                r = 7
                for x in range(18, cw - 12, step):
                    sdraw.ellipse((x - r, -r, x + r, r), fill=0)
                    sdraw.ellipse((x - r, ch - 1 - r, x + r, ch - 1 + r), fill=0)
                for y in range(18, ch - 12, step):
                    sdraw.ellipse((-r, y - r, r, y + r), fill=0)
                    sdraw.ellipse((cw - 1 - r, y - r, cw - 1 + r, y + r), fill=0)
            else:
                # Classic concave ticket/archival corner notches
                cr = 18
                for cx, cy in ((0, 0), (cw - 1, 0), (0, ch - 1), (cw - 1, ch - 1)):
                    sdraw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=0)

            stamp.putalpha(smask)
            stamp.paste(photo, (pad_s, pad_s), mask=photo)
            bdraw = ImageDraw.Draw(stamp)
            bdraw.rectangle(
                (pad_s - 6, pad_s - 6, pad_s + pw + 5, pad_s + ph + 5),
                outline=(72, 64, 54, 175),
                width=2,
            )
            bdraw.rectangle(
                (pad_s - 2, pad_s - 2, pad_s + pw + 1, pad_s + ph + 1),
                outline=(72, 64, 54, 110),
                width=1,
            )
            final = _compose_with_drop_shadow(stamp, pad=66, offset=(2, 18), blur_radius=26, shadow_alpha=150)

        else:  # cinema_glass_bevel
            rim = 20
            outer_r = rng.randint(28, 36)
            inner_r = max(14, outer_r - 10)
            cw, ch = pw + 2 * rim, ph + 2 * rim

            # Smoked frosted glass rim sampled from the image's own colors
            glass_bg = photo.resize((cw, ch), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(24))
            tint = Image.new("RGBA", (cw, ch), (18, 20, 26, 155))
            glass = Image.alpha_composite(glass_bg, tint)

            gmask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=outer_r, fill=238)
            glass.putalpha(gmask)

            pmask = Image.new("L", (pw, ph), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=inner_r, fill=255)
            p_rounded = photo.copy()
            p_rounded.putalpha(pmask)
            glass.paste(p_rounded, (rim, rim), mask=p_rounded)

            # Directional specular highlight (brighter top-left, softer bottom-right)
            gdraw = ImageDraw.Draw(glass)
            gdraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=outer_r, outline=(255, 255, 255, 150), width=2)
            gdraw.rounded_rectangle(
                (rim - 1, rim - 1, rim + pw, rim + ph),
                radius=inner_r,
                outline=(255, 255, 255, 75),
                width=1,
            )
            final = _compose_with_drop_shadow(glass, pad=68, offset=(0, 18), blur_radius=28, shadow_alpha=155)

        final.save(output_path, "PNG")
        return True
    except Exception as exc:
        print(f"      [Editorial Frame Error] {os.path.basename(input_path)} ({frame_style}): {exc}")
        return False


def apply_editorial_fullscreen_framing(input_path: str, output_path: str, seed: int = 42) -> bool:
    """
    Formats full_screen images onto 1920x1080:
    - Native ~16:9 images get crisp full-bleed fit + subtle cinema polish.
    - Non-16:9 images (portrait, 4:3, square) keep 100% of the photo uncropped over a darkened
      atmospheric blur with randomized tasteful foreground framing (gallery mat, rounded bevel,
      subtle chamfer, or clean archival print).
    """
    try:
        img = Image.open(input_path).convert("RGBA")
        orig_w, orig_h = img.size
        aspect = orig_w / float(orig_h) if orig_h > 0 else 1.0

        if 1.68 <= aspect <= 1.88:
            fitted = ImageOps.fit(img, (CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
            polished = _polish_photo_rgba(fitted)
            polished.convert("RGB").save(output_path, "PNG")
            return True

        rng = random.Random(seed)
        # 1. Atmospheric blurred + darkened + vignetted background
        scale_bg = max(CANVAS_W / float(orig_w), CANVAS_H / float(orig_h))
        bg_w = int(orig_w * scale_bg) + 8
        bg_h = int(orig_h * scale_bg) + 8
        bg_resized = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        left = (bg_w - CANVAS_W) // 2
        top = (bg_h - CANVAS_H) // 2
        bg_cropped = bg_resized.crop((left, top, left + CANVAS_W, top + CANVAS_H))
        bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(44))
        dark_overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (6, 8, 12, 142))
        canvas = Image.alpha_composite(bg_blurred, dark_overlay)

        # 2. Foreground intact scaling
        max_fg_w, max_fg_h = 1700, 936
        scale_fg = min(max_fg_w / float(orig_w), max_fg_h / float(orig_h))
        fg_w = max(80, int(orig_w * scale_fg))
        fg_h = max(80, int(orig_h * scale_fg))
        fg_photo = _polish_photo_rgba(img.resize((fg_w, fg_h), Image.Resampling.LANCZOS))

        fg_variant = rng.choice(["rounded_bevel", "gallery_border", "warm_print", "crisp_cinema"])
        if fg_variant == "rounded_bevel":
            r = 18
            pmask = Image.new("L", (fg_w, fg_h), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, fg_w - 1, fg_h - 1), radius=r, fill=255)
            fg_photo.putalpha(pmask)
            ImageDraw.Draw(fg_photo).rounded_rectangle(
                (0, 0, fg_w - 1, fg_h - 1), radius=r, outline=(255, 255, 255, 95), width=2
            )
            framed_fg = fg_photo
        elif fg_variant == "gallery_border":
            m = 12
            gw, gh = fg_w + 2 * m, fg_h + 2 * m
            framed_fg = Image.new("RGBA", (gw, gh), (22, 23, 27, 255))
            framed_fg.paste(fg_photo, (m, m), mask=fg_photo)
            ImageDraw.Draw(framed_fg).rectangle((0, 0, gw - 1, gh - 1), outline=(228, 222, 210, 165), width=2)
        elif fg_variant == "warm_print":
            m = 10
            gw, gh = fg_w + 2 * m, fg_h + 2 * m
            framed_fg = _make_paper_sheet(gw, gh, (244, 239, 229), grain_opacity=0.05)
            pmask = Image.new("L", (gw, gh), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=6, fill=255)
            framed_fg.putalpha(pmask)
            framed_fg.paste(fg_photo, (m, m), mask=fg_photo)
        else:
            ImageDraw.Draw(fg_photo).rectangle((0, 0, fg_w - 1, fg_h - 1), outline=(255, 255, 255, 80), width=1)
            framed_fg = fg_photo

        lifted = _compose_with_drop_shadow(framed_fg, pad=44, offset=(0, 12), blur_radius=22, shadow_alpha=165)
        px = (CANVAS_W - lifted.width) // 2
        py = (CANVAS_H - lifted.height) // 2
        canvas.alpha_composite(lifted, (px, py))
        canvas.convert("RGB").save(output_path, "PNG")
        return True
    except Exception as exc:
        print(f"      [Fullscreen Framing Error] {os.path.basename(input_path)}: {exc}")
        return False


# ── 3. Analytical Motion Modifiers, Angles & Editorial Transitions ────────────

def normalize_angle_deg(angle: float) -> float:
    """Matches FreeCut normalize.ts `((rotation % 360) + 360) % 360` so normalization is clean."""
    val = ((float(angle) % 360.0) + 360.0) % 360.0
    return round(val, 2)


def build_card_motion_modifiers(sid: str, rng: random.Random) -> List[Dict[str, Any]]:
    """
    Returns clean FreeCut v2 procedural `MotionModifier` specs for organic 60fps floating/breathing
    without flooding the timeline dopesheet with sampled linear keyframes.
    """
    mods: List[Dict[str, Any]] = [
        {
            "version": 2,
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_mod_drift")),
            "type": "float-drift",
            "enabled": True,
            "amplitude": round(rng.uniform(0.38, 0.68), 2),
            "frequency": round(rng.uniform(0.18, 0.28), 2),
            "phaseFrames": rng.randint(0, 90),
            "seed": rng.randint(1, 9999),
            "channelGains": {"x": 0.85, "y": 1.0, "rotation": 0.55},
        }
    ]
    if rng.random() < 0.45:
        mods.append(
            {
                "version": 2,
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_mod_breath")),
                "type": "breath-pulse",
                "enabled": True,
                "amplitude": round(rng.uniform(0.22, 0.42), 2),
                "frequency": round(rng.uniform(0.16, 0.24), 2),
                "phaseFrames": rng.randint(0, 90),
                "seed": rng.randint(1, 9999),
                "channelGains": {"width": 1.0, "height": 1.0, "opacity": 0.0},
            }
        )
    return mods


def build_fullscreen_motion_modifiers(sid: str, rng: random.Random) -> List[Dict[str, Any]]:
    """Subtle handheld operator feel on ~35% of full_screen shots."""
    if rng.random() > 0.38:
        return []
    if rng.random() < 0.7:
        return [
            {
                "version": 2,
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_fs_drift")),
                "type": "float-drift",
                "enabled": True,
                "amplitude": round(rng.uniform(0.18, 0.30), 2),
                "frequency": round(rng.uniform(0.14, 0.22), 2),
                "phaseFrames": rng.randint(0, 90),
                "seed": rng.randint(1, 9999),
                "channelGains": {"x": 0.7, "y": 0.7, "rotation": 0.2},
            }
        ]
    return [
        {
            "version": 2,
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_fs_handheld")),
            "type": "micro-shake",
            "enabled": True,
            "amplitude": round(rng.uniform(0.10, 0.18), 2),
            "frequency": round(rng.uniform(1.8, 2.8), 2),
            "phaseFrames": rng.randint(0, 60),
            "seed": rng.randint(1, 9999),
            "channelGains": {"x": 0.8, "y": 0.8, "rotation": 0.25},
        }
    ]


def select_editorial_transition(
    left_label: str,
    right_label: str,
    scene_hint: str,
    prev_preset: Optional[str],
    rng: random.Random,
) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Selects organic editorial transitions between full_screen / text_only clips.
    Mixes ~28% clean hard cuts (like real manual editors!) with ~72% tasteful film/editorial transitions.
    """
    is_text_bridge = "text_only" in left_label or "text_only" in right_label or "_bg" in left_label or "_bg" in right_label
    if is_text_bridge:
        return ("dissolve", rng.randint(12, 16), None)

    valid_explicit = {
        "dissolve", "blurDissolve", "additiveDissolve", "dipToColorDissolve",
        "filmGateSlip", "lightLeakBurn", "lensWarpZoom", "slide", "wipe", "smoothCut", "fade",
    }
    if scene_hint in valid_explicit and scene_hint != prev_preset and rng.random() < 0.65:
        preset = scene_hint
    else:
        # ~25% crisp manual hard cuts so the edit breathes and isn't 100% mushy dissolves
        if rng.random() < 0.25:
            return None
        weighted_pool = [
            ("dissolve", 24),
            ("blurDissolve", 18),
            ("filmGateSlip", 14),
            ("lightLeakBurn", 12),
            ("smoothCut", 10),
            ("dipToColorDissolve", 8),
            ("additiveDissolve", 6),
            ("slide", 4),
            ("wipe", 4),
        ]
        filtered = [(p, w) for p, w in weighted_pool if p != prev_preset]
        preset = rng.choices([p for p, _ in filtered], weights=[w for _, w in filtered], k=1)[0]

    dur = rng.randint(10, 16)
    direction = rng.choice(["from-left", "from-right", "from-top", "from-bottom"]) if preset in ("wipe", "slide") else None
    return (preset, dur, direction)


# ── 4. Instant-Load Workspace v2 Cache Pre-Generation ─────────────────────────

def fit_filmstrip_size(
    src_w: int,
    src_h: int,
    max_w: int = FILMSTRIP_EXTRACT_WIDTH,
    max_h: int = FILMSTRIP_EXTRACT_HEIGHT,
) -> Tuple[int, int]:
    """Exact port of walterlow/freecut fitFilmstripFrameSize."""
    if src_w <= 0 or src_h <= 0:
        return (max_w, max_h)
    scale = min(max_w / float(src_w), max_h / float(src_h))
    return (max(2, int(round(src_w * scale))), max(2, int(round(src_h * scale))))


def generate_media_thumbnail_jpg(src_path: str, mime_type: str, dest_jpg_path: str) -> bool:
    """Generates a fast 320px `thumbnail.jpg` for instant Media Library & Timeline hydration."""
    try:
        if mime_type.startswith("image/"):
            with Image.open(src_path) as im:
                im_rgba = im.convert("RGBA")
                im_rgba.thumbnail((320, 320), Image.Resampling.BILINEAR)
                bg = Image.new("RGB", im_rgba.size, (10, 10, 12))
                bg.paste(im_rgba, (0, 0), mask=im_rgba.getchannel("A"))
                bg.save(dest_jpg_path, "JPEG", quality=80)
            return os.path.isfile(dest_jpg_path) and os.path.getsize(dest_jpg_path) > 0

        if mime_type.startswith("video/"):
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-ss", "0.2",
                "-i", src_path,
                "-frames:v", "1",
                "-vf", "scale=320:-2",
                "-q:v", "6",
                dest_jpg_path,
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if not os.path.isfile(dest_jpg_path) or os.path.getsize(dest_jpg_path) == 0:
                # Retry at 0.0s for very short clips
                cmd[4] = "0"
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            return os.path.isfile(dest_jpg_path) and os.path.getsize(dest_jpg_path) > 0
    except Exception:
        pass
    return False


def generate_video_filmstrip_cache(
    video_path: str,
    src_w: int,
    src_h: int,
    duration_s: float,
    filmstrip_dir: str,
) -> Optional[str]:
    """
    Pre-extracts 1fps JPEG filmstrip frames + `meta.json` (Schema v2) inside
    `media/{id}/cache/filmstrip/` so FreeCut opens the timeline with ZERO WebCodecs worker lag.
    Returns path to frame `0.jpg` if extracted so it can double as `thumbnail.jpg`.
    """
    try:
        os.makedirs(filmstrip_dir, exist_ok=True)
        fw, fh = fit_filmstrip_size(src_w, src_h)
        # Cap pre-extracted frames on ultra-long background loops (e.g. 30-min ambient MP4s)
        max_extract_s = min(max(1.0, duration_s), 180.0)
        out_pattern = os.path.join(filmstrip_dir, "%d.jpg")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-t", f"{max_extract_s:.2f}",
            "-i", video_path,
            "-vf", f"fps=1,scale={fw}:{fh}",
            "-q:v", "7",
            "-start_number", "0",
            out_pattern,
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=35)
        jpgs = [
            f for f in os.listdir(filmstrip_dir)
            if f.endswith(".jpg") and os.path.getsize(os.path.join(filmstrip_dir, f)) > 0
        ]
        if not jpgs:
            return None

        meta = {
            "version": 2,
            "width": fw,
            "height": fh,
            "isComplete": True,
            "frameCount": len(jpgs),
        }
        with open(os.path.join(filmstrip_dir, "meta.json"), "w", encoding="utf-8") as mf:
            json.dump(meta, mf, separators=(",", ":"))

        zero_jpg = os.path.join(filmstrip_dir, "0.jpg")
        return zero_jpg if os.path.isfile(zero_jpg) else os.path.join(filmstrip_dir, sorted(jpgs)[0])
    except Exception:
        return None


def generate_waveform_multires_bin(audio_path: str, duration_s: float, dest_bin_path: str) -> bool:
    """
    Generates a byte-exact FreeCut `WFORM` v1 multi-resolution waveform cache file
    (`media/{id}/cache/waveform/multi-res.bin`) with levels [500, 100, 25, 10] Hz.
    Eliminates full-file browser audio decoding on timeline open.
    """
    try:
        dur = max(0.05, float(duration_s))
        decode_rate = 4000  # Exact 8x multiple of top level 500 Hz -> 8 int16 samples per bin!
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", audio_path,
            "-ac", "1",
            "-ar", str(decode_rate),
            "-f", "s16le",
            "pipe:1",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        raw = res.stdout
        if not raw:
            return False

        # Ensure even byte count for int16
        if len(raw) % 2 != 0:
            raw = raw[:-1]
        pcm = array.array("h")
        pcm.frombytes(raw)
        if os.sys.byteorder != "little":
            pcm.byteswap()

        total_pcm = len(pcm)
        if total_pcm == 0:
            return False

        # Level 0: 500 samples/sec (each bin = 8 samples at 4000 Hz)
        base_rate = WAVEFORM_LEVELS[0]  # 500
        n0 = max(1, int(math.ceil(dur * base_rate)))
        peaks_500 = array.array("f", [0.0]) * n0
        inv_max = 1.0 / 32768.0
        step = decode_rate // base_rate  # 8

        limit_bins = min(n0, (total_pcm + step - 1) // step)
        for i in range(limit_bins):
            s0 = i * step
            chunk = pcm[s0 : s0 + step]
            if chunk:
                hi = max(abs(min(chunk)), abs(max(chunk)))
                val = hi * inv_max
                peaks_500[i] = 1.0 if val > 1.0 else val

        levels_data: List[Tuple[int, array.array]] = [(base_rate, peaks_500)]
        for target_rate in WAVEFORM_LEVELS[1:]:
            num_samples = max(1, int(math.ceil(dur * target_rate)))
            ratio = base_rate / float(target_rate)
            down = array.array("f", [0.0]) * num_samples
            for i in range(num_samples):
                start_idx = int(i * ratio)
                end_idx = min(int((i + 1) * ratio), n0)
                if end_idx > start_idx:
                    down[i] = max(peaks_500[start_idx:end_idx])
            levels_data.append((target_rate, down))

        # Write WFORM v1 binary:
        # Header (48B): "WFORM" (5B) + uint8(1) + float32le(dur) + uint8(1 ch) + uint8(4 levels) + 36B reserved
        header_size = 48
        level_index_size = 12
        level_count = len(levels_data)
        data_offset_start = header_size + level_count * level_index_size

        header = bytearray(header_size)
        header[0:5] = b"WFORM"
        struct.pack_into("<BfBB", header, 5, 1, dur, 1, level_count)

        index_buf = bytearray(level_count * level_index_size)
        curr_offset = data_offset_start
        payload_chunks: List[bytes] = []

        for idx, (sr, flt_arr) in enumerate(levels_data):
            if os.sys.byteorder != "little":
                flt_copy = array.array("f", flt_arr)
                flt_copy.byteswap()
                raw_floats = flt_copy.tobytes()
            else:
                raw_floats = flt_arr.tobytes()
            sample_count = len(flt_arr)
            struct.pack_into("<HIIH", index_buf, idx * level_index_size, sr, sample_count, curr_offset, 0)
            payload_chunks.append(raw_floats)
            curr_offset += len(raw_floats)

        os.makedirs(os.path.dirname(dest_bin_path), exist_ok=True)
        with open(dest_bin_path, "wb") as bf:
            bf.write(header)
            bf.write(index_buf)
            for ch_bytes in payload_chunks:
                bf.write(ch_bytes)

        return os.path.isfile(dest_bin_path) and os.path.getsize(dest_bin_path) > header_size
    except Exception as exc:
        print(f"      [Waveform Cache Warning] {os.path.basename(audio_path)}: {exc}")
        return False


def generate_project_cover_bytes(first_media_path: Optional[str], mime_type: str = "") -> Optional[bytes]:
    """Creates a clean 320x180 JPEG cover buffer for both `.freecut.zip` and `projects/{id}/thumbnail.jpg`."""
    try:
        if first_media_path and os.path.isfile(first_media_path):
            if mime_type.startswith("image/") or first_media_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                with Image.open(first_media_path) as im:
                    rgba = im.convert("RGBA")
                    bg = Image.new("RGB", rgba.size, (0, 0, 0))
                    bg.paste(rgba, (0, 0), mask=rgba.getchannel("A"))
                    cover = ImageOps.fit(bg, (320, 180), Image.Resampling.BILINEAR)
                    import io
                    buf = io.BytesIO()
                    cover.save(buf, "JPEG", quality=82)
                    return buf.getvalue()
            elif mime_type.startswith("video/") or first_media_path.lower().endswith((".mp4", ".webm", ".mov")):
                cmd = [
                    "ffmpeg", "-v", "error", "-ss", "0.3", "-i", first_media_path,
                    "-frames:v", "1", "-vf", "scale=320:180:force_original_aspect_ratio=increase,crop=320:180",
                    "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
                if res.stdout:
                    return res.stdout
    except Exception:
        pass
    return None


def prewarm_workspace_media_caches(
    workspace_dir: str,
    manifest_media: Sequence[Dict[str, Any]],
    media_id_to_filepath: Dict[str, str],
) -> Dict[str, bool]:
    """
    Populates `thumbnail.jpg`, `cache/filmstrip/`, and `cache/waveform/multi-res.bin` in parallel
    for every media item in `freecut_workspace/media/{id}/`.
    Returns `{media_id: has_thumbnail}` so `metadata.json` can reference `thumbnailId`.
    """
    thumb_ok: Dict[str, bool] = {}

    def _warm_one(entry: Dict[str, Any]) -> Tuple[str, bool]:
        media_id = entry["originalId"]
        mime = entry.get("mimeType", "")
        meta = entry.get("metadata", {})
        dur = float(meta.get("duration") or 0.0)
        w = int(meta.get("width") or 0)
        h = int(meta.get("height") or 0)
        media_dir = os.path.join(workspace_dir, "media", media_id)
        src_path = media_id_to_filepath.get(media_id) or os.path.join(media_dir, entry["fileName"])
        if not os.path.isfile(src_path):
            return (media_id, False)

        thumb_path = os.path.join(media_dir, "thumbnail.jpg")
        has_thumb = False

        if mime.startswith("video/"):
            fs_dir = os.path.join(media_dir, "cache", "filmstrip")
            frame0 = generate_video_filmstrip_cache(src_path, w, h, dur, fs_dir)
            if frame0 and os.path.isfile(frame0):
                shutil.copy2(frame0, thumb_path)
                has_thumb = True
            else:
                has_thumb = generate_media_thumbnail_jpg(src_path, mime, thumb_path)
        elif mime.startswith("image/"):
            has_thumb = generate_media_thumbnail_jpg(src_path, mime, thumb_path)
        elif mime.startswith("audio/"):
            wf_path = os.path.join(media_dir, "cache", "waveform", "multi-res.bin")
            generate_waveform_multires_bin(src_path, dur, wf_path)

        return (media_id, has_thumb)

    workers = min(6, max(2, os.cpu_count() or 4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for mid, ok in pool.map(_warm_one, manifest_media):
            thumb_ok[mid] = ok

    return thumb_ok
