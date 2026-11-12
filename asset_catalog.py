"""
Asset Catalog & Registry Module
================================
Universal native asset manager for background video loops, texture overlays,
and transition sound effects (SFX) in FreeCut automated video editing pipelines.

Manages 77 background video/image textures across 11 visual categories and 7 SFX
whooshes with acoustic metadata, audio muting flags, and smart fallback routing.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import random
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger("asset_catalog")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Default search directories (100% portable relative paths)
LOCAL_BG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "backgrounds")
LOCAL_SFX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx")
DEFAULT_BG_DIR = LOCAL_BG_DIR
DEFAULT_SFX_DIR = LOCAL_SFX_DIR

# 11 Standard Visual Categories
CATEGORY_TOPOGRAPHIC = "topographic"
CATEGORY_PAPER = "paper"
CATEGORY_FILM_GRAIN = "film_grain"
CATEGORY_GRUNGE = "grunge"
CATEGORY_GRIDS = "grids"
CATEGORY_OVERLAYS = "overlays"
CATEGORY_DARK_MINIMAL = "dark_minimal"
CATEGORY_COLOR_MOOD = "color_mood"
CATEGORY_PARTICLES_TECH = "particles_tech"
CATEGORY_BRIGHT_WHITE = "bright_white"
CATEGORY_CINEMATIC_AMBIENT = "cinematic_ambient"

ALL_CATEGORIES = [
    CATEGORY_TOPOGRAPHIC,
    CATEGORY_PAPER,
    CATEGORY_FILM_GRAIN,
    CATEGORY_GRUNGE,
    CATEGORY_GRIDS,
    CATEGORY_OVERLAYS,
    CATEGORY_DARK_MINIMAL,
    CATEGORY_COLOR_MOOD,
    CATEGORY_PARTICLES_TECH,
    CATEGORY_BRIGHT_WHITE,
    CATEGORY_CINEMATIC_AMBIENT,
]

ENERGY_LOW = "low"
ENERGY_MEDIUM = "medium"
ENERGY_HIGH = "high"
ALL_ENERGY_LEVELS = [ENERGY_LOW, ENERGY_MEDIUM, ENERGY_HIGH]

SFX_KIND_WHOOSH = "whoosh"
SFX_KIND_AIR_WOOSH = "air_woosh"
ALL_SFX_KINDS = [SFX_KIND_WHOOSH, SFX_KIND_AIR_WOOSH]


@dataclass
class BackgroundAsset:
    """Represents a background video loop, texture, or grid overlay."""
    id: str
    filename: str
    path: str
    category: str
    energy_level: str = ENERGY_LOW
    resolution: Tuple[int, int] = (1280, 720)
    duration_s: float = 10.0
    fps: float = 30.0
    media_type: str = "video"  # "video" or "image"
    has_audio: bool = False
    mute_audio: bool = True  # Always mute background tracks to protect narration
    volume: float = 0.0      # Explicit volume for FreeCut timeline clips
    recommended_loop: str = "loop"  # "loop", "pingpong", "freeze_last", "cut"
    brightness: float = 20.0
    tags: List[str] = field(default_factory=list)
    is_duplicate_of: Optional[str] = None
    size_bytes: int = 0
    md5: str = ""

    @property
    def width(self) -> int:
        return self.resolution[0]

    @property
    def height(self) -> int:
        return self.resolution[1]

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["resolution"] = list(self.resolution)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BackgroundAsset:
        d = dict(data)
        if isinstance(d.get("resolution"), (list, tuple)):
            d["resolution"] = (int(d["resolution"][0]), int(d["resolution"][1]))
        return cls(**d)

    def get_timeline_clip_metadata(self, target_duration_s: Optional[float] = None) -> Dict[str, Any]:
        """Returns clip configuration ready for FreeCut project.json track_bg insertion."""
        dur = target_duration_s if target_duration_s is not None else self.duration_s
        return {
            "label": f"BG: {self.category} - {self.filename}",
            "type": self.media_type,
            "path": self.path,
            "volume": 0.0,
            "muted": True,
            "has_audio": self.has_audio,
            "loop": self.recommended_loop,
            "category": self.category,
            "duration_s": dur,
        }


@dataclass
class SFXAsset:
    """Represents a transition sound effect (whoosh / air-woosh)."""
    id: str
    filename: str
    path: str
    kind: str  # "whoosh" or "air_woosh"
    duration_s: float = 1.0
    duration_frames_30fps: int = 30
    peak_offset_ms: float = 150.0
    peak_frame_30fps: int = 5
    rms_energy: float = 0.05
    default_volume: float = -24.0
    native_peak_db: float = 0.0
    default_gain_db: float = -24.0
    tags: List[str] = field(default_factory=list)
    recommended_use: str = "card_entrance"
    size_bytes: int = 0
    md5: str = ""

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SFXAsset:
        return cls(**data)

    def get_timeline_clip_metadata(
        self,
        from_frame: int,
        duration_frames: Optional[int] = None,
        volume: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Returns clip configuration ready for FreeCut project.json track_sfx insertion."""
        dur_f = duration_frames if duration_frames is not None else self.duration_frames_30fps
        vol = volume if volume is not None else self.default_volume
        return {
            "trackId": "track_sfx",
            "from": from_frame,
            "durationInFrames": dur_f,
            "label": self.filename.replace(".mp3", ""),
            "type": "audio",
            "path": self.path,
            "sourceStart": 0.0,
            "sourceEnd": self.duration_s,
            "sourceDuration": self.duration_s,
            "volume": vol,
            "peakOffsetMs": self.peak_offset_ms,
            "peakFrameOffset": self.peak_frame_30fps,
        }


# ==============================================================================
# Master Asset Metadata Registries (Frozen Ground Truth for All 77 BG + 7 SFX)
# ==============================================================================

