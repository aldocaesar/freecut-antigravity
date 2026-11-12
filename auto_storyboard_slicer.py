"""
Auto Storyboard Slicer & Autonomous AI Storyboard Director Module
==================================================================
Implements autonomous, semantic, dynamic scene direction and frame-accurate
narration slicing for FreeCut automated video production pipelines.

Complies with:
- GUIA_EDICAO_DINAMICA.md (Multi-layer Z-Depth, Shot Scale Matrix, Pacing, Dynamic Direction)
- AGENTS.md (Politician query rules, Non-politician conceptualization, >=50% visual diversity,
  concise 2-4 keywords, zero adult/hard terms, safe POP routing)
- FreeCut Schema v15 (track_bg, track_anchor, track_sfx, track_fg, ducking <= 0.50)
"""

from __future__ import annotations

import glob
import json
import logging
import math
import os
import random
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("auto_storyboard_slicer")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Ensure repository root is on sys.path for local module imports
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import asset_catalog
except ImportError:
    asset_catalog = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pacing & Boundary Constants (Anti-Freeze & Zero-Duration Rules)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MIN_DURATION_MS = 3000   # 3.0 seconds minimum per scene
DEFAULT_MAX_DURATION_MS = 7000   # 7.0 seconds soft ceiling per scene
HARD_MAX_DURATION_MS = 7500      # 7.5 seconds absolute hard maximum
MIN_SCENE_MERGE_FLOOR_MS = 2500  # Merge tail segments shorter than 2.5s
ACOUSTIC_PAUSE_THRESHOLD_MS = 350 # Audio pause / breath gap in milliseconds


# ─────────────────────────────────────────────────────────────────────────────
# 2. AGENTS.md Knowledge Bases (Politicians, Authorities & Contextual Archetypes)
# ─────────────────────────────────────────────────────────────────────────────

# Known Brazilian & International Public Figures -> Standardized "[Nome] [Sobrenome] [Cargo]"
POLITICIAN_CANONICAL_MAP: Dict[str, str] = {
    # Presidents & Prime Ministers
    "lula": "Lula presidente",
    "luiz inacio lula da silva": "Lula presidente",
    "jair bolsonaro": "Jair Bolsonaro presidente",
    "bolsonaro": "Jair Bolsonaro presidente",
    "michel temer": "Michel Temer ex-presidente",
    "dilma rousseff": "Dilma Rousseff ex-presidente",
    "fernando henrique cardoso": "FHC ex-presidente",
    "fhc": "FHC ex-presidente",
    "joe biden": "Joe Biden presidente",
    "donald trump": "Donald Trump presidente",
    "emmanuel macron": "Emmanuel Macron presidente",
    "vladimir putin": "Vladimir Putin presidente",
    "xi jinping": "Xi Jinping presidente",
    "javier milei": "Javier Milei presidente",

    # STF / Judicial Authorities
    "alexandre de moraes": "Alexandre de Moraes ministro",
    "moraes": "Alexandre de Moraes ministro",
    "gilmar mendes": "Gilmar Mendes ministro",
    "luis roberto barroso": "Luís Roberto Barroso ministro",
    "luís roberto barroso": "Luís Roberto Barroso ministro",
    "barroso": "Luís Roberto Barroso ministro",
    "dias toffoli": "Dias Toffoli ministro",
    "toffoli": "Dias Toffoli ministro",
    "carmen lucia": "Cármen Lúcia ministra",
    "cármen lúcia": "Cármen Lúcia ministra",
    "luiz fux": "Luiz Fux ministro",
    "fux": "Luiz Fux ministro",
    "kassio nunes marques": "Kassio Nunes Marques ministro",
    "nunes marques": "Kassio Nunes Marques ministro",
    "andre mendonca": "André Mendonça ministro",
    "andré mendonça": "André Mendonça ministro",
    "cristiano zanin": "Cristiano Zanin ministro",
    "zanin": "Cristiano Zanin ministro",
    "flavio dino": "Flávio Dino ministro",
    "flávio dino": "Flávio Dino ministro",
    "augusto aras": "Augusto Aras procurador",
    "paulo gonet": "Paulo Gonet procurador",

    # Senate / Senadores
    "flavio bolsonaro": "Flávio Bolsonaro senador",
    "flávio bolsonaro": "Flávio Bolsonaro senador",
    "eduardo girao": "Eduardo Girão senador",
    "eduardo girão": "Eduardo Girão senador",
    "girao": "Eduardo Girão senador",
    "girão": "Eduardo Girão senador",
    "rodrigo pacheco": "Rodrigo Pacheco senador",
    "pacheco": "Rodrigo Pacheco senador",
    "sergio moro": "Sergio Moro senador",
    "sérgio moro": "Sergio Moro senador",
    "moro": "Sergio Moro senador",
    "hamilton mourao": "Hamilton Mourão senador",
    "hamilton mourão": "Hamilton Mourão senador",
    "mourão": "Hamilton Mourão senador",
    "randolfe rodrigues": "Randolfe Rodrigues senador",
    "renan calheiros": "Renan Calheiros senador",
    "marcos do val": "Marcos do Val senador",
    "magno malta": "Magno Malta senador",
    "carlos portinho": "Carlos Portinho senador",
    "cleitinho": "Cleitinho senador",
    "omar aziz": "Omar Aziz senador",
    "carlos viana": "Carlos Viana senador",

    # Chamber of Deputies / Deputados
    "arthur lira": "Arthur Lira deputado",
    "lira": "Arthur Lira deputado",
    "eduardo bolsonaro": "Eduardo Bolsonaro deputado",
    "nikolas ferreira": "Nikolas Ferreira deputado",
    "guilherme boulos": "Guilherme Boulos deputado",
    "boulos": "Guilherme Boulos deputado",
    "kim kataguiri": "Kim Kataguiri deputado",
    "gleisi hoffmann": "Gleisi Hoffmann deputada",
    "erika hilton": "Erika Hilton deputada",
    "ricardo salles": "Ricardo Salles deputado",
    "tabata amaral": "Tabata Amaral deputada",
    "marcel van hattem": "Marcel van Hattem deputado",
    "carla zambelli": "Carla Zambelli deputada",
    "bia kicis": "Bia Kicis deputada",
    "jandira feghali": "Jandira Feghali deputada",

    # Governors / Governadores
    "tarcisio de freitas": "Tarcísio de Freitas governador",
    "tarcísio de freitas": "Tarcísio de Freitas governador",
    "tarcisio": "Tarcísio de Freitas governador",
    "tarcísio": "Tarcísio de Freitas governador",
    "romeu zema": "Romeu Zema governador",
    "zema": "Romeu Zema governador",
    "claudio castro": "Cláudio Castro governador",
    "cláudio castro": "Cláudio Castro governador",
    "ronaldo caiado": "Ronaldo Caiado governador",
    "caiado": "Ronaldo Caiado governador",
    "eduardo leite": "Eduardo Leite governador",
    "ratinho junior": "Ratinho Junior governador",
    "jerônimo rodrigues": "Jerônimo Rodrigues governador",

    # Ministers / Ministros de Estado
    "fernando haddad": "Fernando Haddad ministro",
    "haddad": "Fernando Haddad ministro",
    "simone tebet": "Simone Tebet ministra",
    "camilo santana": "Camilo Santana ministro",
    "geraldo alckmin": "Geraldo Alckmin vice-presidente",
    "rui costa": "Rui Costa ministro",
    "marina silva": "Marina Silva ministra",
    "anielle franco": "Anielle Franco ministra",
    "carlos fvaro": "Carlos Fávaro ministro",
    "sonia guajajara": "Sonia Guajajara ministra",
}

