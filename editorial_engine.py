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
   editorial accents, and real WebGPU film-stock color grading (`gpu-color-wheels` + `gpu-grain`).
4. Instant-load Workspace v2 cache pre-generation (`thumbnail.jpg`, exact `buildTargetIndices`
   `cache/filmstrip/` v2 frames + `meta.json`, and dual `WaveformMeta`/`WaveformBin` + `WFORM` v1
   `cache/waveform/` caches).
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


def ensure_ffmpeg_on_path() -> None:
    """Ensures WinGet / standard Windows FFmpeg + FFprobe binaries are on PATH even on standalone imports."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    local_app = os.environ.get("LOCALAPPDATA", "")
    for pat in (
        os.path.join(local_app, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ):
        matches = glob.glob(pat, recursive=True)
        if matches:
            os.environ["PATH"] = os.path.dirname(matches[0]) + os.pathsep + os.environ.get("PATH", "")
            return


ensure_ffmpeg_on_path()

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

# ── 1. Curated Cohesive Editorial Typography & Native GPU Film-Grade Palettes ──

# Exact WebGPU `gpu-color-wheels` presets matching walterlow/freecut/src/infrastructure/gpu-effects/effects/color.ts
EDITORIAL_GPU_COLOR_GRADES: Dict[str, Dict[str, float]] = {
    "kodak_2383_warm": {
        "shadowsHue": 218, "shadowsAmount": 0.12,
        "midtonesHue": 34, "midtonesAmount": 0.06,
        "highlightsHue": 44, "highlightsAmount": 0.14,
        "temperature": 8, "tint": 2, "saturation": 6,
        "exposure": 0.02, "contrast": 1.08, "pivot": 0.48,
        "lift": 0.0, "gamma": 1.02, "gain": 1.01, "offset": 0.0,
        "blackPoint": 0.005, "whitePoint": 0.995,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 6, "colorBoost": 8,
        "shadows": -3, "highlights": 2, "hue": 50, "lumMix": 100,
    },
    "fuji_3513_eterna": {
        "shadowsHue": 196, "shadowsAmount": 0.14,
        "midtonesHue": 168, "midtonesAmount": 0.04,
        "highlightsHue": 48, "highlightsAmount": 0.10,
        "temperature": -3, "tint": -2, "saturation": 4,
        "exposure": 0.0, "contrast": 1.06, "pivot": 0.5,
        "lift": 0.005, "gamma": 1.03, "gain": 1.0, "offset": 0.0,
        "blackPoint": 0.0, "whitePoint": 0.99,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 4, "colorBoost": 6,
        "shadows": 2, "highlights": -2, "hue": 50, "lumMix": 100,
    },
    "cinema_teal_amber": {
        "shadowsHue": 204, "shadowsAmount": 0.18,
        "midtonesHue": 28, "midtonesAmount": 0.05,
        "highlightsHue": 36, "highlightsAmount": 0.16,
        "temperature": 4, "tint": 0, "saturation": 8,
        "exposure": 0.0, "contrast": 1.10, "pivot": 0.47,
        "lift": 0.0, "gamma": 1.0, "gain": 1.02, "offset": 0.0,
        "blackPoint": 0.005, "whitePoint": 1.0,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 8, "colorBoost": 10,
        "shadows": -4, "highlights": 3, "hue": 50, "lumMix": 100,
    },
    "archival_dossier": {
        "shadowsHue": 222, "shadowsAmount": 0.10,
        "midtonesHue": 42, "midtonesAmount": 0.05,
        "highlightsHue": 50, "highlightsAmount": 0.09,
        "temperature": -4, "tint": 1, "saturation": -12,
        "exposure": 0.0, "contrast": 1.12, "pivot": 0.5,
        "lift": 0.008, "gamma": 0.98, "gain": 1.0, "offset": 0.0,
        "blackPoint": 0.01, "whitePoint": 0.985,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 10, "colorBoost": 0,
        "shadows": -4, "highlights": -2, "hue": 50, "lumMix": 100,
    },
    "warm_chronicle": {
        "shadowsHue": 28, "shadowsAmount": 0.09,
        "midtonesHue": 36, "midtonesAmount": 0.08,
        "highlightsHue": 46, "highlightsAmount": 0.14,
        "temperature": 12, "tint": 3, "saturation": -4,
        "exposure": 0.02, "contrast": 1.05, "pivot": 0.5,
        "lift": 0.01, "gamma": 1.04, "gain": 1.0, "offset": 0.0,
        "blackPoint": 0.0, "whitePoint": 0.985,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 3, "colorBoost": 5,
        "shadows": 3, "highlights": -2, "hue": 50, "lumMix": 100,
    },
    "clean_studio": {
        "shadowsHue": 214, "shadowsAmount": 0.08,
        "midtonesHue": 0, "midtonesAmount": 0.0,
        "highlightsHue": 42, "highlightsAmount": 0.07,
        "temperature": 2, "tint": 0, "saturation": 5,
        "exposure": 0.01, "contrast": 1.06, "pivot": 0.5,
        "lift": 0.0, "gamma": 1.01, "gain": 1.01, "offset": 0.0,
        "blackPoint": 0.005, "whitePoint": 1.0,
        "offsetHue": 0, "offsetAmount": 0.0,
        "midDetail": 5, "colorBoost": 6,
        "shadows": -2, "highlights": 1, "hue": 50, "lumMix": 100,
    },
}

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
        "grade_presets": ["kodak_2383_warm", "warm_chronicle", "clean_studio"],
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
        "grade_presets": ["cinema_teal_amber", "fuji_3513_eterna", "clean_studio"],
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
        "grade_presets": ["cinema_teal_amber", "fuji_3513_eterna", "kodak_2383_warm"],
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
        "grade_presets": ["archival_dossier", "kodak_2383_warm", "fuji_3513_eterna"],
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
        "grade_presets": ["warm_chronicle", "kodak_2383_warm", "archival_dossier"],
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
        "grade_presets": ["clean_studio", "fuji_3513_eterna", "kodak_2383_warm"],
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
        "grade_presets": ["kodak_2383_warm", "archival_dossier", "fuji_3513_eterna"],
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
        "grade_presets": ["warm_chronicle", "kodak_2383_warm", "clean_studio"],
    },
}


_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def sanitize_workspace_filename(file_name: str) -> str:
    """Exact port of walterlow/freecut/src/infrastructure/storage/workspace-fs/paths.ts `sanitizeWorkspaceFileName`."""
    trimmed = re.sub(r"^\s+|[\s.]+$", "", str(file_name or ""))
    if not trimmed:
        return "source.bin"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", trimmed)
    dot = cleaned.rfind(".")
    has_ext = 0 < dot < len(cleaned) - 1
    stem = cleaned[:dot] if has_ext else cleaned
    ext = cleaned[dot:] if has_ext else ""
    stem_budget = max(1, 200 - len(ext))
    bounded = stem[:stem_budget] if len(stem) > stem_budget else stem
    if bounded.upper() in _WINDOWS_RESERVED_NAMES:
        bounded = f"{bounded}_"
    res = f"{bounded}{ext}"
    return res or "source.bin"


def build_editorial_grade_effects(
    sid: str,
    palette: Dict[str, Any],
    layout_style: str,
    rng: random.Random,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Builds genuine Schema v15 WebGPU adjustment effects (`gpu-color-wheels`, `gpu-grain`, `gpu-vignette`).
    Replaces deprecated v5 `color-grading` LUT objects that FreeCut's runtime ignores.
    """
    grade_pool = palette.get("grade_presets") or ["kodak_2383_warm", "fuji_3513_eterna", "clean_studio"]
    chosen_grade = rng.choice(grade_pool)
    base_params = dict(EDITORIAL_GPU_COLOR_GRADES.get(chosen_grade, EDITORIAL_GPU_COLOR_GRADES["kodak_2383_warm"]))
    # Subtle organic per-scene micro-variation so cuts don't feel mechanically stamped
    intensity = rng.uniform(0.68, 0.95)
    base_params["shadowsAmount"] = round(base_params["shadowsAmount"] * intensity, 3)
    base_params["highlightsAmount"] = round(base_params["highlightsAmount"] * intensity, 3)
    base_params["temperature"] = int(round(base_params["temperature"] * intensity))
    base_params["contrast"] = round(1.0 + (base_params["contrast"] - 1.0) * intensity, 3)

    effects: List[Dict[str, Any]] = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_gpu_wheels")),
            "effect": {
                "type": "gpu-effect",
                "gpuEffectType": "gpu-color-wheels",
                "params": base_params,
            },
            "enabled": True,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_gpu_grain")),
            "effect": {
                "type": "gpu-effect",
                "gpuEffectType": "gpu-grain",
                "params": {
                    "amount": round(rng.uniform(0.014, 0.026), 3),
                    "size": round(rng.uniform(0.8, 1.1), 1),
                    "speed": 1,
                },
            },
            "enabled": True,
        },
    ]
    if layout_style == "full_screen":
        effects.append(
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_gpu_vignette")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-vignette",
                    "params": {
                        "amount": round(rng.uniform(0.20, 0.32), 2),
                        "size": 0.54,
                        "softness": 0.56,
                        "roundness": 1,
                    },
                },
                "enabled": True,
            }
        )
    label = f"GRADE {chosen_grade.upper().replace('_', ' ')}"
    return label, effects


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

    # 1. Dramatic `text_only` stacked title card (1 word display punch OR 2+ words 2-tier stack)
    if layout_style == "text_only":
        disp_font, disp_weight = sanitize_font_and_weight(palette["display_font"], palette["display_weight"])
        if len(words) == 1:
            return (
                [
                    {
                        "text": words[0].upper(),
                        "fontFamily": disp_font,
                        "fontWeight": disp_weight,
                        "fontSize": rng.randint(96, 114),
                        "letterSpacing": float(palette.get("display_tracking", 2.0)),
                        "color": accent_color if rng.random() < 0.68 else "#FFFFFF",
                    }
                ],
                "stack",
            )
        split_at = 1 if len(words) <= 3 else max(1, len(words) // 2)
        top_words = words[:split_at]
        bot_words = words[split_at:]
        top_line = " ".join(top_words).upper()
        bot_line = " ".join(bot_words).upper()
        body_font, body_weight = sanitize_font_and_weight(palette["body_font"], "semibold")
        if len(bot_words) >= 6:
            bot_size = rng.randint(56, 66)
        elif len(bot_words) >= 4:
            bot_size = rng.randint(66, 78)
        else:
            bot_size = rng.randint(78, 96)
        return (
            [
                {
                    "text": top_line,
                    "fontFamily": body_font,
                    "fontWeight": body_weight,
                    "fontSize": rng.randint(28, 35),
                    "letterSpacing": 4.2,
                    "color": "#CBD5E1",
                },
                {
                    "text": bot_line,
                    "fontFamily": disp_font,
                    "fontWeight": disp_weight,
                    "fontSize": bot_size,
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
            bot_m = rng.randint(82, 98)
            add_top_tape = rng.random() < 0.68
            tape_headroom = 22 if add_top_tape else 0
            sw, sh = pw + 2 * side_m, ph + top_m + bot_m
            paper_tones = [(245, 240, 230), (242, 236, 224), (247, 244, 237)]
            sheet = _make_paper_sheet(sw, sh, rng.choice(paper_tones), grain_opacity=0.055)

            sheet.paste(photo, (side_m, top_m), mask=photo)
            overlay = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            # Subtle inner photo recess bevel + crisp outer paper edge highlight
            odraw.rectangle((side_m - 1, top_m - 1, side_m + pw, top_m + ph), outline=(32, 28, 24, 75), width=1)
            odraw.rounded_rectangle((0, 0, sw - 1, sh - 1), radius=7, outline=(255, 255, 255, 110), width=1)
            # Editorial catalog footer rule + registration ticks + accent swatch on bottom chin
            rule_y = top_m + ph + (bot_m // 2)
            odraw.line([(side_m + 2, rule_y), (sw - side_m - 52, rule_y)], fill=(115, 106, 95, 130), width=1)
            for tx_off in (4, 12, 20, 32, 40):
                odraw.line([(side_m + tx_off, rule_y + 6), (side_m + tx_off, rule_y + 11)], fill=(120, 112, 102, 115), width=1)
            odraw.rectangle(
                (sw - side_m - 38, rule_y - 4, sw - side_m - 26, rule_y + 4),
                fill=(*accent_rgb, 230),
            )
            odraw.rectangle((sw - side_m - 20, rule_y - 4, sw - side_m - 12, rule_y + 4), fill=(72, 66, 58, 185))
            odraw.rectangle((sw - side_m - 7, rule_y - 4, sw - side_m - 2, rule_y + 4), fill=(130, 122, 110, 155))
            sheet = Image.alpha_composite(sheet, overlay)

            cmask = Image.new("L", (sw, sh), 0)
            ImageDraw.Draw(cmask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius=7, fill=255)
            sheet.putalpha(ImageChops.multiply(sheet.getchannel("A"), cmask))

            if add_top_tape:
                card = Image.new("RGBA", (sw, sh + tape_headroom), (0, 0, 0, 0))
                card.paste(sheet, (0, tape_headroom), mask=sheet)
                tape = _make_masking_tape(rng.randint(155, 205), 38, rng)
                tape_rot = tape.rotate(rng.uniform(-4.5, 4.5), resample=Image.Resampling.BICUBIC, expand=True)
                tx = (sw - tape_rot.width) // 2 + rng.randint(-24, 24)
                ty = max(0, tape_headroom - 14)
                card.alpha_composite(tape_rot, (tx, ty))
                final = _compose_with_drop_shadow(card, pad=66, offset=(2, 18), blur_radius=26, shadow_alpha=145)
            else:
                final = _compose_with_drop_shadow(sheet, pad=68, offset=(2, 18), blur_radius=26, shadow_alpha=145)

        elif frame_style == "torn_paper_scrapbook":
            pad_p = 30
            tape_headroom = 26
            cw, ch = pw + 2 * pad_p, ph + 2 * pad_p + tape_headroom
            card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

            paper_w, paper_h = cw, ch - tape_headroom
            outer_pts = _build_torn_polygon(paper_w, paper_h, margin=8, amp=6, rng=rng)
            inner_pts = _build_torn_polygon(paper_w, paper_h, margin=13, amp=4, rng=rng)

            # White fiber deckle outer layer
            fiber_sheet = _make_paper_sheet(paper_w, paper_h, (252, 250, 245), grain_opacity=0.04)
            fmask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(fmask).polygon(outer_pts, fill=255)
            fmask = fmask.filter(ImageFilter.GaussianBlur(0.8))
            fiber_sheet.putalpha(fmask)

            # Warm aged paper inner layer
            cream_sheet = _make_paper_sheet(paper_w, paper_h, (240, 232, 217), grain_opacity=0.065)
            cmask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(cmask).polygon(inner_pts, fill=255)
            cream_sheet.putalpha(cmask)

            paper_comp = Image.alpha_composite(fiber_sheet, cream_sheet)
            paper_comp.paste(photo, (pad_p, pad_p), mask=photo)
            recess = Image.new("RGBA", (paper_w, paper_h), (0, 0, 0, 0))
            ImageDraw.Draw(recess).rectangle(
                (pad_p - 1, pad_p - 1, pad_p + pw, pad_p + ph),
                outline=(45, 38, 30, 68),
                width=1,
            )
            paper_comp = Image.alpha_composite(paper_comp, recess)
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

            # Rich charcoal celluloid base + subtle silver outer rim so strip reads clearly on #000000
            film = _make_paper_sheet(cw, ch, (24, 26, 32), grain_opacity=0.03)
            rmask = Image.new("L", (cw, ch), 0)
            rdraw = ImageDraw.Draw(rmask)
            rdraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=10, fill=255)

            overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=10, outline=(210, 218, 230, 88), width=2)

            amber = (245, 158, 11, 185)
            amber_dim = (245, 158, 11, 115)
            sprocket_rim = (226, 232, 240, 44)
            if horizontal_strip:
                step_x = 42
                for idx_s, sx in enumerate(range(24, cw - 30, step_x)):
                    for sy in (11, ch - 35):
                        rdraw.rounded_rectangle((sx, sy, sx + 18, sy + 24), radius=4, fill=0)
                        odraw.rounded_rectangle((sx - 1, sy - 1, sx + 19, sy + 25), radius=4, outline=sprocket_rim, width=1)
                    if idx_s % 3 == 0:
                        odraw.line([(sx + 23, ch - 8), (sx + 35, ch - 8)], fill=amber, width=2)
                        odraw.line([(sx + 23, 7), (sx + 29, 7)], fill=amber_dim, width=2)
                    elif idx_s % 3 == 1:
                        odraw.polygon([(sx + 25, ch - 10), (sx + 31, ch - 7), (sx + 25, ch - 4)], fill=amber_dim)
            else:
                step_y = 42
                for idx_s, sy in enumerate(range(24, ch - 30, step_y)):
                    for sx in (11, cw - 35):
                        rdraw.rounded_rectangle((sx, sy, sx + 24, sy + 18), radius=4, fill=0)
                        odraw.rounded_rectangle((sx - 1, sy - 1, sx + 25, sy + 19), radius=4, outline=sprocket_rim, width=1)
                    if idx_s % 3 == 0:
                        odraw.line([(cw - 8, sy + 23), (cw - 8, sy + 35)], fill=amber, width=2)
                        odraw.line([(7, sy + 23), (7, sy + 29)], fill=amber_dim, width=2)
                    elif idx_s % 3 == 1:
                        odraw.polygon([(cw - 10, sy + 25), (cw - 7, sy + 31), (cw - 4, sy + 25)], fill=amber_dim)

            # Warm halation inner rim around exposure window
            odraw.rectangle(
                (rebate_lr - 1, rebate_tb - 1, rebate_lr + pw, rebate_tb + ph),
                outline=(245, 158, 11, 125),
                width=1,
            )
            film.paste(photo, (rebate_lr, rebate_tb), mask=photo)
            # Composite semi-transparent markings BEFORE applying punched alpha mask so alpha=0 holes stay pure cutouts
            film = Image.alpha_composite(film, overlay)
            film.putalpha(ImageChops.multiply(film.getchannel("A"), rmask))
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

            mat = _make_paper_sheet(cw, ch, (27, 33, 44), grain_opacity=0.03)
            mmask = Image.new("L", (cw, ch), 0)
            outer_poly = _chamfer_pts(0, 0, cw - 1, ch - 1, cut)
            ImageDraw.Draw(mmask).polygon(outer_poly, fill=255)

            # Clip photo to inner chamfer
            pmask = Image.new("L", (pw, ph), 0)
            inner_photo_poly = _chamfer_pts(0, 0, pw - 1, ph - 1, max(6, cut - 10))
            ImageDraw.Draw(pmask).polygon(inner_photo_poly, fill=255)
            clipped_photo = photo.copy()
            clipped_photo.putalpha(pmask)
            mat.paste(clipped_photo, (pad_m, pad_m), mask=clipped_photo)

            overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.polygon(outer_poly, outline=(226, 232, 240, 195), width=2)
            inner_border_poly = _chamfer_pts(pad_m - 4, pad_m - 4, pad_m + pw + 3, pad_m + ph + 3, max(8, cut - 8))
            odraw.polygon(inner_border_poly, outline=(*accent_rgb, 215), width=1)
            # Tactical registration ticks along top & bottom edges
            odraw.line([(cw // 2 - 18, 5), (cw // 2 + 18, 5)], fill=(*accent_rgb, 180), width=2)
            odraw.line([(cw // 2 - 18, ch - 6), (cw // 2 + 18, ch - 6)], fill=(226, 232, 240, 130), width=1)
            mat = Image.alpha_composite(mat, overlay)
            mat.putalpha(ImageChops.multiply(mat.getchannel("A"), mmask))
            final = _compose_with_drop_shadow(mat, pad=66, offset=(0, 18), blur_radius=26, shadow_alpha=155)

        elif frame_style == "gallery_double_mat":
            frame_w = 9
            mat_w = 26
            fillet_w = 5
            total_m = frame_w + mat_w + fillet_w
            cw, ch = pw + 2 * total_m, ph + 2 * total_m

            # Outer bronze-charcoal museum molding + warm archival cotton passe-partout (stands out on #000000!)
            gallery = Image.new("RGBA", (cw, ch), (40, 37, 34, 255))
            cotton_mat = _make_paper_sheet(cw - 2 * frame_w, ch - 2 * frame_w, (236, 230, 217), grain_opacity=0.05)
            gallery.paste(cotton_mat, (frame_w, frame_w))

            # Dark inner museum fillet reveal + 45-degree white core bevel
            fillet_box = (frame_w + mat_w, frame_w + mat_w, cw - frame_w - mat_w - 1, ch - frame_w - mat_w - 1)
            ImageDraw.Draw(gallery).rectangle(fillet_box, fill=(26, 28, 34, 255))
            gallery.paste(photo, (total_m, total_m), mask=photo)

            overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=5, outline=(214, 202, 182, 185), width=2)
            odraw.rectangle((frame_w, frame_w, cw - frame_w - 1, ch - frame_w - 1), outline=(95, 86, 74, 150), width=1)
            odraw.rectangle(fillet_box, outline=(*accent_rgb, 180), width=1)
            odraw.rectangle(
                (total_m - 2, total_m - 2, total_m + pw + 1, total_m + ph + 1),
                outline=(252, 250, 245, 240),
                width=2,
            )
            gallery = Image.alpha_composite(gallery, overlay)

            gmask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=5, fill=255)
            gallery.putalpha(ImageChops.multiply(gallery.getchannel("A"), gmask))
            final = _compose_with_drop_shadow(gallery, pad=68, offset=(0, 18), blur_radius=28, shadow_alpha=160)

        elif frame_style == "offset_stacked_print":
            border_p = 15
            front_w, front_h = pw + 2 * border_p, ph + 2 * border_p
            front = _make_paper_sheet(front_w, front_h, (246, 243, 236), grain_opacity=0.05)
            front.paste(photo, (border_p, border_p), mask=photo)
            f_over = Image.new("RGBA", (front_w, front_h), (0, 0, 0, 0))
            ImageDraw.Draw(f_over).rectangle(
                (border_p - 1, border_p - 1, border_p + pw, border_p + ph),
                outline=(30, 28, 25, 75),
                width=1,
            )
            front = Image.alpha_composite(front, f_over)
            fmask = Image.new("L", (front_w, front_h), 0)
            ImageDraw.Draw(fmask).rounded_rectangle((0, 0, front_w - 1, front_h - 1), radius=6, fill=255)
            front.putalpha(ImageChops.multiply(front.getchannel("A"), fmask))

            # Secondary backing card rendered at 2x supersampling for razor-sharp rotated edges
            tinted_accent = (
                int(accent_rgb[0] * 0.72 + 42),
                int(accent_rgb[1] * 0.72 + 42),
                int(accent_rgb[2] * 0.72 + 42),
            )
            back_tones = [(218, 207, 185), (54, 64, 82), tinted_accent]
            chosen_back = rng.choice(back_tones)
            bw2, bh2 = front_w * 2, front_h * 2
            back_2x = _make_paper_sheet(bw2, bh2, chosen_back, grain_opacity=0.045)
            b_over = Image.new("RGBA", (bw2, bh2), (0, 0, 0, 0))
            ImageDraw.Draw(b_over).rounded_rectangle(
                (1, 1, bw2 - 2, bh2 - 2),
                radius=12,
                outline=(255, 255, 255, 145),
                width=3,
            )
            back_2x = Image.alpha_composite(back_2x, b_over)
            bmask_2x = Image.new("L", (bw2, bh2), 0)
            ImageDraw.Draw(bmask_2x).rounded_rectangle((0, 0, bw2 - 1, bh2 - 1), radius=12, fill=255)
            back_2x.putalpha(bmask_2x)

            tilt = rng.choice([-2.8, -2.2, 2.2, 2.8])
            back_rot_2x = back_2x.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True)
            back_rot = back_rot_2x.resize(
                (max(2, back_rot_2x.width // 2), max(2, back_rot_2x.height // 2)),
                Image.Resampling.LANCZOS,
            )

            off_x = rng.choice([-18, 18])
            off_y = 15
            comp_w = max(front_w, back_rot.width) + abs(off_x) + 24
            comp_h = max(front_h, back_rot.height) + off_y + 24
            stack = Image.new("RGBA", (comp_w, comp_h), (0, 0, 0, 0))

            bx = (comp_w - back_rot.width) // 2 + (off_x // 2)
            by = (comp_h - back_rot.height) // 2 + (off_y // 2)
            fx = (comp_w - front_w) // 2 - (off_x // 2)
            fy = (comp_h - front_h) // 2 - (off_y // 2)

            stack.alpha_composite(back_rot, (bx, by))
            front_with_contact = _compose_with_drop_shadow(front, pad=16, offset=(0, 5), blur_radius=8, shadow_alpha=105)
            stack.alpha_composite(front_with_contact, (max(0, fx - 16), max(0, fy - 16)))
            final = _compose_with_drop_shadow(stack, pad=56, offset=(0, 18), blur_radius=26, shadow_alpha=145)

        elif frame_style == "vintage_archival_stamp":
            pad_s = 30
            cw, ch = pw + 2 * pad_s, ph + 2 * pad_s
            stamp = _make_paper_sheet(cw, ch, (240, 233, 216), grain_opacity=0.06)
            smask = Image.new("L", (cw, ch), 255)
            sdraw = ImageDraw.Draw(smask)

            # Authentic philatelic postage perforations around all 4 edges (100% consistent)
            step = 26
            r = 6
            margin_x = max(16, ((cw - 32) % step) // 2 + 16)
            margin_y = max(16, ((ch - 32) % step) // 2 + 16)
            for x in range(margin_x, cw - 12, step):
                sdraw.ellipse((x - r, -r, x + r, r), fill=0)
                sdraw.ellipse((x - r, ch - 1 - r, x + r, ch - 1 + r), fill=0)
            for y in range(margin_y, ch - 12, step):
                sdraw.ellipse((-r, y - r, r, y + r), fill=0)
                sdraw.ellipse((cw - 1 - r, y - r, cw - 1 + r, y + r), fill=0)

            stamp.paste(photo, (pad_s, pad_s), mask=photo)
            overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            # Double engraved philatelic border rules
            odraw.rectangle(
                (pad_s - 7, pad_s - 7, pad_s + pw + 6, pad_s + ph + 6),
                outline=(68, 58, 48, 195),
                width=2,
            )
            odraw.rectangle(
                (pad_s - 3, pad_s - 3, pad_s + pw + 2, pad_s + ph + 2),
                outline=(68, 58, 48, 125),
                width=1,
            )
            # Subtle vintage circular postmark cancellation arcs in corner
            pm_cx = cw - pad_s - 18 if rng.random() < 0.5 else pad_s + 18
            pm_cy = ch - pad_s - 14
            for rad in (26, 34):
                odraw.ellipse(
                    (pm_cx - rad, pm_cy - rad, pm_cx + rad, pm_cy + rad),
                    outline=(54, 46, 38, 62),
                    width=2,
                )
            stamp = Image.alpha_composite(stamp, overlay)
            stamp.putalpha(ImageChops.multiply(stamp.getchannel("A"), smask))
            final = _compose_with_drop_shadow(stamp, pad=66, offset=(2, 18), blur_radius=26, shadow_alpha=150)

        else:  # cinema_glass_bevel
            rim = 22
            outer_r = rng.randint(28, 36)
            inner_r = max(14, outer_r - 10)
            cw, ch = pw + 2 * rim, ph + 2 * rim

            # Vibrant frosted glass rim sampled from boosted photo colors so it glows softly on #000000
            boosted = ImageEnhance.Color(photo.convert("RGB")).enhance(1.38).convert("RGBA")
            glass_bg = boosted.resize((cw, ch), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(22))
            tint = Image.new("RGBA", (cw, ch), (24, 28, 38, 118))
            glass = Image.alpha_composite(glass_bg, tint)

            pmask = Image.new("L", (pw, ph), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=inner_r, fill=255)
            p_rounded = photo.copy()
            p_rounded.putalpha(pmask)
            glass.paste(p_rounded, (rim, rim), mask=p_rounded)

            # Alpha-composited directional specular glass bevels
            overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=outer_r, outline=(255, 255, 255, 195), width=2)
            odraw.rounded_rectangle(
                (rim - 1, rim - 1, rim + pw, rim + ph),
                radius=inner_r,
                outline=(255, 255, 255, 110),
                width=1,
            )
            glass = Image.alpha_composite(glass, overlay)

            gmask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=outer_r, fill=244)
            glass.putalpha(ImageChops.multiply(glass.getchannel("A"), gmask))
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
    - Non-16:9 images (portrait, 4:3, square) keep 100% of the photo uncropped over a darkened,
      vignetted, film-grained atmospheric backdrop with randomized handcrafted foreground framing.
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
        # 1. Atmospheric blurred + darkened + vignetted + lightly grained backdrop
        scale_bg = max(CANVAS_W / float(orig_w), CANVAS_H / float(orig_h))
        bg_w = int(orig_w * scale_bg) + 8
        bg_h = int(orig_h * scale_bg) + 8
        bg_resized = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        left = (bg_w - CANVAS_W) // 2
        top = (bg_h - CANVAS_H) // 2
        bg_cropped = bg_resized.crop((left, top, left + CANVAS_W, top + CANVAS_H))
        bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(46))
        dark_overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (6, 8, 12, 146))
        canvas = Image.alpha_composite(bg_blurred, dark_overlay)

        # Radial backdrop vignette + subtle organic film grain
        vig_small = Image.new("L", (96, 54), 95)
        ImageDraw.Draw(vig_small).ellipse((10, 6, 86, 48), fill=0)
        vig_mask = vig_small.filter(ImageFilter.GaussianBlur(12)).resize((CANVAS_W, CANVAS_H), Image.Resampling.BILINEAR)
        canvas.paste((0, 0, 0, 255), (0, 0), mask=vig_mask)
        try:
            noise_l = Image.effect_noise((CANVAS_W // 2, CANVAS_H // 2), 18.0).resize((CANVAS_W, CANVAS_H), Image.Resampling.BILINEAR)
            noise_rgba = Image.merge("RGBA", (noise_l, noise_l, noise_l, Image.new("L", (CANVAS_W, CANVAS_H), 12)))
            canvas = Image.alpha_composite(canvas, noise_rgba)
        except Exception:
            pass

        # 2. Foreground intact scaling with 4 genuine handcrafted editorial borders
        max_fg_w, max_fg_h = 1690, 924
        scale_fg = min(max_fg_w / float(orig_w), max_fg_h / float(orig_h))
        fg_w = max(80, int(orig_w * scale_fg))
        fg_h = max(80, int(orig_h * scale_fg))
        fg_photo = _polish_photo_rgba(img.resize((fg_w, fg_h), Image.Resampling.LANCZOS))

        fg_variant = rng.choice(["rounded_glass_bevel", "museum_fillet_border", "archival_warm_print", "chamfer_cinema_plate"])
        if fg_variant == "rounded_glass_bevel":
            rim = 14
            r_out, r_in = 22, 14
            gw, gh = fg_w + 2 * rim, fg_h + 2 * rim
            glass = fg_photo.resize((gw, gh), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(18))
            glass = Image.alpha_composite(glass, Image.new("RGBA", (gw, gh), (20, 24, 34, 115)))
            pmask = Image.new("L", (fg_w, fg_h), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, fg_w - 1, fg_h - 1), radius=r_in, fill=255)
            p_round = fg_photo.copy()
            p_round.putalpha(pmask)
            glass.paste(p_round, (rim, rim), mask=p_round)
            over = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
            ImageDraw.Draw(over).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=r_out, outline=(255, 255, 255, 175), width=2)
            ImageDraw.Draw(over).rounded_rectangle((rim - 1, rim - 1, rim + fg_w, rim + fg_h), radius=r_in, outline=(255, 255, 255, 95), width=1)
            glass = Image.alpha_composite(glass, over)
            gmask = Image.new("L", (gw, gh), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=r_out, fill=245)
            glass.putalpha(ImageChops.multiply(glass.getchannel("A"), gmask))
            framed_fg = glass
        elif fg_variant == "museum_fillet_border":
            m = 16
            gw, gh = fg_w + 2 * m, fg_h + 2 * m
            framed_fg = _make_paper_sheet(gw, gh, (235, 229, 216), grain_opacity=0.045)
            framed_fg.paste(fg_photo, (m, m), mask=fg_photo)
            over = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
            ImageDraw.Draw(over).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=5, outline=(255, 255, 255, 180), width=2)
            ImageDraw.Draw(over).rectangle((m - 2, m - 2, m + fg_w + 1, m + fg_h + 1), outline=(48, 42, 36, 145), width=2)
            framed_fg = Image.alpha_composite(framed_fg, over)
            gmask = Image.new("L", (gw, gh), 0)
            ImageDraw.Draw(gmask).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=5, fill=255)
            framed_fg.putalpha(gmask)
        elif fg_variant == "archival_warm_print":
            m = 14
            bot = 28
            gw, gh = fg_w + 2 * m, fg_h + m + bot
            framed_fg = _make_paper_sheet(gw, gh, (244, 239, 229), grain_opacity=0.05)
            framed_fg.paste(fg_photo, (m, m), mask=fg_photo)
            over = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
            ImageDraw.Draw(over).rectangle((m - 1, m - 1, m + fg_w, m + fg_h), outline=(36, 32, 28, 75), width=1)
            ry = m + fg_h + (bot // 2)
            ImageDraw.Draw(over).line([(m + 2, ry), (gw - m - 24, ry)], fill=(120, 112, 100, 120), width=1)
            ImageDraw.Draw(over).rectangle((gw - m - 16, ry - 3, gw - m - 4, ry + 3), fill=(245, 158, 11, 210))
            framed_fg = Image.alpha_composite(framed_fg, over)
            pmask = Image.new("L", (gw, gh), 0)
            ImageDraw.Draw(pmask).rounded_rectangle((0, 0, gw - 1, gh - 1), radius=6, fill=255)
            framed_fg.putalpha(pmask)
        else:  # chamfer_cinema_plate
            m = 14
            cut = 20
            gw, gh = fg_w + 2 * m, fg_h + 2 * m
            poly = [(cut, 0), (gw - 1 - cut, 0), (gw - 1, cut), (gw - 1, gh - 1 - cut), (gw - 1 - cut, gh - 1), (cut, gh - 1), (0, gh - 1 - cut), (0, cut)]
            framed_fg = _make_paper_sheet(gw, gh, (26, 31, 42), grain_opacity=0.03)
            framed_fg.paste(fg_photo, (m, m), mask=fg_photo)
            over = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
            ImageDraw.Draw(over).polygon(poly, outline=(226, 232, 240, 185), width=2)
            ImageDraw.Draw(over).rectangle((m - 1, m - 1, m + fg_w, m + fg_h), outline=(251, 191, 36, 165), width=1)
            framed_fg = Image.alpha_composite(framed_fg, over)
            pmask = Image.new("L", (gw, gh), 0)
            ImageDraw.Draw(pmask).polygon(poly, fill=255)
            framed_fg.putalpha(pmask)

        lifted = _compose_with_drop_shadow(framed_fg, pad=44, offset=(0, 14), blur_radius=24, shadow_alpha=170)
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


def _build_single_filmstrip_target(
    total_frames: int,
    priority_idx_range: Optional[Tuple[int, int]],
) -> set[int]:
    """
    Bit-exact port of walterlow/freecut `FilmstripCacheService.buildTargetIndices`
    (`src/features/timeline/services/filmstrip-cache.ts` + `filmstrip-cache-config.ts`).
    """
    if total_frames <= 0:
        return set()

    MIN_FILMSTRIP_TARGET_FRAMES = 40
    MAX_FILMSTRIP_TARGET_FRAMES = 72
    TARGET_FRAME_BUDGET_SCALE = 4
    MAX_PRIORITY_DENSE_FRAMES = 180
    MEDIUM_CLIP_FRAME_THRESHOLD = 300
    LONG_CLIP_FRAME_THRESHOLD = 1200
    VERY_LONG_CLIP_FRAME_THRESHOLD = 2400

    target: set[int] = {0, total_frames - 1}

    # Exact port of buildPriorityIndices(totalFrames, priorityRange)
    if priority_idx_range is not None:
        start_idx = max(0, min(total_frames - 1, int(priority_idx_range[0])))
        end_idx = max(start_idx + 1, min(total_frames, int(priority_idx_range[1])))
        range_len = max(0, end_idx - start_idx)
        if range_len > 0:
            if range_len <= MAX_PRIORITY_DENSE_FRAMES:
                for i in range(start_idx, end_idx):
                    target.add(i)
            else:
                p_stride = int(math.ceil(range_len / float(MAX_PRIORITY_DENSE_FRAMES)))
                for i in range(start_idx, end_idx, p_stride):
                    target.add(i)
                target.add(start_idx)
                target.add(end_idx - 1)

    if total_frames <= MIN_FILMSTRIP_TARGET_FRAMES:
        return set(range(total_frames))

    # JS Math.round(x) rounds +0.5 upward -> math.floor(x + 0.5)
    js_round_budget = int(math.floor(math.sqrt(total_frames) * TARGET_FRAME_BUDGET_SCALE + 0.5))
    budget = max(
        MIN_FILMSTRIP_TARGET_FRAMES,
        min(total_frames, min(MAX_FILMSTRIP_TARGET_FRAMES, js_round_budget)),
    )
    if budget >= total_frames:
        return set(range(total_frames))

    if total_frames <= MEDIUM_CLIP_FRAME_THRESHOLD:
        bg_stride = 1
    elif total_frames <= LONG_CLIP_FRAME_THRESHOLD:
        bg_stride = 2
    elif total_frames <= VERY_LONG_CLIP_FRAME_THRESHOLD:
        bg_stride = 3
    else:
        bg_stride = 4

    background_candidates = [i for i in range(0, total_frames, bg_stride) if i not in target]
    remaining_budget = max(0, budget - len(target))
    if remaining_budget == 0 or not background_candidates:
        return target

    if len(background_candidates) <= remaining_budget:
        target.update(background_candidates)
    else:
        step = len(background_candidates) / float(remaining_budget)
        for i in range(remaining_budget):
            outside_idx = int(math.floor(i * step))
            chosen = background_candidates[min(len(background_candidates) - 1, outside_idx)]
            target.add(chosen)

    return target


def compute_freecut_filmstrip_target_indices(
    duration_s: float,
    priority_ranges: Optional[Sequence[Tuple[float, float]]] = None,
) -> List[int]:
    """
    Computes the exact union of frame indices needed so FreeCut's `needsRefinementForTarget`
    (`use-filmstrip.ts` + `filmstrip-cache.ts`) returns `False` for both `priorityWindow = null`
    and every timeline clip's `{startTime, endTime}` window, with zero excess file bloat.
    """
    dur = max(0.1, float(duration_s))
    total_frames = max(1, int(math.ceil(dur * 1.0)))
    if total_frames <= 40:
        return list(range(total_frames))

    union_idx: set[int] = set()
    union_idx |= _build_single_filmstrip_target(total_frames, None)
    for st, et in priority_ranges or ():
        s0 = max(0, int(math.floor(float(st))))
        e0 = max(s0 + 1, int(math.ceil(float(et))))
        union_idx |= _build_single_filmstrip_target(total_frames, (s0, e0))
    return sorted(union_idx)


def generate_video_filmstrip_cache(
    video_path: str,
    src_w: int,
    src_h: int,
    duration_s: float,
    filmstrip_dir: str,
    priority_ranges: Optional[Sequence[Tuple[float, float]]] = None,
) -> Optional[str]:
    """
    Pre-extracts FreeCut Schema v2 JPEG filmstrip frames (`{index}.jpg` + `meta.json`) inside
    `media/{id}/cache/filmstrip/` matching `buildTargetIndices` 1:1 so FreeCut opens the timeline
    with ZERO WebCodecs worker extraction and ZERO excess file scan bloat.
    Returns path to frame `0.jpg` if extracted so it can double as `thumbnail.jpg`.
    """
    try:
        os.makedirs(filmstrip_dir, exist_ok=True)
        for stale in os.listdir(filmstrip_dir):
            if stale.endswith(".jpg") or stale == "meta.json":
                try:
                    os.remove(os.path.join(filmstrip_dir, stale))
                except OSError:
                    pass

        dur = max(0.1, float(duration_s))
        fw, fh = fit_filmstrip_size(src_w, src_h)
        target_indices = compute_freecut_filmstrip_target_indices(dur, priority_ranges)
        total_frames = max(1, int(math.ceil(dur * 1.0)))

        if total_frames <= 40:
            out_pattern = os.path.join(filmstrip_dir, "%d.jpg")
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-i", video_path,
                "-vf", f"fps=1,scale={fw}:{fh}",
                "-q:v", "7",
                "-start_number", "0",
                out_pattern,
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        else:
            # Fast demuxer-seek extraction in batches of 16 for >45s / multi-minute videos
            batch_size = 16
            safe_end = max(0.0, dur - 0.12)
            for b0 in range(0, len(target_indices), batch_size):
                batch = target_indices[b0 : b0 + batch_size]
                cmd = ["ffmpeg", "-y", "-v", "error"]
                for idx in batch:
                    seek_t = min(float(idx), safe_end)
                    cmd.extend(["-ss", f"{seek_t:.3f}", "-i", video_path])
                for k, idx in enumerate(batch):
                    dest_jpg = os.path.join(filmstrip_dir, f"{idx}.jpg")
                    cmd.extend([
                        "-map", f"{k}:v:0",
                        "-frames:v", "1",
                        "-vf", f"scale={fw}:{fh}",
                        "-q:v", "7",
                        dest_jpg,
                    ])
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

        # Guarantee every target index exists (handles fractional EOF frames like ceil(10.04) - 1 = 10)
        existing_sorted = sorted(
            [
                int(f[:-4])
                for f in os.listdir(filmstrip_dir)
                if f.endswith(".jpg") and f[:-4].isdigit() and os.path.getsize(os.path.join(filmstrip_dir, f)) > 0
            ]
        )
        if not existing_sorted:
            # Emergency single-frame fallback at t=0
            zero_fallback = os.path.join(filmstrip_dir, "0.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", video_path, "-frames:v", "1", "-vf", f"scale={fw}:{fh}", "-q:v", "7", zero_fallback],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
            )
            if os.path.isfile(zero_fallback) and os.path.getsize(zero_fallback) > 0:
                existing_sorted = [0]
            else:
                return None

        last_valid_path = os.path.join(filmstrip_dir, f"{existing_sorted[0]}.jpg")
        for idx in target_indices:
            cand = os.path.join(filmstrip_dir, f"{idx}.jpg")
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                last_valid_path = cand
            else:
                shutil.copy2(last_valid_path, cand)

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


def generate_waveform_multires_bin(
    audio_path: str,
    duration_s: float,
    dest_bin_path: str,
    write_bins: bool = True,
    media_id: Optional[str] = None,
) -> bool:
    """
    Generates BOTH FreeCut waveform storage formats in a single `ffmpeg` decode pass inside
    `media/{id}/cache/waveform/`:
    1. `meta.json` + 30s `bin-{i}.meta.json` + `bin-{i}.bin` (Schema v2 `WaveformMeta`/`WaveformBin`
       probed first by `waveformCache.loadFromStorage` — eliminates FSA `NotFoundError` misses & OPFS copy).
    2. `multi-res.bin` (`WFORM` v1 binary with levels [500, 100, 25, 10] Hz for multi-zoom display).
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

        # 1. Write WFORM v1 binary (`multi-res.bin`):
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

        wf_dir = os.path.dirname(dest_bin_path)
        os.makedirs(wf_dir, exist_ok=True)
        with open(dest_bin_path, "wb") as bf:
            bf.write(header)
            bf.write(index_buf)
            for ch_bytes in payload_chunks:
                bf.write(ch_bytes)

        # 2. Write primary `WaveformMeta` (`meta.json`) + 30s `WaveformBin` (`bin-{i}.meta.json` + `bin-{i}.bin`)
        #    matching `src/types/storage.ts` & `src/infrastructure/storage/workspace-fs/waveforms.ts` 1:1
        if write_bins:
            resolved_mid = media_id
            if not resolved_mid:
                # Infer from .../media/{mediaId}/cache/waveform
                parent_cache = os.path.dirname(wf_dir)
                parent_media = os.path.dirname(parent_cache)
                resolved_mid = os.path.basename(parent_media) or os.path.basename(wf_dir) or "media"

            bin_duration_sec = 30
            samples_per_bin = base_rate * bin_duration_sec  # 15000
            bin_count = max(1, int(math.ceil(n0 / float(samples_per_bin))))
            try:
                updated_ms = int(os.path.getmtime(audio_path) * 1000)
            except OSError:
                updated_ms = 1735689600000

            for b_idx in range(bin_count):
                b_start = b_idx * samples_per_bin
                b_end = min(n0, (b_idx + 1) * samples_per_bin)
                sub_arr = peaks_500[b_start:b_end]
                if os.sys.byteorder != "little":
                    sub_copy = array.array("f", sub_arr)
                    sub_copy.byteswap()
                    bin_bytes = sub_copy.tobytes()
                else:
                    bin_bytes = sub_arr.tobytes()
                with open(os.path.join(wf_dir, f"bin-{b_idx}.bin"), "wb") as bfile:
                    bfile.write(bin_bytes)
                bin_meta = {
                    "id": f"{resolved_mid}:bin:{b_idx}",
                    "mediaId": resolved_mid,
                    "kind": "bin",
                    "binIndex": b_idx,
                    "samples": len(sub_arr),
                    "createdAt": updated_ms,
                }
                with open(os.path.join(wf_dir, f"bin-{b_idx}.meta.json"), "w", encoding="utf-8") as bmfile:
                    json.dump(bin_meta, bmfile, separators=(",", ":"))

            wf_meta = {
                "id": resolved_mid,
                "mediaId": resolved_mid,
                "kind": "meta",
                "sampleRate": base_rate,
                "totalSamples": n0,
                "binCount": bin_count,
                "binDurationSec": bin_duration_sec,
                "duration": round(dur, 4),
                "channels": 1,
                "stereo": False,
                "createdAt": updated_ms,
            }
            with open(os.path.join(wf_dir, "meta.json"), "w", encoding="utf-8") as mfile:
                json.dump(wf_meta, mfile, separators=(",", ":"))

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
    video_priority_ranges: Optional[Dict[str, Sequence[Tuple[float, float]]]] = None,
) -> Dict[str, bool]:
    """
    Populates `thumbnail.jpg`, `cache/filmstrip/` (`buildTargetIndices` + Schema v2 `meta.json`),
    and `cache/waveform/` (`meta.json` + `bin-*.bin` + `multi-res.bin`) in parallel
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
            pr_list = (video_priority_ranges or {}).get(media_id)
            frame0 = generate_video_filmstrip_cache(src_path, w, h, dur, fs_dir, priority_ranges=pr_list)
            if frame0 and os.path.isfile(frame0):
                shutil.copy2(frame0, thumb_path)
                has_thumb = True
            else:
                has_thumb = generate_media_thumbnail_jpg(src_path, mime, thumb_path)
        elif mime.startswith("image/"):
            has_thumb = generate_media_thumbnail_jpg(src_path, mime, thumb_path)
        elif mime.startswith("audio/"):
            wf_path = os.path.join(media_dir, "cache", "waveform", "multi-res.bin")
            generate_waveform_multires_bin(src_path, dur, wf_path, write_bins=True, media_id=media_id)

        return (media_id, has_thumb)

    workers = min(6, max(2, os.cpu_count() or 4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for mid, ok in pool.map(_warm_one, manifest_media):
            thumb_ok[mid] = ok

    return thumb_ok