RAW_BACKGROUND_DEFINITIONS: List[Dict[str, Any]] = [
    {"id": "bg_001", "filename": "1.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 6.01, "fps": 30.0, "has_audio": True, "brightness": 100.2, "tags": ["color_mood", "dynamic_lights", "gradient", "vibrant", "flow", "blue_amber"]},
    {"id": "bg_002", "filename": "10.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 6.41, "fps": 30.0, "has_audio": True, "brightness": 20.6, "tags": ["dark", "minimal", "deep_black", "subtle_gradient", "contrast"]},
    {"id": "bg_003", "filename": "107303-676158761.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1920, 1080), "duration_s": 10.00, "fps": 30.0, "has_audio": False, "brightness": 13.3, "tags": ["dark", "minimal", "1080p", "clean", "deep_space"]},
    {"id": "bg_004", "filename": "107308-676158771_medium.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (2560, 1440), "duration_s": 10.00, "fps": 30.0, "has_audio": False, "brightness": 16.5, "tags": ["dark", "minimal", "1440p", "2k", "clean", "abstract"]},
    {"id": "bg_005", "filename": "107311-676158777.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1920, 1080), "duration_s": 10.00, "fps": 30.0, "has_audio": False, "brightness": 22.0, "tags": ["dark", "minimal", "1080p", "clean", "smooth"]},
    {"id": "bg_006", "filename": "107465-678258871.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1920, 1080), "duration_s": 10.00, "fps": 30.0, "has_audio": False, "brightness": 54.9, "tags": ["color_mood", "1080p", "dynamic_lights", "gradient"]},
    {"id": "bg_007", "filename": "107466-678258874.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1920, 1080), "duration_s": 8.00, "fps": 30.0, "has_audio": False, "brightness": 23.4, "tags": ["dark", "minimal", "1080p", "clean"]},
    {"id": "bg_008", "filename": "11.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 30.05, "fps": 30.0, "has_audio": True, "brightness": 22.8, "tags": ["color_mood", "dynamic_lights", "gradient", "ambient_flow"]},
    {"id": "bg_009", "filename": "12.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 300.00, "fps": 30.0, "has_audio": True, "brightness": 12.9, "tags": ["color_mood", "long_loop", "subtle_color", "ambient"]},
    {"id": "bg_010", "filename": "13.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 300.05, "fps": 30.0, "has_audio": True, "brightness": 20.2, "tags": ["color_mood", "long_loop", "lights", "dynamic"]},
    {"id": "bg_011", "filename": "14.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 5.94, "fps": 30.0, "has_audio": True, "brightness": 15.3, "tags": ["cinematic", "ambient", "smoke", "moody", "atmospheric"]},
    {"id": "bg_012", "filename": "15.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 7.01, "fps": 30.0, "has_audio": True, "brightness": 23.5, "tags": ["dark", "minimal", "deep_black", "contrast"]},
    {"id": "bg_013", "filename": "156354-812591843.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1920, 1080), "duration_s": 5.01, "fps": 30.0, "has_audio": True, "brightness": 40.4, "tags": ["color_mood", "1080p", "dynamic_lights", "flow"]},
    {"id": "bg_014", "filename": "16.mp4", "category": "particles_tech", "energy_level": "high", "resolution": (1280, 720), "duration_s": 60.00, "fps": 30.0, "has_audio": True, "brightness": 7.4, "tags": ["particles", "tech", "digital", "network", "cyber"]},
    {"id": "bg_015", "filename": "17.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 30.00, "fps": 30.0, "has_audio": True, "brightness": 14.4, "tags": ["dark", "minimal", "deep_black", "clean"]},
    {"id": "bg_016", "filename": "18.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 110.02, "fps": 30.0, "has_audio": True, "brightness": 8.2, "tags": ["dark", "minimal", "deep_black", "long_loop"]},
    {"id": "bg_017", "filename": "19.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 83.75, "fps": 30.0, "has_audio": True, "brightness": 38.0, "tags": ["cinematic", "ambient", "slow_motion", "moody"]},
    {"id": "bg_018", "filename": "2 grunge film overlay.mp4", "category": "grunge", "energy_level": "high", "resolution": (1280, 720), "duration_s": 35.02, "fps": 24.0, "has_audio": True, "brightness": 2.6, "tags": ["grunge", "dirt", "industrial", "gritty", "film_overlay", "distressed"]},
    {"id": "bg_019", "filename": "2.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 6.01, "fps": 30.0, "has_audio": True, "brightness": 36.8, "tags": ["cinematic", "ambient", "slow_drift", "haze"]},
    {"id": "bg_020", "filename": "20.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 30.26, "fps": 25.0, "has_audio": True, "brightness": 17.5, "tags": ["dark", "minimal", "deep_black"]},
    {"id": "bg_021", "filename": "25.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 10.05, "fps": 30.0, "has_audio": True, "brightness": 2.5, "tags": ["cinematic", "ambient", "deep_mood", "atmospheric"]},
    {"id": "bg_022", "filename": "26.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 107.3, "tags": ["color_mood", "dynamic_lights", "vibrant", "gold_amber"]},
    {"id": "bg_023", "filename": "27.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 240.05, "fps": 25.0, "has_audio": True, "brightness": 56.9, "tags": ["color_mood", "gradient", "flow", "dynamic"]},
    {"id": "bg_024", "filename": "3.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 6.01, "fps": 30.0, "has_audio": True, "brightness": 20.9, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_025", "filename": "31.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.02, "fps": 30.0, "has_audio": True, "brightness": 39.0, "tags": ["color_mood", "lights", "purple_blue", "flow"]},
    {"id": "bg_026", "filename": "33.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1082, 720), "duration_s": 58.82, "fps": 24.0, "has_audio": True, "brightness": 28.7, "tags": ["dark", "minimal", "clean", "contrast"]},
    {"id": "bg_027", "filename": "34.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 120.00, "fps": 25.0, "has_audio": True, "brightness": 29.8, "tags": ["cinematic", "ambient", "smoke", "moody"]},
    {"id": "bg_028", "filename": "35.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 10.01, "fps": 30.0, "has_audio": True, "brightness": 16.5, "tags": ["dark", "minimal", "deep_black"]},
    {"id": "bg_029", "filename": "36.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 5.02, "fps": 24.0, "has_audio": True, "brightness": 11.6, "tags": ["dark", "minimal", "short_loop"]},
    {"id": "bg_030", "filename": "37.mp4", "category": "particles_tech", "energy_level": "high", "resolution": (1280, 720), "duration_s": 73.28, "fps": 25.0, "has_audio": True, "brightness": 110.1, "tags": ["particles", "tech", "digital", "high_energy", "glowing"]},
    {"id": "bg_031", "filename": "38.mp4", "category": "bright_white", "energy_level": "low", "resolution": (1280, 720), "duration_s": 19.02, "fps": 30.0, "has_audio": True, "brightness": 234.0, "tags": ["bright", "white", "clean", "minimal", "corporate", "light"]},
    {"id": "bg_032", "filename": "39.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 29.91, "fps": 30.0, "has_audio": True, "brightness": 18.3, "tags": ["dark", "minimal", "deep_black", "contrast"]},
    {"id": "bg_033", "filename": "4 Topographic background (1).mp4", "category": "topographic", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 10.01, "fps": 30.0, "has_audio": True, "brightness": 7.9, "tags": ["topographic", "contour", "lines", "map", "vector", "geopolitics", "anime_map"]},
    {"id": "bg_034", "filename": "4.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 7.01, "fps": 30.0, "has_audio": True, "brightness": 55.8, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_035", "filename": "40.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 240.09, "fps": 25.0, "has_audio": True, "brightness": 26.1, "tags": ["color_mood", "flow", "gradient", "long_loop"]},
    {"id": "bg_036", "filename": "41.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 29.91, "fps": 30.0, "has_audio": True, "brightness": 32.1, "tags": ["dark", "minimal", "clean"]},
    {"id": "bg_037", "filename": "42.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 15.05, "fps": 30.0, "has_audio": True, "brightness": 8.9, "tags": ["cinematic", "ambient", "haze", "moody"]},
    {"id": "bg_038", "filename": "43.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 15.05, "fps": 25.0, "has_audio": True, "brightness": 6.8, "tags": ["color_mood", "subtle_color", "ambient"]},
    {"id": "bg_039", "filename": "44.mp4", "category": "bright_white", "energy_level": "low", "resolution": (1280, 720), "duration_s": 111.99, "fps": 30.0, "has_audio": True, "brightness": 224.7, "tags": ["bright", "white", "clean", "minimal", "paper_like", "light"]},
    {"id": "bg_040", "filename": "45.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 58.89, "fps": 30.0, "has_audio": True, "brightness": 4.2, "tags": ["dark", "minimal", "deep_black", "subtle"]},
    {"id": "bg_041", "filename": "46.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 58.61, "fps": 30.0, "has_audio": True, "brightness": 45.5, "tags": ["color_mood", "dynamic_lights", "flow"]},
    {"id": "bg_042", "filename": "47.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 29.98, "fps": 25.0, "has_audio": True, "brightness": 16.4, "tags": ["dark", "minimal", "clean"]},
    {"id": "bg_043", "filename": "48.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 29.98, "fps": 25.0, "has_audio": True, "brightness": 46.8, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_044", "filename": "49.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 29.98, "fps": 25.0, "has_audio": True, "brightness": 35.2, "tags": ["color_mood", "flow", "gradient"]},
    {"id": "bg_045", "filename": "5 Topographic background.mp4", "category": "topographic", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 61.97, "fps": 30.0, "has_audio": True, "brightness": 20.8, "tags": ["topographic", "contour", "lines", "map", "vector", "long_loop"]},
    {"id": "bg_046", "filename": "5.mp4", "category": "particles_tech", "energy_level": "high", "resolution": (1280, 720), "duration_s": 30.00, "fps": 30.0, "has_audio": True, "brightness": 16.3, "tags": ["particles", "tech", "digital", "network"]},
    {"id": "bg_047", "filename": "50.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 29.98, "fps": 25.0, "has_audio": True, "brightness": 22.2, "tags": ["dark", "minimal", "deep_black"]},
    {"id": "bg_048", "filename": "51.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 29.98, "fps": 25.0, "has_audio": True, "brightness": 16.2, "tags": ["dark", "minimal", "clean"]},
    {"id": "bg_049", "filename": "52.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 1784.27, "fps": 30.0, "has_audio": True, "brightness": 55.9, "tags": ["cinematic", "ambient", "ultra_long_loop", "smoke", "atmospheric"]},
    {"id": "bg_050", "filename": "53.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 240.09, "fps": 25.0, "has_audio": True, "brightness": 38.2, "tags": ["color_mood", "gradient", "flow"]},
    {"id": "bg_051", "filename": "54.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 13.37, "fps": 30.0, "has_audio": True, "brightness": 55.5, "tags": ["color_mood", "dynamic_lights", "vibrant"]},
    {"id": "bg_052", "filename": "55.mp4", "category": "topographic", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 10.01, "fps": 30.0, "has_audio": True, "brightness": 7.9, "is_duplicate_of": "4 Topographic background (1).mp4", "tags": ["topographic", "contour", "lines", "map", "vector"]},
    {"id": "bg_053", "filename": "56.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 9.7, "tags": ["color_mood", "subtle_lights", "dark_ambient"]},
    {"id": "bg_054", "filename": "57.mp4", "category": "cinematic_ambient", "energy_level": "low", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 10.4, "tags": ["cinematic", "ambient", "slow_drift", "moody"]},
    {"id": "bg_055", "filename": "58.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 22.2, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_056", "filename": "59.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 17.2, "tags": ["color_mood", "gradient", "flow"]},
    {"id": "bg_057", "filename": "6 -Efeito de filme antigo.mp4", "category": "film_grain", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 80.06, "fps": 25.0, "has_audio": True, "brightness": 3.5, "tags": ["film_grain", "vintage", "retro", "scratches", "dust", "old_film", "recap"]},
    {"id": "bg_058", "filename": "6.mp4", "category": "particles_tech", "energy_level": "high", "resolution": (1280, 720), "duration_s": 120.00, "fps": 24.0, "has_audio": True, "brightness": 88.5, "tags": ["particles", "tech", "glowing", "cyber", "data"]},
    {"id": "bg_059", "filename": "61.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 24.6, "tags": ["color_mood", "dynamic_lights", "ambient"]},
    {"id": "bg_060", "filename": "62.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 20.04, "fps": 30.0, "has_audio": True, "brightness": 17.8, "tags": ["color_mood", "lights", "flow"]},
    {"id": "bg_061", "filename": "63.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 30.05, "fps": 30.0, "has_audio": True, "brightness": 6.3, "tags": ["color_mood", "subtle_lights", "deep_color"]},
    {"id": "bg_062", "filename": "64.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 30.81, "fps": 25.0, "has_audio": True, "brightness": 27.0, "tags": ["dark", "minimal", "clean"]},
    {"id": "bg_063", "filename": "65.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 7.01, "fps": 30.0, "has_audio": True, "brightness": 57.0, "tags": ["color_mood", "dynamic_lights", "vibrant"]},
    {"id": "bg_064", "filename": "66.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 15.00, "fps": 30.0, "has_audio": True, "brightness": 21.7, "tags": ["color_mood", "gradient", "flow"]},
    {"id": "bg_065", "filename": "67.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 90.07, "fps": 30.0, "has_audio": True, "brightness": 26.1, "tags": ["dark", "minimal", "long_loop"]},
    {"id": "bg_066", "filename": "68.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 560.04, "fps": 30.0, "has_audio": True, "brightness": 23.9, "tags": ["color_mood", "ultra_long_loop", "dynamic"]},
    {"id": "bg_067", "filename": "69.mp4", "category": "bright_white", "energy_level": "low", "resolution": (1280, 720), "duration_s": 600.00, "fps": 30.0, "has_audio": True, "brightness": 241.2, "tags": ["bright", "white", "clean", "minimal", "corporate", "light", "long_loop"]},
    {"id": "bg_068", "filename": "7 Crumpled White Paper.mp4", "category": "paper", "energy_level": "low", "resolution": (1920, 1080), "duration_s": 15.17, "fps": 30.0, "has_audio": True, "brightness": 227.6, "tags": ["paper", "crumpled", "texture", "white", "dossier", "document", "editorial", "vox"]},
    {"id": "bg_069", "filename": "7.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 12.17, "fps": 30.0, "has_audio": True, "brightness": 43.9, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_070", "filename": "70.mp4", "category": "dark_minimal", "energy_level": "low", "resolution": (1280, 720), "duration_s": 50.27, "fps": 30.0, "has_audio": True, "brightness": 7.1, "tags": ["dark", "minimal", "deep_black"]},
    {"id": "bg_071", "filename": "71.mp4", "category": "particles_tech", "energy_level": "high", "resolution": (1280, 720), "duration_s": 13.42, "fps": 15.0, "has_audio": True, "brightness": 53.0, "tags": ["particles", "tech", "digital", "network", "cyber"]},
    {"id": "bg_072", "filename": "8 overlay video effect.mp4", "category": "overlays", "energy_level": "medium", "resolution": (1920, 1012), "duration_s": 101.30, "fps": 30.0, "has_audio": True, "brightness": 0.7, "tags": ["overlay", "light_leaks", "atmospheric", "warm", "glow", "particles", "cinematic"]},
    {"id": "bg_073", "filename": "8.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 10.01, "fps": 30.0, "has_audio": True, "brightness": 25.5, "tags": ["color_mood", "dynamic_lights", "gradient"]},
    {"id": "bg_074", "filename": "9 Old FIlm Grain.mp4", "category": "film_grain", "energy_level": "medium", "resolution": (1920, 1080), "duration_s": 10.04, "fps": 25.0, "has_audio": True, "brightness": 3.9, "tags": ["film_grain", "vintage", "retro", "grain", "1080p", "cinema", "flashback"]},
    {"id": "bg_075", "filename": "9.mp4", "category": "color_mood", "energy_level": "medium", "resolution": (1280, 720), "duration_s": 71.89, "fps": 30.0, "has_audio": True, "brightness": 93.7, "tags": ["color_mood", "dynamic_lights", "vibrant"]},
    {"id": "bg_076", "filename": "grade1.png", "category": "grids", "energy_level": "low", "resolution": (1919, 1079), "duration_s": 0.0, "fps": 0.0, "media_type": "image", "has_audio": False, "recommended_loop": "freeze_last", "brightness": 7.8, "tags": ["grid", "blueprint", "hud", "technical", "transparent", "coordinates"]},
    {"id": "bg_077", "filename": "grade2.png", "category": "grids", "energy_level": "low", "resolution": (1919, 1079), "duration_s": 0.0, "fps": 0.0, "media_type": "image", "has_audio": False, "recommended_loop": "freeze_last", "brightness": 20.2, "tags": ["grid", "blueprint", "hud", "technical", "transparent", "coordinates"]},
]

# ── Built-in SFX Registry (Audio characteristics for the 7 transition files) ──
SFX_REGISTRY = [
    {
        "id": "sfx_whoosh_1",
        "filename": "Whoosh 1.mp3",
        "kind": SFX_KIND_WHOOSH,
        "duration_s": 0.862,
        "duration_frames_30fps": 26,
        "peak_offset_ms": 210.7,
        "peak_frame_30fps": 6,
        "rms_energy": 0.0768,
        "native_peak_db": -5.0,
        "default_gain_db": -24.0,
        "default_volume": -24.0,
        "tags": ["standard", "whoosh", "transition", "camera_cut", "fast", "clean"],
        "recommended_use": "camera_cut",
    },
    {
        "id": "sfx_whoosh_2",
        "filename": "Whoosh 2.mp3",
        "kind": SFX_KIND_WHOOSH,
        "duration_s": 0.888,
        "duration_frames_30fps": 27,
        "peak_offset_ms": 146.0,
        "peak_frame_30fps": 5,
        "rms_energy": 0.0537,
        "native_peak_db": -8.8,
        "default_gain_db": -20.0,
        "default_volume": -20.0,
        "tags": ["quick", "snappy", "whoosh", "card_entrance", "fast_pan", "accent"],
        "recommended_use": "card_entrance",
    },
    {
        "id": "sfx_whoosh_7",
        "filename": "Whoosh 7.mp3",
        "kind": SFX_KIND_WHOOSH,
        "duration_s": 0.940,
        "duration_frames_30fps": 29,
        "peak_offset_ms": 294.8,
        "peak_frame_30fps": 9,
        "rms_energy": 0.2790,
        "native_peak_db": 0.0,
        "default_gain_db": -30.0,
        "default_volume": -30.0,
        "tags": ["heavy", "cinematic", "dramatic", "impact", "act_transition", "power"],
        "recommended_use": "dramatic_transition",
    },
    {
        "id": "sfx_air_woosh_1",
        "filename": "air-woosh-1.mp3",
        "kind": SFX_KIND_AIR_WOOSH,
        "duration_s": 1.321,
        "duration_frames_30fps": 40,
        "peak_offset_ms": 129.3,
        "peak_frame_30fps": 4,
        "rms_energy": 0.0373,
        "native_peak_db": -11.3,
        "default_gain_db": -17.0,
        "default_volume": -17.0,
        "tags": ["soft", "atmospheric", "air", "floating", "subtle", "gentle"],
        "recommended_use": "floating_card",
    },
    {
        "id": "sfx_air_woosh_2",
        "filename": "air-woosh-2.mp3",
        "kind": SFX_KIND_AIR_WOOSH,
        "duration_s": 1.321,
        "duration_frames_30fps": 40,
        "peak_offset_ms": 176.3,
        "peak_frame_30fps": 5,
        "rms_energy": 0.0769,
        "native_peak_db": -5.2,
        "default_gain_db": -24.0,
        "default_volume": -24.0,
        "tags": ["medium", "air", "wind", "slide", "document", "paper"],
        "recommended_use": "slide_transition",
    },
    {
        "id": "sfx_air_woosh_3",
        "filename": "air-woosh-3.mp3",
        "kind": SFX_KIND_AIR_WOOSH,
        "duration_s": 1.321,
        "duration_frames_30fps": 40,
        "peak_offset_ms": 127.6,
        "peak_frame_30fps": 4,
        "rms_energy": 0.0366,
        "native_peak_db": -7.8,
        "default_gain_db": -21.0,
        "default_volume": -21.0,
        "tags": ["gentle", "flutter", "badge", "info_badge", "tag", "pop"],
        "recommended_use": "info_badge",
    },
    {
        "id": "sfx_air_woosh_4",
        "filename": "air-woosh-4.mp3",
        "kind": SFX_KIND_AIR_WOOSH,
        "duration_s": 1.321,
        "duration_frames_30fps": 40,
        "peak_offset_ms": 226.8,
        "peak_frame_30fps": 7,
        "rms_energy": 0.0549,
        "native_peak_db": -9.3,
        "default_gain_db": -19.0,
        "default_volume": -19.0,
        "tags": ["exit", "breeze", "dissipate", "card_exit", "out", "vanish"],
        "recommended_use": "card_exit",
    },
]

RAW_SFX_DEFINITIONS: List[Dict[str, Any]] = SFX_REGISTRY


class AssetCatalog:
    """
    Central Asset Catalog & Registry for backgrounds and sound effects.

    Provides high-performance querying, smart fallback, audio stream muting,
    and automatic path discovery across external downloads and local workspace folders.
    """

    def __init__(
        self,
        bg_dir: Optional[str] = None,
        sfx_dir: Optional[str] = None,
        auto_index: bool = True,
    ):
        self._custom_bg_dir = bg_dir
        self._custom_sfx_dir = sfx_dir
        self._backgrounds: Dict[str, BackgroundAsset] = {}
        self._sfx: Dict[str, SFXAsset] = {}
        self._bg_by_filename: Dict[str, BackgroundAsset] = {}
        self._sfx_by_filename: Dict[str, SFXAsset] = {}
        self._bg_search_dirs: List[str] = []
        self._sfx_search_dirs: List[str] = []

        if auto_index:
            self.reload()

    def _resolve_search_directories(self) -> None:
        """Determines search directories in priority order."""
        bg_candidates = []
        if self._custom_bg_dir and os.path.isdir(self._custom_bg_dir):
            bg_candidates.append(os.path.abspath(self._custom_bg_dir))

        env_bg = os.getenv("BACKGROUNDS_DIR") or os.getenv("ASSETS_BG_DIR")
        if env_bg and os.path.isdir(env_bg):
            bg_candidates.append(os.path.abspath(env_bg))

        if os.path.isdir(DEFAULT_BG_DIR):
            bg_candidates.append(os.path.abspath(DEFAULT_BG_DIR))

        if os.path.isdir(LOCAL_BG_DIR):
            bg_candidates.append(os.path.abspath(LOCAL_BG_DIR))

        # Additional local fallback paths
        ws_root = os.path.dirname(os.path.abspath(__file__))
        for cand in [
            os.path.join(ws_root, "assets", "BACKGROUNDS"),
            os.path.join(ws_root, "assets"),
        ]:
            if os.path.isdir(cand) and cand not in bg_candidates:
                bg_candidates.append(os.path.abspath(cand))

        self._bg_search_dirs = bg_candidates

        sfx_candidates = []
        if self._custom_sfx_dir and os.path.isdir(self._custom_sfx_dir):
            sfx_candidates.append(os.path.abspath(self._custom_sfx_dir))

        env_sfx = os.getenv("SFX_DIR") or os.getenv("ASSETS_SFX_DIR")
        if env_sfx and os.path.isdir(env_sfx):
            sfx_candidates.append(os.path.abspath(env_sfx))

        if os.path.isdir(DEFAULT_SFX_DIR):
            sfx_candidates.append(os.path.abspath(DEFAULT_SFX_DIR))

        if os.path.isdir(LOCAL_SFX_DIR) and os.path.abspath(LOCAL_SFX_DIR) not in sfx_candidates:
            sfx_candidates.append(os.path.abspath(LOCAL_SFX_DIR))

        for cand in [
            os.path.join(ws_root, "assets", "trandição de saida e entrada"),
            os.path.join(ws_root, "assets", "transitions"),
        ]:
            if os.path.isdir(cand) and cand not in sfx_candidates:
                sfx_candidates.append(os.path.abspath(cand))

        self._sfx_search_dirs = sfx_candidates

    def _find_file_path(self, filename: str, search_dirs: List[str], default_dir: str) -> str:
        """Finds the absolute path of a file across candidate search directories."""
        for d in search_dirs:
            p = os.path.join(d, filename)
            if os.path.isfile(p):
                return os.path.abspath(p)
        # Fallback to default directory even if not currently mounted
        return os.path.abspath(os.path.join(default_dir, filename))

    def reload(self) -> None:
        """Reloads and indexes all background and SFX assets."""
        self._resolve_search_directories()
        self._backgrounds.clear()
        self._bg_by_filename.clear()
        self._sfx.clear()
        self._sfx_by_filename.clear()

        # 1. Index Backgrounds
        for raw in RAW_BACKGROUND_DEFINITIONS:
            item_data = copy.deepcopy(raw)
            fn = item_data["filename"]
            resolved_path = self._find_file_path(
                fn,
                self._bg_search_dirs,
                DEFAULT_BG_DIR if os.path.isdir(DEFAULT_BG_DIR) else LOCAL_BG_DIR,
            )
            item_data["path"] = resolved_path
            
            # Populate file size if exists
            if os.path.isfile(resolved_path):
                item_data["size_bytes"] = os.path.getsize(resolved_path)

            bg = BackgroundAsset.from_dict(item_data)
            self._backgrounds[bg.id] = bg
            self._bg_by_filename[bg.filename] = bg

        # 2. Index SFX
        for raw in RAW_SFX_DEFINITIONS:
            item_data = copy.deepcopy(raw)
            fn = item_data["filename"]
            resolved_path = self._find_file_path(
                fn,
                self._sfx_search_dirs,
                DEFAULT_SFX_DIR if os.path.isdir(DEFAULT_SFX_DIR) else LOCAL_SFX_DIR,
            )
            item_data["path"] = resolved_path
            
            if os.path.isfile(resolved_path):
                item_data["size_bytes"] = os.path.getsize(resolved_path)

            sfx = SFXAsset.from_dict(item_data)
            self._sfx[sfx.id] = sfx
            self._sfx_by_filename[sfx.filename] = sfx

        logger.info(
            "AssetCatalog indexed: %d backgrounds, %d SFX across %d categories.",
            len(self._backgrounds),
            len(self._sfx),
            len(self.get_categories()),
        )

    # --------------------------------------------------------------------------
    # Background Query Methods
    # --------------------------------------------------------------------------

    def get_background(
        self,
        category: Optional[str] = None,
        energy: Optional[str] = None,
        tags: Optional[Union[str, Sequence[str]]] = None,
        mood: Optional[str] = None,
        min_duration_s: Optional[float] = None,
        exclude_ids: Optional[Sequence[str]] = None,
        exclude_filenames: Optional[Sequence[str]] = None,
        media_type: Optional[str] = None,
        fallback: bool = True,
        deterministic_seed: Optional[Union[int, str]] = None,
    ) -> Optional[BackgroundAsset]:
        """
        Retrieves the most suitable background asset matching criteria.

        Args:
            category: Visual category name (e.g. 'topographic', 'paper', 'dark_minimal', 'color_mood', 'random', 'any').
            energy: Energy level ('low', 'medium', 'high').
            tags: Tag or list of tags to filter by.
            mood: Mood shorthand ('dark', 'bright', 'vibrant', 'ambient', 'tech').
            min_duration_s: Minimum duration required in seconds.
            exclude_ids: Asset IDs to exclude (prevents repetition).
            exclude_filenames: Filenames to exclude.
            media_type: Filter by 'video' or 'image'.
            fallback: If True and no exact match found, returns best available fallback.
            deterministic_seed: Seed for reproducible random selection.

        Returns:
            BackgroundAsset object or None if no match and fallback=False.
        """
        candidates = list(self._backgrounds.values())

        # Filter exclusions
        ex_ids = set(exclude_ids or [])
        ex_fns = set(exclude_filenames or [])
        candidates = [b for b in candidates if b.id not in ex_ids and b.filename not in ex_fns]

        if not candidates and fallback:
            # If all candidates excluded, reset pool
            candidates = list(self._backgrounds.values())

        # Normalize category
        cat_norm = category.strip().lower() if category else None
        if cat_norm in ("any", "random", "all", "*"):
            cat_norm = None

        # Handle mood alias mapping
        if mood and not cat_norm:
            mood_lower = mood.strip().lower()
            if mood_lower in ("dark", "noir", "deep"):
                cat_norm = CATEGORY_DARK_MINIMAL
            elif mood_lower in ("bright", "clean", "white", "corporate"):
                cat_norm = CATEGORY_BRIGHT_WHITE
            elif mood_lower in ("vibrant", "color", "lights", "dynamic"):
                cat_norm = CATEGORY_COLOR_MOOD
            elif mood_lower in ("ambient", "smoke", "slow", "moody"):
                cat_norm = CATEGORY_CINEMATIC_AMBIENT
            elif mood_lower in ("tech", "cyber", "digital", "matrix"):
                cat_norm = CATEGORY_PARTICLES_TECH
            elif mood_lower in ("retro", "vintage", "old", "flashback"):
                cat_norm = CATEGORY_FILM_GRAIN
            elif mood_lower in ("editorial", "paper", "dossier", "document"):
                cat_norm = CATEGORY_PAPER
            elif mood_lower in ("map", "contour", "geo"):
                cat_norm = CATEGORY_TOPOGRAPHIC

        # Filter by media_type
        if media_type:
            mt_norm = media_type.strip().lower()
            candidates = [b for b in candidates if b.media_type == mt_norm]

        # Primary filter match
        matched = candidates

        if cat_norm:
            matched = [b for b in matched if b.category == cat_norm]

        if energy:
            en_norm = energy.strip().lower()
            matched = [b for b in matched if b.energy_level == en_norm]

        if min_duration_s is not None and min_duration_s > 0:
            matched = [b for b in matched if b.duration_s >= min_duration_s]

        if tags:
            tag_list = [tags.lower()] if isinstance(tags, str) else [t.lower() for t in tags]
            matched = [
                b for b in matched
                if any(t in [bg_tag.lower() for bg_tag in b.tags] for t in tag_list)
            ]

        # If matches found, select
        rng = random.Random(deterministic_seed) if deterministic_seed is not None else random
        if matched:
            return rng.choice(matched)

        # Fallback tier 1: match category only
        if fallback and cat_norm:
            cat_fallback = [b for b in candidates if b.category == cat_norm]
            if cat_fallback:
                return rng.choice(cat_fallback)

        # Fallback tier 2: dark_minimal (safest universal card background)
        if fallback:
            dark_fallback = [b for b in candidates if b.category == CATEGORY_DARK_MINIMAL]
            if dark_fallback:
                return rng.choice(dark_fallback)
            if candidates:
                return rng.choice(candidates)

        return None

    def get_background_path(
        self,
        category: Optional[str] = None,
        energy: Optional[str] = None,
        tags: Optional[Union[str, Sequence[str]]] = None,
        fallback: bool = True,
    ) -> Optional[str]:
        """Convenience method returning absolute path string directly."""
        bg = self.get_background(category=category, energy=energy, tags=tags, fallback=fallback)
        return bg.path if bg else None

    def get_background_by_id(self, asset_id: str) -> Optional[BackgroundAsset]:
        """Returns background asset by exact ID (e.g. 'bg_001')."""
        return self._backgrounds.get(asset_id)

    def get_background_by_filename(self, filename: str) -> Optional[BackgroundAsset]:
        """Returns background asset by filename (e.g. '1.mp4' or 'grade1.png')."""
        return self._bg_by_filename.get(filename)

    def list_all_backgrounds(
        self,
        category: Optional[str] = None,
        energy: Optional[str] = None,
        media_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[BackgroundAsset]:
        """Returns filtered list of background assets."""
        results = list(self._backgrounds.values())
        if category and category.lower() not in ("any", "all", "*"):
            cat_norm = category.lower()
            results = [b for b in results if b.category == cat_norm]
        if energy:
            en_norm = energy.lower()
            results = [b for b in results if b.energy_level == en_norm]
        if media_type:
            mt_norm = media_type.lower()
            results = [b for b in results if b.media_type == mt_norm]
        if tag:
            t_norm = tag.lower()
            results = [b for b in results if any(t_norm == bt.lower() for bt in b.tags)]
        return results

    # --------------------------------------------------------------------------
    # SFX Query Methods
    # --------------------------------------------------------------------------

    def get_sfx(
        self,
        kind: Optional[str] = None,
        event_type: Optional[str] = None,
        intensity: Optional[str] = None,
        tags: Optional[Union[str, Sequence[str]]] = None,
        fallback: bool = True,
        deterministic_seed: Optional[Union[int, str]] = None,
    ) -> Optional[SFXAsset]:
        """
        Retrieves the most suitable transition sound effect (whoosh / air-woosh).

        Args:
            kind: 'whoosh' or 'air_woosh' (or 'random', 'any').
            event_type: Editing event type:
                - 'card_entrance' -> Whoosh 1 (Fast whip snap)
                - 'camera_cut' -> Whoosh 2 (Crisp instant swipe)
                - 'dramatic_transition' -> Whoosh 7 (Heavy cinematic impact)
                - 'floating_card' -> air-woosh-1 (Soft atmospheric air)
                - 'slide_transition' -> air-woosh-2 (Medium air swipe)
                - 'info_badge' -> air-woosh-3 (Gentle flutter)
                - 'card_exit' -> air-woosh-4 (Exit breeze)
            intensity: 'soft', 'medium', 'heavy' / 'high'.
            tags: Tag or list of tags to filter by.
            fallback: Fallback to another SFX if exact match not found.
            deterministic_seed: Seed for reproducible random selection.

        Returns:
            SFXAsset object or None.
        """
        candidates = list(self._sfx.values())
        if not candidates:
            return None

        # 1. Direct event_type routing
        if event_type:
            ev_norm = event_type.strip().lower()
            ev_map = {
                "card_entrance": "sfx_whoosh_1",
                "entrance": "sfx_whoosh_1",
                "whip": "sfx_whoosh_1",
                "camera_cut": "sfx_whoosh_2",
                "cut": "sfx_whoosh_2",
                "scene_transition": "sfx_whoosh_2",
                "swipe": "sfx_whoosh_2",
                "dramatic_transition": "sfx_whoosh_7",
                "heavy_impact": "sfx_whoosh_7",
                "act_transition": "sfx_whoosh_7",
                "dramatic": "sfx_whoosh_7",
                "floating_card": "sfx_air_woosh_1",
                "soft_entrance": "sfx_air_woosh_1",
                "floating": "sfx_air_woosh_1",
                "slide_transition": "sfx_air_woosh_2",
                "slide": "sfx_air_woosh_2",
                "document": "sfx_air_woosh_2",
                "info_badge": "sfx_air_woosh_3",
                "badge": "sfx_air_woosh_3",
                "info_card": "sfx_air_woosh_3",
                "tag": "sfx_air_woosh_3",
                "card_exit": "sfx_air_woosh_4",
                "exit": "sfx_air_woosh_4",
                "dissipate": "sfx_air_woosh_4",
                "out": "sfx_air_woosh_4",
            }
            target_id = ev_map.get(ev_norm)
            if target_id and target_id in self._sfx:
                return self._sfx[target_id]

        # 2. Filter by kind
        if kind and kind.lower() not in ("any", "random", "all", "*"):
            k_norm = kind.strip().lower()
            candidates = [s for s in candidates if s.kind == k_norm]

        # 3. Filter by intensity
        if intensity:
            int_norm = intensity.strip().lower()
            if int_norm in ("heavy", "high", "strong"):
                candidates = [s for s in candidates if s.id == "sfx_whoosh_7" or s.rms_energy >= 0.15]
            elif int_norm in ("soft", "low", "gentle"):
                candidates = [s for s in candidates if s.kind == SFX_KIND_AIR_WOOSH and s.rms_energy < 0.05]
            elif int_norm in ("medium", "mid"):
                candidates = [s for s in candidates if 0.04 <= s.rms_energy <= 0.10]

        # 4. Filter by tags
        if tags:
            tag_list = [tags.lower()] if isinstance(tags, str) else [t.lower() for t in tags]
            candidates = [
                s for s in candidates
                if any(t in [st.lower() for st in s.tags] for t in tag_list)
            ]

        rng = random.Random(deterministic_seed) if deterministic_seed is not None else random
        if candidates:
            return rng.choice(candidates)

        if fallback and self._sfx:
            return rng.choice(list(self._sfx.values()))

        return None

    def get_sfx_path_and_volume(
        self,
        event_type: Optional[str] = None,
        kind: Optional[str] = None,
        intensity: Optional[str] = None,
        fallback: bool = True,
    ) -> Tuple[Optional[str], float]:
        """
        Convenience query returning (sfx_filepath, default_volume) tuple.
        """
        sfx = self.get_sfx(kind=kind, event_type=event_type, intensity=intensity, fallback=fallback)
        if sfx:
            return sfx.path, sfx.default_volume
        return None, 0.42

    def get_sfx_by_id(self, asset_id: str) -> Optional[SFXAsset]:
        """Returns SFX asset by exact ID (e.g. 'sfx_whoosh_1')."""
        return self._sfx.get(asset_id)

    def get_sfx_by_filename(self, filename: str) -> Optional[SFXAsset]:
        """Returns SFX asset by filename (e.g. 'Whoosh 1.mp3')."""
        return self._sfx_by_filename.get(filename)

    def list_all_sfx(
        self,
        kind: Optional[str] = None,
        recommended_use: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[SFXAsset]:
        """Returns filtered list of SFX assets."""
        results = list(self._sfx.values())
        if kind and kind.lower() not in ("any", "all", "*"):
            k_norm = kind.lower()
            results = [s for s in results if s.kind == k_norm]
        if recommended_use:
            ru_norm = recommended_use.lower()
            results = [s for s in results if s.recommended_use == ru_norm]
        if tag:
            t_norm = tag.lower()
            results = [s for s in results if any(t_norm == st.lower() for st in s.tags)]
        return results

    # --------------------------------------------------------------------------
    # Catalog Introspection & Metadata Helpers
    # --------------------------------------------------------------------------

    def get_categories(self) -> List[str]:
        """Returns list of distinct background categories present in catalog."""
        return sorted(list({b.category for b in self._backgrounds.values()}))

    def get_energy_levels(self) -> List[str]:
        """Returns available energy levels."""
        return list(ALL_ENERGY_LEVELS)

    def get_sfx_kinds(self) -> List[str]:
        """Returns available SFX kinds."""
        return list(ALL_SFX_KINDS)

    def get_sfx_events(self) -> List[str]:
        """Returns standard event types supported by get_sfx."""
        return [
            "card_entrance",
            "camera_cut",
            "dramatic_transition",
            "floating_card",
            "slide_transition",
            "info_badge",
            "card_exit",
        ]

    def verify_all(self) -> Dict[str, Any]:
        """
        Runs comprehensive integrity and health check on catalog items.
        """
        bg_total = len(self._backgrounds)
        bg_existing = sum(1 for b in self._backgrounds.values() if b.exists())
        bg_with_audio = sum(1 for b in self._backgrounds.values() if b.has_audio)
        bg_muted = sum(1 for b in self._backgrounds.values() if b.mute_audio and b.volume == 0.0)

        sfx_total = len(self._sfx)
        sfx_existing = sum(1 for s in self._sfx.values() if s.exists())

        return {
            "status": "ok" if (bg_total == 77 and sfx_total == 7) else "partial",
            "backgrounds": {
                "total_indexed": bg_total,
                "files_found_on_disk": bg_existing,
                "with_embedded_audio": bg_with_audio,
                "properly_muted_flags": bg_muted,
                "categories_count": len(self.get_categories()),
                "search_dirs": self._bg_search_dirs,
            },
            "sfx": {
                "total_indexed": sfx_total,
                "files_found_on_disk": sfx_existing,
                "kinds": self.get_sfx_kinds(),
                "search_dirs": self._sfx_search_dirs,
            },
        }

    def sync_to_local_workspace(
        self,
        target_dir: Optional[str] = None,
        copy_mode: str = "copy",
    ) -> Dict[str, int]:
        """
        Copies or symlinks assets into local workspace `assets/backgrounds` and `assets/sfx`.
        Provides self-contained portability when moving projects across machines.
        """
        ws_root = target_dir or os.path.dirname(os.path.abspath(__file__))
        dest_bg = os.path.join(ws_root, "assets", "backgrounds")
        dest_sfx = os.path.join(ws_root, "assets", "sfx")

        os.makedirs(dest_bg, exist_ok=True)
        os.makedirs(dest_sfx, exist_ok=True)

        copied_bg = 0
        copied_sfx = 0

        for bg in self._backgrounds.values():
            if bg.exists():
                dst = os.path.join(dest_bg, bg.filename)
                if not os.path.exists(dst):
                    if copy_mode == "symlink":
                        try:
                            os.symlink(bg.path, dst)
                        except Exception:
                            shutil.copy2(bg.path, dst)
                    else:
                        shutil.copy2(bg.path, dst)
                    copied_bg += 1

        for sfx in self._sfx.values():
            if sfx.exists():
                dst = os.path.join(dest_sfx, sfx.filename)
                if not os.path.exists(dst):
                    if copy_mode == "symlink":
                        try:
                            os.symlink(sfx.path, dst)
                        except Exception:
                            shutil.copy2(sfx.path, dst)
                    else:
                        shutil.copy2(sfx.path, dst)
                    copied_sfx += 1

        self.reload()
        return {"synced_backgrounds": copied_bg, "synced_sfx": copied_sfx}

    def to_dict(self) -> Dict[str, Any]:
        """Serializes complete catalog metadata into a dictionary."""
        return {
            "version": "1.0.0",
            "total_backgrounds": len(self._backgrounds),
            "total_sfx": len(self._sfx),
            "backgrounds": [b.to_dict() for b in self._backgrounds.values()],
            "sfx": [s.to_dict() for s in self._sfx.values()],
        }

    def save_manifest(self, filepath: Optional[str] = None) -> str:
        """Exports catalog registry to JSON manifest file."""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "asset_manifest.json")
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath


# ==============================================================================
# Global Singleton & Convenience Functions
# ==============================================================================

_GLOBAL_CATALOG: Optional[AssetCatalog] = None


def get_catalog(
    bg_dir: Optional[str] = None,
    sfx_dir: Optional[str] = None,
    force_reload: bool = False,
) -> AssetCatalog:
    """Returns the shared global AssetCatalog instance."""
    global _GLOBAL_CATALOG
    if _GLOBAL_CATALOG is None or force_reload or bg_dir or sfx_dir:
        _GLOBAL_CATALOG = AssetCatalog(bg_dir=bg_dir, sfx_dir=sfx_dir, auto_index=True)
    return _GLOBAL_CATALOG


def get_background(
    category: Optional[str] = None,
    energy: Optional[str] = None,
    tags: Optional[Union[str, Sequence[str]]] = None,
    mood: Optional[str] = None,
    min_duration_s: Optional[float] = None,
    exclude_ids: Optional[Sequence[str]] = None,
    fallback: bool = True,
    deterministic_seed: Optional[Union[int, str]] = None,
) -> Optional[BackgroundAsset]:
    """Retrieves a background asset using the global catalog."""
    return get_catalog().get_background(
        category=category,
        energy=energy,
        tags=tags,
        mood=mood,
        min_duration_s=min_duration_s,
        exclude_ids=exclude_ids,
        fallback=fallback,
        deterministic_seed=deterministic_seed,
    )


def get_background_path(
    category: Optional[str] = None,
    energy: Optional[str] = None,
    tags: Optional[Union[str, Sequence[str]]] = None,
    fallback: bool = True,
) -> Optional[str]:
    """Retrieves the file path of a background asset."""
    return get_catalog().get_background_path(
        category=category, energy=energy, tags=tags, fallback=fallback
    )


def get_sfx(
    kind: Optional[str] = None,
    event_type: Optional[str] = None,
    intensity: Optional[str] = None,
    tags: Optional[Union[str, Sequence[str]]] = None,
    fallback: bool = True,
    deterministic_seed: Optional[Union[int, str]] = None,
) -> Optional[SFXAsset]:
    """Retrieves a sound effect asset using the global catalog."""
    return get_catalog().get_sfx(
        kind=kind,
        event_type=event_type,
        intensity=intensity,
        tags=tags,
        fallback=fallback,
        deterministic_seed=deterministic_seed,
    )


def get_sfx_path_and_volume(
    event_type: Optional[str] = None,
    kind: Optional[str] = None,
    intensity: Optional[str] = None,
    fallback: bool = True,
) -> Tuple[Optional[str], float]:
    """Retrieves (sfx_filepath, default_volume) tuple using the global catalog."""
    return get_catalog().get_sfx_path_and_volume(
        event_type=event_type, kind=kind, intensity=intensity, fallback=fallback
    )


def list_all_backgrounds(
    category: Optional[str] = None,
    energy: Optional[str] = None,
    media_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[BackgroundAsset]:
    """Lists all background assets matching filters."""
    return get_catalog().list_all_backgrounds(
        category=category, energy=energy, media_type=media_type, tag=tag
    )


def get_background_by_id(asset_id: str) -> Optional[BackgroundAsset]:
    """Retrieves a background asset by its ID."""
    return get_catalog().get_background_by_id(asset_id)


def get_background_by_filename(filename: str) -> Optional[BackgroundAsset]:
    """Retrieves a background asset by its filename."""
    return get_catalog().get_background_by_filename(filename)


def get_sfx_by_id(asset_id: str) -> Optional[SFXAsset]:
    """Retrieves an SFX asset by its ID."""
    return get_catalog().get_sfx_by_id(asset_id)


def get_sfx_by_filename(filename: str) -> Optional[SFXAsset]:
    """Retrieves an SFX asset by its filename."""
    return get_catalog().get_sfx_by_filename(filename)


def list_all_sfx(
    kind: Optional[str] = None,
    recommended_use: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[SFXAsset]:
    """Lists all SFX assets matching filters."""
    return get_catalog().list_all_sfx(
        kind=kind, recommended_use=recommended_use, tag=tag
    )


if __name__ == "__main__":
    catalog = get_catalog()
    report = catalog.verify_all()
    print("Asset Catalog Verification Report:")
    print(json.dumps(report, indent=2))
    
    # Save manifest
    manifest_path = catalog.save_manifest()
    print(f"\nManifest saved to: {manifest_path}")