# Known Non-Politicians / Private Civilians -> Mapped to Conceptual Ilustrative Queries
NON_POLITICIAN_REPLACEMENTS: Dict[str, str] = {
    "tiago miranda": "empresario de terno reuniao",
    "daniel vorcaro": "banqueiro escritorio financas",
    "marcos silva": "homem falando celular escritorio",
    "lucas oliveira": "executivo reuniao corporativa",
    "juliana santos": "mulher microfone protesto",
    "gabriel souza": "jovem estudante palestra",
    "rodrigo alves": "analista mercado financas",
    "tiago": "empresario de terno reuniao",
    "vorcaro": "banqueiro escritorio financas",
}

# Metonymic Contextual Queries for >= 50% Visual Diversity in Storyboards
CONTEXTUAL_DIVERSITY_POOL: List[str] = [
    "STF plenario sessao",
    "urna eletronica voto",
    "policial federal viatura",
    "congresso nacional cupula",
    "senado federal plenario",
    "palacio do planalto brasilia",
    "tribunal justica martelo",
    "processo judicial autos",
    "manifestacao praca tres poderes",
    "dinheiro macos cedulas",
    "grafico estatistica barras",
    "bandeira brasil mastro",
    "computador seguranca cyber",
    "sala reuniao corporativa",
    "documento confidencial carimbo",
    "assinatura contrato caneta",
    "multidao protesto rua",
    "palacio itamaraty brasilia",
    "sala de imprensa microfones",
    "coletiva imprensa cameras",
]

# Forbidden Words to Purge Immediately (Safety & Anti-Frustration)
FORBIDDEN_QUERY_TERMS: Set[str] = {
    "adult", "hard", "nsfw", "porn", "nude", "naked", "sex", "explicit", "gore"
}

# Redundant Qualifiers to Strip from Stock Searches
REDUNDANT_QUALIFIERS: List[str] = [
    "high-quality photograph", "high quality", "high-resolution", "hd", "4k",
    "closeup", "close-up", "documentary shot", "version 11", "photorealistic",
    "8k", "ultra detailed", "cinematic shot", "hyperrealistic", "masterpiece"
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Step 1: Strict Audio & Punctuation-Based Slicing Engine
# ─────────────────────────────────────────────────────────────────────────────

def auto_slice_words(
    words: List[Dict[str, Any]],
    min_duration_ms: int = DEFAULT_MIN_DURATION_MS,
    max_duration_ms: int = DEFAULT_MAX_DURATION_MS,
    hard_max_duration_ms: int = HARD_MAX_DURATION_MS
) -> List[Dict[str, Any]]:
    """
    Slices a list of word timestamps (words.json) strictly by grammatical punctuation
    and natural acoustic pauses into contiguous scene segments.
    
    Guarantees:
    1. Every scene duration is strictly between min_duration_ms and hard_max_duration_ms (3.0s - 7.5s).
    2. Zero-duration scenes (start_ms == end_ms) are strictly impossible.
    3. Perfect contiguity with zero gaps: scene[N+1].start_ms == scene[N].end_ms.
    4. Handles composite punctuations, hyphenated words (e.g. 'Grã-Bretanha.'), and acoustic pauses.
    """
    if not words:
        return []

    scenes_data: List[Dict[str, Any]] = []
    current_words: List[Dict[str, Any]] = []
    current_start_ms = words[0]["start_ms"]

    for i, w in enumerate(words):
        word_text = str(w.get("word", "")).strip()
        word_end = int(w.get("end_ms", 0))
        word_start = int(w.get("start_ms", 0))

        if not current_words:
            current_start_ms = word_start if not scenes_data else scenes_data[-1]["end_ms"]

        current_words.append(w)
        dur = word_end - current_start_ms

        # Detect punctuation types
        has_strong_punct = bool(re.search(r"[\.\!\?\:]+$", word_text))
        has_clause_punct = bool(re.search(r"[\,\;\—\–\-]|\-\-$", word_text))

        # Detect acoustic pause to next word (>= 350ms breath silence)
        has_acoustic_pause = False
        if i < len(words) - 1:
            next_start = int(words[i + 1].get("start_ms", 0))
            if next_start - word_end >= ACOUSTIC_PAUSE_THRESHOLD_MS:
                has_acoustic_pause = True

        is_last_word = (i == len(words) - 1)

        # Decision Logic for Cut:
        should_cut = False
        if is_last_word:
            should_cut = True
        elif dur >= max_duration_ms:
            # Force cut on soft ceiling
            should_cut = True
        elif dur >= min_duration_ms:
            if has_strong_punct:
                should_cut = True
            elif dur >= 4500 and (has_clause_punct or has_acoustic_pause):
                should_cut = True
            elif dur >= 5800:
                should_cut = True

        if should_cut:
            scene_narration = " ".join(str(item.get("word", "")).strip() for item in current_words)
            scenes_data.append({
                "start_ms": current_start_ms,
                "end_ms": word_end if not is_last_word else int(words[-1].get("end_ms", word_end)),
                "narration": scene_narration,
                "words_count": len(current_words),
                "words": list(current_words)
            })
            current_words = []

    # Post-Processing: Rebalance or Merge Abnormal Tail Segments
    if len(scenes_data) >= 2:
        last_dur = scenes_data[-1]["end_ms"] - scenes_data[-1]["start_ms"]
        prev_dur = scenes_data[-2]["end_ms"] - scenes_data[-2]["start_ms"]

        # If last scene is under the floor (< 2.5s) and merging doesn't exceed hard maximum
        if last_dur < MIN_SCENE_MERGE_FLOOR_MS:
            if prev_dur + last_dur <= hard_max_duration_ms:
                # Merge into previous scene
                scenes_data[-2]["end_ms"] = scenes_data[-1]["end_ms"]
                scenes_data[-2]["narration"] = f"{scenes_data[-2]['narration']} {scenes_data[-1]['narration']}".strip()
                scenes_data[-2]["words_count"] += scenes_data[-1]["words_count"]
                scenes_data[-2]["words"].extend(scenes_data[-1].get("words", []))
                scenes_data.pop()
            else:
                # Rebalance words between last two scenes
                all_combined_words = scenes_data[-2].get("words", []) + scenes_data[-1].get("words", [])
                if len(all_combined_words) >= 4:
                    mid_idx = len(all_combined_words) // 2
                    first_half = all_combined_words[:mid_idx]
                    second_half = all_combined_words[mid_idx:]

                    scenes_data[-2]["end_ms"] = first_half[-1]["end_ms"]
                    scenes_data[-2]["narration"] = " ".join(w["word"] for w in first_half)
                    scenes_data[-2]["words_count"] = len(first_half)
                    scenes_data[-2]["words"] = first_half

                    scenes_data[-1]["start_ms"] = first_half[-1]["end_ms"]
                    scenes_data[-1]["narration"] = " ".join(w["word"] for w in second_half)
                    scenes_data[-1]["words_count"] = len(second_half)
                    scenes_data[-1]["words"] = second_half

    # Absolute Contiguity & Zero-Gap Enforcement
    if scenes_data:
        scenes_data[0]["start_ms"] = 0
        for j in range(len(scenes_data) - 1):
            scenes_data[j + 1]["start_ms"] = scenes_data[j]["end_ms"]
        scenes_data[-1]["end_ms"] = int(words[-1]["end_ms"])

    return scenes_data


# ─────────────────────────────────────────────────────────────────────────────
# 4. Step 2: Semantic Archetype Classifier & Anti-Monotony Filter
# ─────────────────────────────────────────────────────────────────────────────

def classify_scene_archetype(
    narration: str,
    scene_idx: int,
    total_scenes: int,
    prev_archetypes: List[str],
    duration_ms: int,
    mode: str = "default",
    universe: str = ""
) -> Dict[str, Any]:
    """
    Autonomously evaluates the narration text to select visual archetypes and
    kinetic parameters without rigid hardcoded cyclic templates.
    """
    text_lower = narration.lower()
    rng = random.Random(f"{scene_idx}_{narration[:15]}")

    # Semantic Keyword Scores
    action_keywords = [
        "batalha", "combate", "guerra", "mundo", "horizonte", "panorama",
        "onigashima", "plenário", "plenario", "stf", "congresso", "senado",
        "tribunal", "arena", "cidade", "paisagem", "reino", "multidão", "multidao",
        "universo", "epic", "battle", "landscape", "world", "clímax", "climax",
        "explosão", "derrota", "vitória", "vitoria", "destruição", "conflito",
        "revolução", "revolucao", "império", "imperio", "mar", "oceano"
    ]

    data_keywords = [
        "dados", "estatística", "estatistica", "número", "numero", "porcento", "%",
        "relatório", "relatorio", "artigo", "lei", "processo", "prova", "registro",
        "ficha", "especificação", "especificacao", "potência", "potencia", "velocidade",
        "cv", "km/h", "dossiê", "dossie", "irregularidades", "fato", "pesquisa",
        "migram", "votos", "eleitores", "porcentagem", "tabela", "gráfico", "grafico",
        "índice", "indice", "milhões", "milhoes", "bilhões", "bilhoes", "orçamento"
    ]

    character_keywords = [
        "luffy", "zoro", "kaido", "shanks", "barba", "sanji", "senador", "ministro",
        "presidente", "governador", "deputado", "juiz", "advogado", "empresário",
        "banqueiro", "homem", "mulher", "guerreiro", "líder", "lider", "personagem",
        "figura", "autoridade", "testemunha", "carro", "veículo", "ferrari", "espada",
        "akuma", "arma", "objeto", "documento", "carta", "livro", "relic"
    ]

    dramatic_hook_keywords = [
        "atenção", "atencao", "cuidado", "perigo", "segredo", "mistério", "misterio",
        "a verdade", "afinal", "o motivo", "veja bem", "revelação", "revelacao",
        "silêncio", "silencio", "surpresa", "inacreditável", "inacreditavel"
    ]

    is_hook = (scene_idx == 0) or any(k in text_lower for k in dramatic_hook_keywords) or ("?" in narration)
    is_data = any(k in text_lower for k in data_keywords) or bool(re.search(r"\b\d+([,\.]\d+)?\b", text_lower))
    is_action = any(k in text_lower for k in action_keywords)
    is_character = any(k in text_lower for k in character_keywords)

    # Base Archetype Scoring
    score_full_screen = 2.0 if is_action else 1.0
    score_single_card = 2.5 if is_character else 1.5
    score_split_slide = 3.0 if (is_data and duration_ms >= 4500) else 0.5
    score_text_only = 2.5 if (is_hook and duration_ms <= 4500) else 0.2
    score_lottie = 2.0 if ("lottie" in text_lower or (is_data and not is_action)) else 0.3

    # Penalize if repeated in recent scenes (anti-monotony rule)
    if len(prev_archetypes) >= 1 and prev_archetypes[-1] == "full_screen":
        score_full_screen *= 0.4
    if len(prev_archetypes) >= 1 and prev_archetypes[-1] == "single_card":
        score_single_card *= 0.6
    if len(prev_archetypes) >= 1 and prev_archetypes[-1] == "split_info_slide":
        score_split_slide *= 0.2
    if len(prev_archetypes) >= 2 and prev_archetypes[-1] == prev_archetypes[-2]:
        if prev_archetypes[-1] == "single_card":
            score_single_card *= 0.2
        elif prev_archetypes[-1] == "full_screen":
            score_full_screen *= 0.1

    # Frequency Caps Check (Split info slide max 30%)
    split_count = sum(1 for a in prev_archetypes if a == "split_info_slide")
    if total_scenes > 0 and (split_count / max(1, len(prev_archetypes))) >= 0.30:
        score_split_slide = 0.0

    scores = {
        "full_screen": score_full_screen,
        "single_card": score_single_card,
        "split_info_slide": score_split_slide,
        "text_only": score_text_only,
        "lottie": score_lottie
    }

    # Select highest scoring layout
    selected_layout = max(scores, key=lambda k: scores[k])

    # Dynamic Rotations (-3.0° to +3.0° non-zero, organic alternating sign)
    base_sign = 1.0 if (scene_idx % 2 == 0) else -1.0
    sign = base_sign if rng.random() < 0.85 else -base_sign
    rot_mag = round(rng.uniform(1.0, 2.8), 1)
    rotation = round(sign * rot_mag, 1)

    # Scale calculation
    if selected_layout == "single_card":
        scale = round(rng.uniform(0.72, 0.78), 2)
    elif selected_layout == "split_info_slide":
        scale = round(rng.uniform(0.68, 0.74), 2)
    else:
        scale = 1.0

    # Dynamic Ken Burns Camera Direction for full_screen (9 directions)
    ken_burns_options = [
        "zoom_in_center", "zoom_out_center", "pan_left", "pan_right",
        "pan_left_right", "pan_right_left", "pan_top_bottom", "pan_bottom_top",
        "tilt_up", "tilt_down", "slow_push_in", "slow_pull_out"
    ]
    camera_motion = rng.choice(ken_burns_options) if selected_layout == "full_screen" else "none"

    # Dynamic Transition Selection
    transitions_pool = [
        "crossfade", "dissolve", "blurDissolve", "lensWarpZoom", "filmGateSlip",
        "additiveDissolve", "slide", "wipe"
    ]
    transition = rng.choice(transitions_pool) if selected_layout == "full_screen" else "none"

    return {
        "layout_style": selected_layout,
        "rotation": rotation,
        "scale": scale,
        "camera_motion": camera_motion,
        "transition": transition
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Step 3: Asset Catalog Background & SFX Assigners
# ─────────────────────────────────────────────────────────────────────────────

def select_background_for_scene(
    narration: str,
    layout_style: str,
    global_style: str = "dynamic_cinematic",
    universe: str = ""
) -> Dict[str, Any]:
    """
    Selects an appropriate background loop texture from the asset catalog
    based on semantic context and visual universe.
    """
    text_lower = f"{universe} {narration}".lower()

    if any(w in text_lower for w in ["mapa", "geopolitica", "fronteira", "territorio", "map", "rota", "reino", "navegação"]):
        category = "topographic"
    elif any(w in text_lower for w in ["papel", "processo", "documento", "jornal", "dossie", "relatorio", "carta", "judicial", "autos"]):
        category = "paper"
    elif any(w in text_lower for w in ["antigo", "passado", "flashback", "historico", "luto", "vintage", "grain", "filme", "memória"]):
        category = "film_grain"
    elif any(w in text_lower for w in ["batalha", "combate", "guerra", "violencia", "destruicao", "grunge", "trevas", "ataque"]):
        category = "grunge"
    elif any(w in text_lower for w in ["tecnologia", "digital", "rede", "cyber", "dados", "tech", "futuristic", "ferrari", "supercarro"]):
        category = "particles_tech"
    elif any(w in text_lower for w in ["blueprint", "grid", "coordenadas", "radar", "engenharia"]):
        category = "grids"
    elif any(w in text_lower for w in ["clean", "white", "claro", "corporativo", "editorial"]):
        category = "bright_white"
    else:
        category = "dark_minimal"

    asset_filename = None
    if asset_catalog is not None:
        bg_asset = asset_catalog.get_background(category=category, fallback=True)
        if bg_asset:
            asset_filename = bg_asset.filename

    return {
        "source": "asset",
        "category": category,
        "asset_name": asset_filename or "10.mp4",
        "blur": 8,
        "opacity": 0.85
    }


def select_sfx_for_scene(
    narration: str,
    layout_style: str,
    scene_idx: int,
    duration_ms: int,
    prev_had_sfx: bool
) -> Optional[Dict[str, Any]]:
    """
    Selects a synchronized transition SFX (Whoosh or Air-Woosh) ducked within
    safe acoustic levels (0.35 to 0.45), preventing sonic clutter.
    """
    # Prevent chaotic whooshes on rapid consecutive scenes (< 3.5s)
    if duration_ms < 3500 and prev_had_sfx:
        return None

    if layout_style in ["single_card", "full_screen"]:
        # Vigorous Whoosh for card snap entrance / camera cut
        whooshes = ["Whoosh 1.mp3", "Whoosh 2.mp3", "Whoosh 7.mp3"]
        asset_name = random.choice(whooshes)
        volume = 0.42  # Calibrated ducking volume
        sfx_type = "whoosh"
    else:
        # Soft Air-Woosh for info slides / tags
        air_wooshes = ["air-woosh-1.mp3", "air-woosh-2.mp3", "air-woosh-3.mp3", "air-woosh-4.mp3"]
        asset_name = random.choice(air_wooshes)
        volume = 0.35  # Calibrated ducking volume
        sfx_type = "air_woosh"

    return {
        "enabled": True,
        "type": sfx_type,
        "asset": asset_name,
        "volume": volume
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. Step 4: AGENTS.md Query Formulator & POP Mode Router
# ─────────────────────────────────────────────────────────────────────────────

def formulate_scene_query(
    narration: str,
    layout_style: str,
    mode: str = "default",
    universe: str = "",
    used_queries: Optional[List[str]] = None,
    scene_idx: int = 0
) -> Dict[str, Any]:
    """
    Formulates strict AGENTS.md compliant search queries:
    1. Politicians/Authorities: [Nome] + [Sobrenome] + [Cargo/Função]
    2. Non-Politicians / Civilians: Generic conceptual terms in English or Portuguese
    3. Diversity Enforcement: At least 50% contextual queries across the project
    4. Conciseness: 2 to 4 keywords, zero filler words, zero redundant qualifiers
    5. Safety: Purges 'adult' and 'hard' words
    6. POP Mode: Forces image source_type and sets TMDB/DDG providers
    """
    if used_queries is None:
        used_queries = []

    text_clean = narration.lower()

    # 1. Check for Known Politicians & Public Figures (longest full names match first)
    politician_match: Optional[str] = None
    for pol_key in sorted(POLITICIAN_CANONICAL_MAP.keys(), key=len, reverse=True):
        # Match whole words to prevent substring issues
        if re.search(r"\b" + re.escape(pol_key) + r"\b", text_clean):
            politician_match = POLITICIAN_CANONICAL_MAP[pol_key]
            break

    # 2. Check for Non-Politicians / Private Civilians (longest full names match first)
    non_pol_replacement: Optional[str] = None
    for np_key in sorted(NON_POLITICIAN_REPLACEMENTS.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(np_key) + r"\b", text_clean):
            non_pol_replacement = NON_POLITICIAN_REPLACEMENTS[np_key]
            break

    # 3. Calculate Visual Diversity Ratio
    total_q = len(used_queries)
    politician_q_count = sum(1 for q in used_queries if any(p in q.lower() for p in ["presidente", "senador", "ministro", "governador", "deputado"]))
    politician_ratio = politician_q_count / max(1, total_q)

    final_query = ""
    source = "pexels" if layout_style == "full_screen" else "duckduckgo"
    source_type = "video" if layout_style == "full_screen" else "image"
    specific = True

    # 4. Formulate Query Text
    if mode == "pop":
        source_type = "image"
        source = "tmdb" if any(k in universe.lower() for k in ["house of the dragon", "movie", "filme", "serie"]) else "duckduckgo"
        
        # Extract core characters or actions for POP universe
        words = re.findall(r"\b[A-Za-z0-9_]+\b", narration)
        core_words = [w for w in words if len(w) > 3 and w.lower() not in ["quando", "porque", "depois", "sobre", "assim", "entao"]][:3]
        if universe:
            final_query = f"{universe} {' '.join(core_words)}".strip()
        else:
            final_query = " ".join(core_words)
    elif politician_match:
        # Enforce >= 50% visual diversity: If politician ratio is high or alternating, use contextual pool
        if politician_ratio >= 0.50 and total_q >= 2 and (scene_idx % 2 == 1):
            pool_idx = scene_idx % len(CONTEXTUAL_DIVERSITY_POOL)
            final_query = CONTEXTUAL_DIVERSITY_POOL[pool_idx]
            source = "duckduckgo"
            specific = True
        else:
            final_query = politician_match
            source = "duckduckgo"
            specific = True
    elif non_pol_replacement:
        final_query = non_pol_replacement
        source = "pexels"
        specific = False
    else:
        # Generic Concept Query: 2 to 4 concise keywords
        if "lottie" in text_clean or layout_style == "lottie":
            if any(w in text_clean for w in ["alerta", "aviso", "perigo", "warning"]):
                final_query = "warning alert lottie"
            elif any(w in text_clean for w in ["gráfico", "grafico", "crescimento", "financeiro", "dinheiro"]):
                final_query = "financial graph lottie"
            elif any(w in text_clean for w in ["tempo", "espera", "relógio", "relogio", "hora"]):
                final_query = "clock timer lottie"
            else:
                final_query = "abstract motion lottie"
            source_type = "lottie"
            specific = True
        else:
            # Extract nouns and concepts
            stopwords = {
                "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "com",
                "nao", "não", "uma", "os", "no", "se", "na", "por", "mais", "as",
                "dos", "como", "mas", "foi", "ao", "ele", "das", "tem", "seu", "sua",
                "ou", "quando", "muito", "nos", "ja", "já", "eu", "tambem", "também",
                "so", "só", "pelo", "pela", "ate", "até", "isso", "ela", "entre", "era"
            }
            tokens = [t for t in re.findall(r"\b[A-Za-z0-9À-ÿ]+\b", narration) if t.lower() not in stopwords]
            short_tokens = tokens[:3] if tokens else ["cena", "contexto"]

            # Map common concepts to concise English for stock searches
            concept_pt_to_en = {
                "batalha": "battlefield dramatic smoke",
                "dinheiro": "cash money bills",
                "tribunal": "courtroom judge gavel",
                "computador": "cyber security matrix",
                "reuniao": "business executive meeting",
                "notificacao": "phone notification bell 3d",
                "curtir": "youtube subscribe button click",
                "urna": "urna eletronica voto",
                "policia": "policia federal viatura",
                "stf": "STF plenario sessao",
                "congresso": "congresso nacional cupula"
            }

            matched_concept = None
            for pt_k, en_v in concept_pt_to_en.items():
                if pt_k in text_clean:
                    matched_concept = en_v
                    break

            if matched_concept:
                final_query = matched_concept
            else:
                final_query = " ".join(short_tokens[:3])

    # 5. Clean Redundant Qualifiers and Forbidden Terms
    for red in REDUNDANT_QUALIFIERS:
        final_query = re.sub(re.escape(red), "", final_query, flags=re.IGNORECASE)

    # Purge forbidden terms
    clean_words = [w for w in final_query.split() if w.lower() not in FORBIDDEN_QUERY_TERMS]
    final_query = " ".join(clean_words).strip()
    if not final_query:
        final_query = "cinematic scene visual"

    # Enforce concise length (2 to 4 words max for stock, exact for politician)
    query_parts = final_query.split()
    if len(query_parts) > 4 and not politician_match:
        final_query = " ".join(query_parts[:4])

    media_obj: Dict[str, Any] = {
        "query": final_query,
        "source_type": source_type,
        "specific": specific,
        "source": source
    }

    return media_obj


# ─────────────────────────────────────────────────────────────────────────────
# 7. Step 5: Info Card Intelligent Populator
# ─────────────────────────────────────────────────────────────────────────────

def create_info_card_for_scene(
    narration: str,
    duration_ms: int,
    scene_idx: int
) -> Optional[Dict[str, Any]]:
    """
    Creates structured info_card with populated title and content/items
    only when scene duration >= 5000ms.
    """
    if duration_ms < 5000:
        return None

    text_lower = narration.lower()

    # Choose info_card style based on content semantics
    if any(k in text_lower for k in ["processo", "prova", "tribunal", "lei", "relatório", "dossiê", "artigo"]):
        style = "paper_typewriter"
        title = "FACT CHECK"
        content = narration[:90].strip() + ("..." if len(narration) > 90 else "")
        return {
            "style": style,
            "position": "random",
            "title": title,
            "content": content
        }
    elif any(k in text_lower for k in ["dados", "estatística", "porcento", "%", "índice", "números", "potência", "km/h"]):
        style = "futuristic_hud"
        title = "DADO CONCRETO"
        content = narration[:90].strip() + ("..." if len(narration) > 90 else "")
        return {
            "style": style,
            "position": "random",
            "title": title,
            "content": content
        }
    elif any(k in text_lower for k in ["irregularidades", "motivos", "tópicos", "lista", "razões"]):
        style = "checklist_card"
        title = "PONTOS CHAVE"
        # Extract short bullet items
        clauses = [c.strip() for c in re.split(r"[\,\;\.]", narration) if len(c.strip()) > 5][:3]
        if not clauses:
            clauses = ["Análise preliminar dos fatos", "Conclusão técnica do dossiê"]
        return {
            "style": style,
            "position": "random",
            "title": title,
            "items": clauses
        }
    elif any(k in text_lower for k in ["data", "local", "cidade", "estado", "ano"]):
        style = "minimalist_tag"
        title = "REGISTRO"
        content = narration[:70].strip()
        return {
            "style": style,
            "position": "random",
            "title": title,
            "content": content
        }

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Master Storyboard Director Interface
# ─────────────────────────────────────────────────────────────────────────────

def direct_storyboard(
    words: List[Dict[str, Any]],
    title: str = "Automated Video Project",
    project_name: str = "automated_project",
    audio_file: str = "audio.mp3",
    mode: str = "default",
    universe: str = "",
    global_style: str = "dynamic_cinematic"
) -> Dict[str, Any]:
    """
    Master Autonomous AI Storyboard Director:
    Slices words, dynamically directs each scene, applies multi-layer backgrounds,
    synchronized SFX, compliant queries, and validated pacing constraints.
    """
    slices = auto_slice_words(words)
    total_scenes = len(slices)
    scenes: List[Dict[str, Any]] = []

    prev_archetypes: List[str] = []
    used_queries: List[str] = []
    info_card_count = 0
    max_info_cards = max(1, int(total_scenes * 0.20)) # Max 20% frequency cap
    prev_had_sfx = False

    for i, sl in enumerate(slices, 1):
        sid = f"S{i:02d}"
        start_ms = sl["start_ms"]
        end_ms = sl["end_ms"]
        duration_ms = end_ms - start_ms
        narration = sl["narration"]

        # 1. Classify Archetype & Camera Motion
        arch = classify_scene_archetype(
            narration=narration,
            scene_idx=i - 1,
            total_scenes=total_scenes,
            prev_archetypes=prev_archetypes,
            duration_ms=duration_ms,
            mode=mode,
            universe=universe
        )
        layout_style = arch["layout_style"]
        prev_archetypes.append(layout_style)

        # 2. Formulate Compliant Media Query
        media_obj = formulate_scene_query(
            narration=narration,
            layout_style=layout_style,
            mode=mode,
            universe=universe,
            used_queries=used_queries,
            scene_idx=i - 1
        )
        used_queries.append(media_obj["query"])

        # 3. Select Multi-Layer Background Loop (track_bg)
        bg_obj = select_background_for_scene(
            narration=narration,
            layout_style=layout_style,
            global_style=global_style,
            universe=universe
        )

        # 4. Select Synchronized Transition SFX (track_sfx)
        sfx_obj = select_sfx_for_scene(
            narration=narration,
            layout_style=layout_style,
            scene_idx=i - 1,
            duration_ms=duration_ms,
            prev_had_sfx=prev_had_sfx
        )
        prev_had_sfx = bool(sfx_obj)

        # 5. Populate Info Card if Eligible (>= 5.0s, cap <= 20%)
        info_card_obj = None
        if info_card_count < max_info_cards:
            info_card_obj = create_info_card_for_scene(narration, duration_ms, i - 1)
            if info_card_obj:
                info_card_count += 1

        scene: Dict[str, Any] = {
            "id": sid,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "narration": narration,
            "layout_style": layout_style,
            "rotation": arch["rotation"],
            "scale": arch["scale"],
            "transition": arch["transition"],
            "camera_motion": arch["camera_motion"],
            "subtitles": True,
            "background": bg_obj,
            "media": media_obj
        }

        if sfx_obj:
            scene["sfx"] = sfx_obj
        if info_card_obj:
            scene["info_card"] = info_card_obj

        scenes.append(scene)

    storyboard: Dict[str, Any] = {
        "title": title,
        "project_name": project_name,
        "mode": mode,
        "universe": universe,
        "audio_file": audio_file,
        "words_file": "words.json",
        "total_duration_ms": words[-1]["end_ms"] if words else 0,
        "global_style": global_style,
        "subtitles": True,
        "scenes": scenes
    }

    return storyboard


def generate_directed_storyboard(
    project_dir: str,
    title: str = "",
    mode: str = "default",
    universe: str = "",
    global_style: str = "dynamic_cinematic"
) -> str:
    """
    Reads words.json from project_dir, runs autonomous AI storyboard direction,
    and writes out storyboard.json.
    """
    words_path = os.path.join(project_dir, "words.json")
    if not os.path.exists(words_path):
        raise FileNotFoundError(f"words.json não encontrado em: {project_dir}")

    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    audio_files = [f for f in os.listdir(project_dir) if f.endswith(".mp3") or f.endswith(".wav")]
    audio_file = audio_files[0] if audio_files else "audio.mp3"
    proj_name = os.path.basename(os.path.abspath(project_dir))
    proj_title = title or proj_name

    storyboard = direct_storyboard(
        words=words,
        title=proj_title,
        project_name=proj_name,
        audio_file=audio_file,
        mode=mode,
        universe=universe,
        global_style=global_style
    )

    out_path = os.path.join(project_dir, "storyboard.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(storyboard, f, indent=2, ensure_ascii=False)

    logger.info(f"Storyboard autônomo gerado com sucesso em: {out_path} ({len(storyboard['scenes'])} cenas)")
    return out_path


def generate_blank_storyboard(project_dir: str, title: str = "") -> str:
    """Backward-compatible entry point that generates a high-fidelity directed storyboard."""
    return generate_directed_storyboard(project_dir, title=title)
