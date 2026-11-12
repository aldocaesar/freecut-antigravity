import os
import re
import sys
import json
import math
import uuid
import time
import glob
import zipfile
import hashlib
import random
import argparse
import subprocess
import urllib.request
import urllib.parse
import shutil
import ssl
import copy
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import asset_catalog
import editorial_engine


# ── Global Constants ──────────────────────────────────────────
CANVAS_W = 1920
CANVAS_H = 1080
FPS = 30

TRACKS = [
    {
        "id": "track_text",
        "name": "Text / Legend",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 0,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_7",
        "name": "Foreground 7",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 1,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_6",
        "name": "Foreground 6",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 2,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_5",
        "name": "Foreground 5",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 3,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_4",
        "name": "Foreground 4",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 4,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_3",
        "name": "Foreground 3",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 5,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_2",
        "name": "Foreground 2",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 6,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_fg_1",
        "name": "Foreground 1",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 7,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_anchor",
        "name": "Anchor Image",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 8,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_bg",
        "name": "Background",
        "kind": "video",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": True,
        "solo": False,
        "order": 9,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_sfx",
        "name": "Sound Effects",
        "kind": "audio",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 10,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_audio",
        "name": "Audio",
        "kind": "audio",
        "height": 100,
        "locked": False,
        "visible": True,
        "muted": False,
        "solo": False,
        "order": 11,
        "syncLock": True,
        "volume": 0
    }
]

# ── Env Loader ────────────────────────────────────────────────
def _ensure_ffmpeg_on_path():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    local_app = os.environ.get("LOCALAPPDATA", "")
    for pat in [
        os.path.join(local_app, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]:
        matches = glob.glob(pat, recursive=True)
        if matches:
            os.environ["PATH"] = os.path.dirname(matches[0]) + os.pathsep + os.environ.get("PATH", "")
            break


_ensure_ffmpeg_on_path()


def load_env(project_dir):
    """Loads variables from .env in the project directory, repo root, or cwd, and ensures FFmpeg is on PATH."""
    _ensure_ffmpeg_on_path()

    repo_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    for dotenv_path in [os.path.join(project_dir, ".env"), repo_env, ".env"]:
        if os.path.exists(dotenv_path):
            print(f"  [Env] Carregando variáveis de: {dotenv_path}")
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")
            break

    # Log recognized API keys status
    api_keys = ["PIXABAY_API_KEY", "PEXELS_API_KEY", "TMDB_API_KEY"]
    for k in api_keys:
        val = os.environ.get(k)
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
            print(f"  [Env] {k}: configurada ({masked})")

# ── Utility Functions ──────────────────────────────────────────
def get_uid():
    return str(uuid.uuid4())

def ms_to_frames(ms):
    return int(round((ms / 1000.0) * FPS))

def compute_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def norm_to_px(norm_x, norm_y):
    return int(norm_x * CANVAS_W), int(norm_y * CANVAS_H)

SUPPORTED_AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus")


def detect_mime(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.mkv': 'video/x-matroska',
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4',
        '.aac': 'audio/aac', '.ogg': 'audio/ogg', '.flac': 'audio/flac', '.opus': 'audio/opus',
        '.json': 'application/json', '.lottie': 'application/octet-stream'
    }.get(ext, 'application/octet-stream')


def find_narration_audio(project_dir):
    """Finds the primary narration audio file in `project_dir` across all common formats."""
    candidates = []
    for ext in SUPPORTED_AUDIO_EXTS:
        candidates.extend(sorted(glob.glob(os.path.join(project_dir, f"*{ext}"))))
    if not candidates:
        return None
    # Prefer files explicitly named narration/audio/voz if multiple exist
    for c in candidates:
        stem = os.path.splitext(os.path.basename(c))[0].lower()
        if any(k in stem for k in ("narration", "narracao", "audio", "voz", "voice")):
            return c
    return candidates[0]


def load_words_normalized(words_path):
    """
    Loads `words.json` whether formatted as a flat list `[{word, start_ms, end_ms}]`
    or a Whisper dict `{"words": [...], "segments": [...]}` with float-second `start`/`end`.
    """
    if not os.path.exists(words_path):
        return []
    try:
        with open(words_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []

    raw_list = []
    if isinstance(raw, list):
        raw_list = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("words"), list):
            raw_list = raw["words"]
        elif isinstance(raw.get("segments"), list):
            for seg in raw["segments"]:
                if isinstance(seg, dict) and isinstance(seg.get("words"), list):
                    raw_list.extend(seg["words"])

    out = []
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        w_txt = str(entry.get("word") or entry.get("text") or "").strip()
        if not w_txt:
            continue
        s_ms = entry.get("start_ms")
        e_ms = entry.get("end_ms")
        if s_ms is None and entry.get("start") is not None:
            try:
                s_ms = int(round(float(entry["start"]) * 1000.0))
            except (ValueError, TypeError):
                s_ms = None
        if e_ms is None and entry.get("end") is not None:
            try:
                e_ms = int(round(float(entry["end"]) * 1000.0))
            except (ValueError, TypeError):
                e_ms = None
        if s_ms is not None and e_ms is not None:
            out.append({"word": w_txt, "start_ms": int(s_ms), "end_ms": int(e_ms)})
    return out

def find_matching_lottie(project_dir, query):
    lotties_dir = os.path.join(project_dir, "assets", "lotties")
    global_lotties_dir = os.path.join(".", "assets", "lotties")
    
    target_dir = lotties_dir if os.path.exists(lotties_dir) else (global_lotties_dir if os.path.exists(global_lotties_dir) else None)
    if not target_dir:
        return None
        
    query_clean = query.lower().strip()
    lottie_files = glob.glob(os.path.join(target_dir, "*.json")) + glob.glob(os.path.join(target_dir, "*.lottie"))
    if not lottie_files:
        return None
        
    lottie_files.sort(key=lambda x: len(os.path.splitext(os.path.basename(x))[0]), reverse=True)
    
    words = re.findall(r'\b\w+\b', query_clean)
    for lottie_path in lottie_files:
        name = os.path.splitext(os.path.basename(lottie_path))[0].lower()
        name_words = re.findall(r'\b\w+\b', name.replace("-", " ").replace("_", " "))
        if all(nw in words for nw in name_words):
            return lottie_path
            
    return None

def get_lottie_dimensions(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return int(data.get("w", 1920)), int(data.get("h", 1080))
    except Exception:
        return 1920, 1080


def get_audio_duration_ms(audio_path):
    try:
        import wave
        with wave.open(audio_path, 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return int((frames / float(rate)) * 1000)
    except Exception:
        pass
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return int(float(res.stdout.strip()) * 1000)
    except Exception:
        return 0

def get_video_metadata(video_path):
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,codec_name,duration:format=duration",
            "-of", "json",
            video_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {}) or {}

        duration = 0.0
        width = CANVAS_W
        height = CANVAS_H
        codec = "unknown"
        fps = FPS

        def _safe_pos_float(val):
            if val is None or val == "N/A":
                return 0.0
            try:
                f = float(val)
                return f if f > 0.0 and math.isfinite(f) else 0.0
            except (ValueError, TypeError):
                return 0.0

        if streams:
            s = streams[0]
            width = int(s.get("width") or CANVAS_W)
            height = int(s.get("height") or CANVAS_H)
            codec = s.get("codec_name") or "unknown"
            duration = _safe_pos_float(s.get("duration"))
            for fr_key in ("avg_frame_rate", "r_frame_rate"):
                fr = str(s.get(fr_key) or "")
                if "/" in fr:
                    num_s, den_s = fr.split("/", 1)
                    num_f, den_f = _safe_pos_float(num_s), _safe_pos_float(den_s)
                    if num_f > 0 and den_f > 0:
                        raw_fps = num_f / den_f
                        if 1.0 <= raw_fps <= 240.0:
                            fps = int(round(raw_fps)) if abs(raw_fps - round(raw_fps)) < 0.02 else round(raw_fps * 1000.0) / 1000.0
                            break

        if duration <= 0.0:
            duration = _safe_pos_float(fmt.get("duration"))

        return {"width": width, "height": height, "duration": duration, "codec": codec, "fps": fps}
    except Exception:
        return {"width": CANVAS_W, "height": CANVAS_H, "duration": 0.0, "codec": "unknown", "fps": FPS}

def strip_audio_from_video(video_path):
    """Checks if a video has audio, and if so, strips it using a fast FFmpeg copy command."""
    try:
        # Check if there is an audio stream
        cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path]
        res_probe = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if len(res_probe.stdout.strip()) == 0:
            # Already mute or no audio track
            return True
            
        # Strip audio
        temp_path = video_path + ".temp.mp4"
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except Exception: pass
            
        os.rename(video_path, temp_path)
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", temp_path, "-c:v", "copy", "-an", video_path]
        res_run = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        success = False
        if res_run.returncode == 0:
            print(f"      [Mudo] Áudio removido com sucesso de: {os.path.basename(video_path)}")
            success = True
        else:
            print(f"      [Warning] Falha ao remover áudio de: {os.path.basename(video_path)}, mantendo original.")
            os.rename(temp_path, video_path)
            
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except Exception: pass
        return success
    except Exception as e:
        print(f"      [Warning] Falha no pós-processamento de áudio para {os.path.basename(video_path)}: {e}")
        return False

def translate_to_english(text):
    """Translates text to English using Google's free translation API."""
    if not text:
        return text
    if all(ord(c) < 128 for c in text):
        return text.strip()
    import urllib.request
    import urllib.parse
    import json
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={urllib.parse.quote(text)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            res = json.loads(response.read().decode("utf-8"))
            translated = "".join(sentence[0] for sentence in res[0] if sentence[0])
            if translated.strip():
                return translated.strip()
    except Exception as e:
        print(f"      [Translation Warning] Failed to translate '{text}': {e}")
    return text

def clean_search_query(query):
    """Removes quality buzzwords and redundant modifiers to prevent tag pollution."""
    import re
    modifiers = [
        r"\bhigh-quality photograph\b", r"\bhigh quality photograph\b",
        r"\bcloseup\b", r"\bclose-up\b", r"\bdocumentary shot\b",
        r"\bclean studio background\b", r"\bmacro close-up\b", r"\bversion \d+\b",
        r"\beditorial photo\b", r"\bpress photo official\b", r"\bprofessional photography\b",
        r"\bwide angle view\b", r"\bcinematic angle\b", r"\bclose up portrait\b",
        r"\bdramatic lighting\b", r"\bnews broadcast\b"
    ]
    cleaned = query
    for mod in modifiers:
        cleaned = re.sub(mod, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

# ── API Key Request Delays ────────────────────────────────────
def api_request_delay():
    delay = random.uniform(0.3, 0.6)
    time.sleep(delay)

# ── Premium API Video / Image Downloaders ──────────────────────
def search_pexels_video(query, exclude_urls=None):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return None
    api_request_delay()
    cleaned = clean_search_query(query)
    eng_query = translate_to_english(cleaned)
    print(f"    - [Pexels Video API] Buscando por: '{eng_query}' (Original: '{query}')")
    url = f"https://api.pexels.com/v1/videos/search?query={urllib.parse.quote(eng_query)}&per_page=15&orientation=landscape"
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        videos = data.get("videos", [])
        for vid in videos:
            files = vid.get("video_files", [])
            # Prefer standard horizontal HD 1080p
            hd_files = [f for f in files if f.get("width") == 1920 and f.get("height") == 1080]
            if hd_files:
                link = hd_files[0]["link"]
                if not exclude_urls or link not in exclude_urls:
                    return link
            # Fallback to any horizontal video
            horiz = [f for f in files if f.get("width") and f.get("height") and f["width"] > f["height"]]
            if horiz:
                link = horiz[0]["link"]
                if not exclude_urls or link not in exclude_urls:
                    return link
            if files:
                link = files[0]["link"]
                if not exclude_urls or link not in exclude_urls:
                    return link
    except Exception as e:
        print(f"      [Pexels API Error]: {e}")
    return None

def search_pexels_image(query):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return None
    api_request_delay()
    cleaned = clean_search_query(query)
    eng_query = translate_to_english(cleaned)
    print(f"    - [Pexels Photo API] Buscando por: '{eng_query}' (Original: '{query}')")
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(eng_query)}&per_page=5&orientation=landscape"
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        photos = data.get("photos", [])
        for photo in photos:
            src = photo.get("src", {})
            for sz in ["large2x", "original", "large"]:
                if src.get(sz):
                    return src[sz]
    except Exception as e:
        print(f"      [Pexels Photo API Error]: {e}")
    return None

def search_pixabay_video(query, exclude_urls=None):
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        return None
    exclude_set = exclude_urls or set()
    api_request_delay()
    cleaned = clean_search_query(query)
    eng_query = translate_to_english(cleaned)
    print(f"    - [Pixabay Video API] Buscando por: '{eng_query}' (Original: '{query}')")
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={urllib.parse.quote(eng_query)}&per_page=15&safesearch=true"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        hits = data.get("hits", [])
        for hit in hits:
            videos = hit.get("videos", {})
            for size in ["large", "medium", "small"]:
                cand_url = videos.get(size, {}).get("url")
                if cand_url and cand_url not in exclude_set:
                    return cand_url
    except Exception as e:
        print(f"      [Pixabay Video API Error]: {e}")
    return None

def search_pixabay_image(query, exclude_urls=None):
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        return None
    exclude_set = exclude_urls or set()
    api_request_delay()
    cleaned = clean_search_query(query)
    eng_query = translate_to_english(cleaned)
    print(f"    - [Pixabay Image API] Buscando por: '{eng_query}' (Original: '{query}')")
    url = f"https://pixabay.com/api/?key={api_key}&q={urllib.parse.quote(eng_query)}&per_page=15&image_type=photo&orientation=horizontal&safesearch=true"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        hits = data.get("hits", [])
        for hit in hits:
            img_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if img_url and img_url not in exclude_set:
                return img_url
    except Exception as e:
        print(f"      [Pixabay Image API Error]: {e}")
    return None

# ── Image Web Scrapers Fallbacks ──────────────────────────────
def is_blocked_response(html_content):
    html_lower = html_content.lower()
    block_indicators = [
        "sorry/index.html", "captcha", "security challenge", "unusual traffic",
        "automated requests", "cookie consent", "security check",
        "verify you are a human", "consent.yahoo.com"
    ]
    return any(indicator in html_lower for indicator in block_indicators)

def get_random_headers_and_delay():
    delay = random.uniform(2.0, 4.0)
    time.sleep(delay)
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
        "Connection": "keep-alive"
    }
    return headers

def yandex_images_scraper(query, num_results=20):
    import html
    headers = get_random_headers_and_delay()
    urls = []
    cleaned = clean_search_query(query)
    print(f"    - [Yandex Images Scraper] Buscando por: '{cleaned}' (Original: '{query}')")
    url_yandex = f"https://yandex.com/images/search?text={urllib.parse.quote(cleaned)}"
    req_yandex = urllib.request.Request(url_yandex, headers=headers)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req_yandex, context=ctx, timeout=8) as response:
            raw_html = response.read().decode('utf-8', errors='ignore')
            
        if is_blocked_response(raw_html):
            print("      [Yandex Images] Bloqueado por CAPTCHA/Segurança.")
            return []
            
        clean_html = html.unescape(raw_html)
        json_urls = re.findall(r'"url":"(https?://[^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"', clean_html)
        for u in json_urls:
            if "yandex" in u or "yastatic" in u:
                continue
            if u not in urls:
                urls.append(u)
                
        query_urls = re.findall(r'img_url=(https?%3A%2F%2F[^\s&"\'>]+)', clean_html)
        for u in query_urls:
            decoded = urllib.parse.unquote(u)
            if "yandex" in decoded or "yastatic" in decoded:
                continue
            if decoded not in urls:
                urls.append(decoded)
                
        if urls:
            print(f"      [Yandex Images] Encontrou {len(urls)} urls.")
    except Exception as e:
        print(f"      [Yandex Images scraper failed: {e}]")
    return urls[:num_results]

def google_images_scraper(query, num_results=3):
    import html
    headers = get_random_headers_and_delay()
    urls = []
    cleaned = clean_search_query(query)
    print(f"    - [Google Images Scraper] Buscando por: '{cleaned}' (Original: '{query}')")
    url_google = f"https://www.google.com/search?q={urllib.parse.quote(cleaned)}&tbm=isch&safe=active"
    req_google = urllib.request.Request(url_google, headers=headers)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req_google, context=ctx, timeout=8) as response:
            html_google = response.read().decode('utf-8', errors='ignore')
        
        if is_blocked_response(html_google):
            print("      [Google Images] Bloqueado por CAPTCHA/Challenge.")
            matches = []
        else:
            matches = re.findall(r'"ou":"(https://[^"]+)"', html_google)
            callbacks = re.findall(r'AF_initDataCallback\((.*?)\);', html_google, re.DOTALL)
            for cb in callbacks:
                found_urls = re.findall(r'"(https?://[^"]+)"', cb)
                for u in found_urls:
                    clean_url = u.encode().decode('unicode-escape', errors='ignore') if '\\u' in u else u
                    clean_url = clean_url.replace('\\/', '/')
                    if "gstatic" not in clean_url and "google.com" not in clean_url:
                        matches.append(clean_url)
                        
        for m in matches:
            clean_url = m.replace('\\u003d', '=').replace('\\&', '&')
            if clean_url not in urls:
                urls.append(clean_url)
                if len(urls) >= num_results:
                    break
        if urls:
            print(f"      [Google Images] Encontrou {len(urls)} urls.")
    except Exception as e:
        print(f"      [Google Images scraper failed: {e}]")
        
    # Fallback to Bing Images if Google fails to find urls
    if not urls:
        print(f"      [Fallback Bing] Tentando Bing Images para: '{query}'")
        url_bing = f"https://www.bing.com/images/search?q={urllib.parse.quote_plus(query)}&form=HDRSC2&first=1&adlt=strict"
        headers_bing = get_random_headers_and_delay()
        req_bing = urllib.request.Request(url_bing, headers=headers_bing)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req_bing, context=ctx, timeout=8) as response:
                raw_html = response.read().decode('utf-8', errors='ignore')
                
            if is_blocked_response(raw_html):
                print("      [Fallback Bing] Bloqueado por CAPTCHA.")
                m_blocks = []
            else:
                m_blocks = re.findall(r'class="iusc"[^>]*?m="([^"]+?)"', raw_html)
                
            keywords = [w.lower() for w in re.split(r'\W+', query) if len(w) > 2]
            for block in m_blocks:
                unescaped_block = html.unescape(block)
                try:
                    data = json.loads(unescaped_block)
                    murl = data.get("murl")
                    title = data.get("t", "").lower()
                    desc = data.get("desc", "").lower()
                    is_relevant = any(kw in title or kw in desc for kw in keywords) if keywords else True
                    if murl and is_relevant and murl not in urls:
                        urls.append(murl)
                        if len(urls) >= num_results:
                            break
                except Exception:
                    pass
            if urls:
                print(f"      [Bing Images] Encontrou {len(urls)} urls.")
        except Exception as e:
            print(f"      [Bing Images scraper failed: {e}]")
    return urls

def duckduckgo_fallback_scraper(query, num_results=3):
    headers = get_random_headers_and_delay()
    cleaned = clean_search_query(query)
    print(f"    - [DuckDuckGo Fallback Scraper] Buscando por: '{cleaned}' (Original: '{query}')")
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(cleaned)}&kp=1"
    req = urllib.request.Request(url, headers=headers)
    urls = []
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            html_data = response.read().decode('utf-8', errors='ignore')
        
        if is_blocked_response(html_data):
            return []
            
        matches = re.findall(r'//tse\d+\.mm\.bing\.net/th\?id=[^&"]+', html_data)
        for m in matches:
            full_url = "https:" + m
            if full_url not in urls:
                urls.append(full_url)
                if len(urls) >= num_results:
                    break
    except Exception as e:
        print(f"      [DuckDuckGo fallback failed: {e}]")
    return urls

# ── YouTube Downloader (yt-dlp) ───────────────────────────────
def download_youtube_video(query, output_path):
    if os.environ.get("DISABLE_YOUTUBE", "").lower() in ("true", "1", "yes"):
        print(f"    - [YouTube Search] YouTube downloads disabled via environment variable.")
        return False
    cleaned = clean_search_query(query)
    print(f"    - [YouTube Search] Buscando clip para: '{cleaned}' (Original: '{query}')")
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch1:{cleaned}",
            "-f", "bestvideo[height<=1080][ext=mp4]/bestvideo",
            "--match-filter", "duration <= 60",
            "-o", output_path,
            "--no-playlist",
            "--quiet"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40)
        if res.returncode == 0 and os.path.exists(output_path):
            print(f"      [OK] YouTube vídeo baixado: {os.path.basename(output_path)}")
            # Strip metadata/audio
            temp_path = output_path + ".temp.mp4"
            try:
                os.rename(output_path, temp_path)
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", temp_path,
                    "-map_metadata", "-1",
                    "-map_chapters", "-1",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-profile:v", "main",
                    "-level:v", "4.0",
                    "-crf", "20",
                    "-r", "30",
                    "-g", "30",
                    "-keyint_min", "30",
                    "-sc_threshold", "0",
                    "-movflags", "+faststart",
                    "-an",
                    output_path
                ]
                sub_res = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                if sub_res.returncode == 0:
                    print("      [OK] FFmpeg: Limpeza de vídeo executada com sucesso.")
                else:
                    # Fallback to moving temp back
                    os.rename(temp_path, output_path)
            except Exception as fe:
                print(f"      [Warning] Falha no pós-processamento ffmpeg: {fe}")
                if os.path.exists(temp_path) and not os.path.exists(output_path):
                    os.rename(temp_path, output_path)
            finally:
                if os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except Exception: pass
            return True
    except Exception as e:
        print(f"      [YouTube Downloader Error]: {e}")
    return False

# ── Unified Media Downloader ──────────────────────────────────
def run_media_downloads(project_dir):
    load_env(project_dir)
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    if not os.path.exists(storyboard_path):
        print(f"Erro: storyboard.json não encontrado em {project_dir}")
        return False
        
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)
        
    images_dir = os.path.join(project_dir, "media", "images")
    videos_dir = os.path.join(project_dir, "media", "videos")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)
    
    downloaded_urls = {}
    global_mode = storyboard.get("mode", "default")
    global_universe = storyboard.get("universe", None)
    
    for scene in storyboard.get("scenes", []):
        sid = scene["id"]
        layout_style = scene.get("layout_style", "single_card")
        
        # Skip if text_only (no media needed)
        if layout_style == "text_only":
            continue
            
        media = scene.get("media", {})
        if not media:
            elements = scene.get("elements", [])
            if elements:
                media = elements[0]
                
        query = media.get("query", "")
        source_type = media.get("source_type", "image")
        
        scene_mode = scene.get("mode") or media.get("mode") or global_mode or "default"
        scene_universe = scene.get("universe") or media.get("universe") or global_universe
        is_pop_mode = (str(scene_mode).strip().lower() == "pop")
        
        if is_pop_mode:
            # POP mode strictly forces image downloads only (zero video downloads)
            source_type = "image"
            media["source_type"] = "image"
        if source_type == "lottie" and media.get("lottie_path"):
            dest_path = os.path.join(project_dir, media["lottie_path"])
            if os.path.exists(dest_path):
                print(f"    - Lottie {media['lottie_path']} já existe. Ignorando.")
                continue
                
        if not query:
            continue
            
        # Check if query matches a local Lottie file to use instead of image/video
        lottie_path = find_matching_lottie(project_dir, query)
        if lottie_path:
            ext = os.path.splitext(lottie_path)[1].lower()
            lotties_dest_dir = os.path.join(project_dir, "media", "lotties")
            os.makedirs(lotties_dest_dir, exist_ok=True)
            filename = f"{sid}_lottie{ext}"
            dest_path = os.path.join(lotties_dest_dir, filename)
            shutil.copy2(lottie_path, dest_path)
            
            # Mutate storyboard media properties
            media["source_type"] = "lottie"
            media["lottie_path"] = f"media/lotties/{filename}"
            print(f"    - [Lottie Match] Usando animação Lottie '{os.path.basename(lottie_path)}' para a cena {sid} (query: '{query}')")
            continue
            
        # Download logic based on source_type
        is_generic = (layout_style == "full_screen")
        
        # 1. Respect explicit source overrides from storyboard
        media_source = media.get("source", "").lower()
        if media_source in ["youtube", "yandex"]:
            is_generic = False
        elif media_source in ["pexels", "pixabay"]:
            is_generic = True
        # 2. Respect explicit specific/generic flags
        elif "specific" in media:
            is_generic = not bool(media["specific"])
        elif "is_generic" in media:
            is_generic = bool(media["is_generic"])
        # 3. Capitalization heuristic (detects proper nouns in the query, e.g. "sunset in Paris", "new York beauty")
        else:
            words = query.strip().split()
            has_proper_nouns = False
            for idx, w in enumerate(words):
                if w and w[0].isupper() and idx > 0:
                    has_proper_nouns = True
                    break
            if has_proper_nouns:
                is_generic = False
        
        if source_type == "video":
            filename = f"{sid}.mp4"
            dest_path = os.path.join(videos_dir, filename)
            
            if os.path.exists(dest_path):
                print(f"    - Vídeo {filename} já existe. Ignorando download.")
                strip_audio_from_video(dest_path)
                success = True
            else:
                success = False
                if is_generic:
                    # Generic scene: Pexels API -> Pixabay API -> YouTube
                    print(f"    - [Cena Genérica] Buscando vídeo nas APIs (Pexels/Pixabay) para: '{query}'")
                    video_url = search_pexels_video(query, exclude_urls=set(downloaded_urls.keys()))
                    if video_url and video_url in downloaded_urls:
                        print(f"      [Duplicado] Vídeo Pexels já baixado para outra cena, pulando...")
                        video_url = None
                    if not video_url:
                        video_url = search_pixabay_video(query, exclude_urls=set(downloaded_urls.keys()))
                        if video_url and video_url in downloaded_urls:
                            print(f"      [Duplicado] Vídeo Pixabay já baixado para outra cena, pulando...")
                            video_url = None
                        
                    if video_url:
                        try:
                            req = urllib.request.Request(video_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode = ssl.CERT_NONE
                            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                                with open(dest_path, "wb") as out_f:
                                    out_f.write(response.read())
                            print(f"      [OK] Vídeo genérico baixado (API): {filename}")
                            downloaded_urls[video_url] = dest_path
                            success = True
                        except Exception as e:
                            print(f"      [Pexels/Pixabay Video download failed: {e}]")
                            if os.path.exists(dest_path):
                                try: os.remove(dest_path)
                                except Exception: pass
                    
                    if not success:
                        print(f"      [Fallback] APIs falharam. Tentando YouTube para cena genérica: '{query}'")
                        success = download_youtube_video(query, dest_path)
                else:
                    # Specific scene: YouTube first!
                    print(f"    - [Cena Específica] Buscando vídeo no YouTube (yt-dlp) para: '{query}'")
                    success = download_youtube_video(query, dest_path)
                
                if success:
                    strip_audio_from_video(dest_path)
                    
            # Image fallback if video completely fails (for both generic and specific)
            if not success:
                print(f"      [Fallback] Vídeo falhou/não encontrado. Buscando imagem Yandex para a cena {sid}...")
                source_type = "image" # mutate type for local processing fallback
                media["source_type"] = "image"
                
        if source_type == "image":
            filename = f"{sid}_E01.png"
            dest_path = os.path.join(images_dir, filename)
            
            if os.path.exists(dest_path):
                try:
                    with Image.open(dest_path) as test_img:
                        test_img.verify()
                    print(f"    - Imagem {filename} já existe e está válida. Ignorando.")
                    success = True
                except Exception:
                    print(f"    - Imagem existente corrompida. Removendo: {filename}")
                    try: os.remove(dest_path)
                    except Exception: pass
                    success = False
            else:
                success = False
                
            if not success:
                if (is_generic or media_source in ["pexels", "pixabay"]) and not is_pop_mode:
                    img_url = search_pexels_image(query)
                    if img_url and img_url in downloaded_urls:
                        img_url = None
                    if not img_url:
                        img_url = search_pixabay_image(query, exclude_urls=set(downloaded_urls.keys()))
                    if img_url:
                        try:
                            req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode = ssl.CERT_NONE
                            with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
                                with open(dest_path, "wb") as out_f:
                                    out_f.write(response.read())
                            with Image.open(dest_path) as test_img:
                                test_img.verify()
                            print(f"      [OK] Imagem Stock (Pixabay/Pexels) salva: {filename}")
                            downloaded_urls[img_url] = dest_path
                            success = True
                        except Exception as e:
                            print(f"      [Stock Image download failed: {e}]")
                            if os.path.exists(dest_path):
                                try: os.remove(dest_path)
                                except Exception: pass

            if not success:
                # Priority 1: VisualAssetAgent (Multi-Fonte + Metadados + OCR + POP Mode)
                try:
                    from visual_asset_agent.app.agent import VisualAssetAgent
                    v_agent = VisualAssetAgent(download_dir=images_dir)
                    res = v_agent.find_best_media(
                        query=query,
                        context=scene.get("narration", ""),
                        media_type="image",
                        strict=True,
                        exclude_urls=set(downloaded_urls.keys()),
                        mode=scene_mode,
                        universe=scene_universe
                    )
                    if res.winner and res.winner.local_path and os.path.exists(res.winner.local_path):
                        if res.winner.local_path != dest_path:
                            shutil.copy2(res.winner.local_path, dest_path)
                        downloaded_urls[res.winner.url] = dest_path
                        print(f"    - [VisualAssetAgent] Imagem validada ({res.winner.source}, score {res.winner.score:.1f}) para: '{query}'")
                        success = True
                except Exception as e:
                    print(f"    - [VisualAssetAgent Fallback]: {e}")
                    
            if not success:
                # Priority 2: Scraper fallback
                effective_search_query = query
                if is_pop_mode and scene_universe and scene_universe.strip().lower() not in query.lower():
                    effective_search_query = f"{scene_universe.strip()} {query.strip()}"
                    
                print(f"    - [Prioridade Imagem Fallback] Buscando imagem no Yandex para: '{effective_search_query}'")
                urls = yandex_images_scraper(effective_search_query)
                
                # In POP mode, 100% block stock APIs (Pixabay)
                if not is_pop_mode and not urls:
                    print(f"      [Fallback] Yandex sem resultados. Tentando Pixabay Image API...")
                    img_url = search_pixabay_image(effective_search_query, exclude_urls=set(downloaded_urls.keys()))
                    if img_url:
                        urls = [img_url]
                        
                if not urls:
                    print(f"      [Fallback] Tentando DuckDuckGo...")
                    urls = duckduckgo_fallback_scraper(effective_search_query)
                    
                if not urls:
                    print(f"      [Fallback] Tentando Google Images...")
                    urls = google_images_scraper(effective_search_query)
                    
                success = False
                for url in urls:
                    try:
                        if url in downloaded_urls:
                            print(f"      [Duplicado] Imagem/URL já baixada para outra cena: {url}. Pulando para garantir exclusividade.")
                            continue
                                
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
                            with open(dest_path, "wb") as out_f:
                                out_f.write(response.read())
                                
                        with Image.open(dest_path) as test_img:
                            test_img.verify()
                            # Reject placeholder icons/thumbnails
                            w_img, h_img = test_img.size
                            if w_img < 300 or h_img < 300:
                                raise ValueError(f"Image dimensions too small: {w_img}x{h_img} (min 300x300)")
                                
                        print(f"      [OK] Imagem salva: {filename}")
                        downloaded_urls[url] = dest_path
                        success = True
                        break
                    except Exception as e:
                        print(f"      [Download tentou {url} mas falhou: {e}]")
                        if os.path.exists(dest_path):
                            try: os.remove(dest_path)
                            except Exception: pass
                if not success:
                    print(f"      [FAIL] Falha geral ao baixar imagem para: '{query}'")
                    
    # Rewrite storyboard with mutated fallback parameters if any
    with open(storyboard_path, "w", encoding="utf-8") as f:
        json.dump(storyboard, f, indent=2, ensure_ascii=False)
    return True

# ── Pillow Image Processor (Handcrafted Editorial Frames + Fullscreen Polish) ─────────
def apply_card_styling(input_path, output_path, border_radius=48, frame_style="polaroid_editorial", accent_hex="#FBBF24", seed=42):
    """Applies randomized handcrafted editorial framing (Polaroid, Torn Paper, 35mm Film, Chamfer, Double Mat, Stacked Print, Archival Stamp, Cinema Glass) with true alpha drop shadow."""
    if editorial_engine.apply_handcrafted_card_frame(
        input_path,
        output_path,
        frame_style=frame_style or "polaroid_editorial",
        accent_hex=accent_hex or "#FBBF24",
        seed=seed,
    ):
        return True
    try:
        img = Image.open(input_path).convert("RGBA")
        orig_w, orig_h = img.size
        aspect = orig_w / float(orig_h) if orig_h > 0 else 1.0
        target_h = 940 if aspect <= 1.0 else max(160, (int(940 / aspect) // 2) * 2)
        target_w = max(160, (int(940 * aspect) // 2) * 2) if aspect <= 1.0 else 940
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        mask = Image.new("L", (target_w, target_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, target_w - 1, target_h - 1), radius=border_radius, fill=255)
        img.putalpha(mask)
        img.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"      [Pillow Error] Falha ao formatar card: {os.path.basename(input_path)}: {e}")
        return False

def apply_blur_background_styling(input_path, output_path, seed=42):
    """Formats full_screen images onto 1920x1080 with subtle cinema polish and varied uncropped framing for non-16:9 photos."""
    return editorial_engine.apply_editorial_fullscreen_framing(input_path, output_path, seed=seed)

def _project_editorial_seed(project_dir, sb_data=None):
    base = os.path.basename(os.path.abspath(project_dir)) or "freecut_project"
    var = str((sb_data or {}).get("variation_seed") or "").strip()
    return f"{base}:{var}" if var else base


def process_images_pipeline(project_dir):
    images_dir = os.path.join(project_dir, "media", "images")
    processed_dir = os.path.join(project_dir, "media", "processed")
    os.makedirs(processed_dir, exist_ok=True)
    manifest_cache_path = os.path.join(processed_dir, ".frame_manifest.json")
    frame_manifest = {}
    if os.path.exists(manifest_cache_path):
        try:
            with open(manifest_cache_path, "r", encoding="utf-8") as mf:
                frame_manifest = json.load(mf)
        except Exception:
            frame_manifest = {}

    # Load storyboard to determine layout style, palette, and per-scene handcrafted frame style
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    storyboard_scenes = []
    sb_data = {}
    if os.path.exists(storyboard_path):
        try:
            with open(storyboard_path, "r", encoding="utf-8") as f:
                sb_data = json.load(f)
                storyboard_scenes = sb_data.get("scenes", [])
        except Exception as e:
            print(f"    [Warning] Erro ao ler storyboard para processamento de imagem: {e}")

    proj_seed = _project_editorial_seed(project_dir, sb_data)
    sample_narration = " ".join(s.get("narration", "") for s in storyboard_scenes[:12])
    _, palette = editorial_engine.select_project_typography_palette(
        project_seed=proj_seed,
        title=sb_data.get("title", ""),
        mode=sb_data.get("mode", "default"),
        universe=sb_data.get("universe", ""),
        sample_text=sample_narration,
        explicit_theme=sb_data.get("font_theme", ""),
    )
    accents = palette.get("accents", ["#FBBF24", "#38BDF8", "#FB7185"])

    # 1. Process standard images
    image_files = (
        glob.glob(os.path.join(images_dir, "*.png"))
        + glob.glob(os.path.join(images_dir, "*.jpg"))
        + glob.glob(os.path.join(images_dir, "*.jpeg"))
        + glob.glob(os.path.join(images_dir, "*.webp"))
    )
    prev_card_styles = []
    for idx_img, filepath in enumerate(sorted(set(image_files))):
        filename = os.path.basename(filepath)
        stem, _ = os.path.splitext(filename)
        out_name = f"{stem}.png"
        out_path = os.path.join(processed_dir, out_name)

        layout_style = "single_card"
        scene = None
        for s in storyboard_scenes:
            sid = s.get("id")
            if filename.startswith(f"{sid}_") or stem == sid:
                scene = s
                break

        seed_val = int(hashlib.md5(f"{proj_seed}_{filename}_{idx_img}".encode("utf-8")).hexdigest()[:8], 16)
        rng_img = random.Random(seed_val)
        accent_hex = rng_img.choice(accents)
        frame_style = "fullscreen_editorial"

        if scene:
            layout_style = scene.get("layout_style", "single_card")
            lparams = scene.get("layout_params") or {}
            if layout_style in ("single_card", "split_info_slide"):
                explicit_fs = lparams.get("frame_style") or scene.get("frame_style") or ""
                frame_style = editorial_engine.select_card_frame_style(
                    narration=scene.get("narration", ""),
                    query=(scene.get("media") or {}).get("query", ""),
                    mode=sb_data.get("mode", "default"),
                    scene_idx=idx_img,
                    prev_styles=prev_card_styles,
                    rng=rng_img,
                    explicit_style=explicit_fs,
                )
                prev_card_styles.append(frame_style)
        else:
            frame_style = editorial_engine.select_card_frame_style(
                narration="", query=filename, mode="default",
                scene_idx=idx_img, prev_styles=prev_card_styles, rng=rng_img,
            )
            prev_card_styles.append(frame_style)

        try:
            st = os.stat(filepath)
            cache_sig = f"{layout_style}:{frame_style}:{accent_hex}:{seed_val}:{st.st_size}:{int(st.st_mtime)}:v3"
        except OSError:
            cache_sig = f"{layout_style}:{frame_style}:{accent_hex}:{seed_val}:v3"

        if os.path.exists(out_path) and frame_manifest.get(out_name) == cache_sig:
            continue

        if layout_style == "full_screen":
            print(f"    - Processando enquadramento editorial full_screen para: {filename}")
            if apply_blur_background_styling(filepath, out_path, seed=seed_val):
                frame_manifest[out_name] = cache_sig
        else:
            print(f"    - Processando moldura artesanal [{frame_style}] para: {filename}")
            if apply_card_styling(filepath, out_path, frame_style=frame_style, accent_hex=accent_hex, seed=seed_val):
                frame_manifest[out_name] = cache_sig

    # 2. Generate custom background color images for text_only scenes (default pure #000000)
    if os.path.exists(storyboard_path):
        with open(storyboard_path, "r", encoding="utf-8") as f:
            storyboard = json.load(f)
        for scene in storyboard.get("scenes", []):
            if scene.get("layout_style") == "text_only":
                sid = scene["id"]
                bg_color = scene.get("bg_color", scene.get("background_color", "#000000"))
                out_bg_name = f"{sid}_bg.png"
                out_bg_path = os.path.join(processed_dir, out_bg_name)
                bg_sig = f"text_only_bg:{bg_color}:v3"
                if not os.path.exists(out_bg_path) or frame_manifest.get(out_bg_name) != bg_sig:
                    print(f"    - Gerando background sólido ({bg_color}) para cena de texto {sid}")
                    img = Image.new("RGB", (CANVAS_W, CANVAS_H), bg_color)
                    img.save(out_bg_path, "PNG")
                    frame_manifest[out_bg_name] = bg_sig

    try:
        with open(manifest_cache_path, "w", encoding="utf-8") as mf:
            json.dump(frame_manifest, mf, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return True


def ensure_storyboard_rebuilt(project_dir, variation=None):
    """
    Ensures raw storyboards (e.g. created via `scripts/build_storyboard.py`) have
    `layout_params`, `text_layout`, and `text_overlays` populated before `build`.
    """
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    if not os.path.exists(storyboard_path):
        return False
    if variation:
        return rebuild_storyboard(project_dir, variation=variation)
    try:
        with open(storyboard_path, "r", encoding="utf-8") as f:
            sb = json.load(f)
        scenes = sb.get("scenes", [])
        needs_rebuild = False
        for s in scenes:
            if "text_layout" not in s or "layout_params" not in s:
                needs_rebuild = True
                break
            if s.get("layout_style") == "text_only" and not s.get("text_overlays"):
                needs_rebuild = True
                break
        if needs_rebuild:
            print("  [Auto-Rebuild] Storyboard bruto detectado — aplicando layout editorial e chunking de legendas...")
            return rebuild_storyboard(project_dir)
    except Exception:
        return False
    return True


# ── Storyboard Rebuilder ──────────────────────────────────────
def rebuild_storyboard(project_dir, variation=None):
    """Parses raw storyboard.json and words.json to assign archetypes and build subtitles."""
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    words_path = os.path.join(project_dir, "words.json")
    
    if not os.path.exists(storyboard_path):
        print(f"Erro: storyboard.json não encontrado em {project_dir}")
        return False
        
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    if variation is not None:
        v_str = str(variation).strip()
        if v_str.lower() in ("random", "new", "auto"):
            v_str = uuid.uuid4().hex[:8]
        storyboard["variation_seed"] = v_str
        # Clear explicit font_theme only if user asked for a fresh random variation and didn't lock font_theme_locked
        if not storyboard.get("font_theme_locked"):
            storyboard.pop("font_theme", None)
        for sc in storyboard.get("scenes", []):
            if isinstance(sc.get("layout_params"), dict) and not sc.get("frame_style"):
                sc["layout_params"].pop("frame_style", None)

    words = load_words_normalized(words_path)
            
    scenes = storyboard.get("scenes", [])
    total_scenes = len(scenes)
    
    # 0. Sanitização de cenas inválidas (0s ou start >= end)
    valid_scenes = []
    for s in scenes:
        s_dur = s.get("end_ms", 0) - s.get("start_ms", 0)
        if s_dur > 0:
            valid_scenes.append(s)
        else:
            print(f"  [AVISO SANITIZAÇÃO] Removida cena '{s.get('id')}' com duração zero ou negativa ({s_dur}ms).")
    scenes = valid_scenes
    total_scenes = len(scenes)
    
    # 0.1 Alerta de cenas excessivamente longas (>8.5s)
    for s in scenes:
        s_dur = s.get("end_ms", 0) - s.get("start_ms", 0)
        if s_dur > 8500:
            print(f"  [ALERTA RITMO] Cena '{s.get('id')}' possui duração de {s_dur/1000:.2f}s (>8.5s). Verifique se o fatiamento foi intencional.")

    # Enforce constraints and rules in preprocessing
    if total_scenes > 0:
        # 1. Enforce 5-second minimum duration for info_card
        for scene in scenes:
            if scene.get("info_card"):
                dur = scene.get("end_ms", 0) - scene.get("start_ms", 0)
                if dur < 5000:
                    scene.pop("info_card", None)
                    
        # 2. Enforce 40% cap on info_card
        info_card_scenes = [s for s in scenes if s.get("info_card")]
        max_cards = int(total_scenes * 0.2)
        if len(info_card_scenes) > max_cards:
            # Sort by duration ascending to drop from the shortest scenes first
            info_card_scenes.sort(key=lambda s: s.get("end_ms", 0) - s.get("start_ms", 0))
            excess_count = len(info_card_scenes) - max_cards
            for i in range(excess_count):
                info_card_scenes[i].pop("info_card", None)
                
        # 3. Enforce 30% cap on split_info_slide (sidebar subtitles)
        split_scenes = []
        for s in scenes:
            layout = (s.get("layout_style") or s.get("layout") or "single_card").lower()
            if layout == "split_info_slide":
                split_scenes.append(s)
                
        max_split = int(total_scenes * 0.3)
        if len(split_scenes) > max_split:
            # Sort by duration ascending to convert the shortest scenes first
            split_scenes.sort(key=lambda s: s.get("end_ms", 0) - s.get("start_ms", 0))
            excess_count = len(split_scenes) - max_split
            for i in range(excess_count):
                s = split_scenes[i]
                if "layout_style" in s:
                    s["layout_style"] = "single_card"
                if "layout" in s:
                    s["layout"] = "single_card"
                    
    new_scenes = []

    proj_seed = _project_editorial_seed(project_dir, storyboard)
    sample_narration = " ".join(s.get("narration", "") for s in scenes[:12])
    palette_key, palette = editorial_engine.select_project_typography_palette(
        project_seed=proj_seed,
        title=storyboard.get("title", ""),
        mode=storyboard.get("mode", "default"),
        universe=storyboard.get("universe", ""),
        sample_text=sample_narration,
        explicit_theme=storyboard.get("font_theme", ""),
    )
    storyboard["font_theme"] = palette_key
    body_font, body_weight = editorial_engine.sanitize_font_and_weight(
        palette["body_font"], palette["body_weight"]
    )
    disp_font, disp_weight = editorial_engine.sanitize_font_and_weight(
        palette["display_font"], palette["display_weight"]
    )

    # State tracking for balanced alternation & frame anti-repetition across scenes
    last_split_side = None
    last_split_type = None
    last_single_card_pos = None
    prev_card_frame_styles = []

    for idx, scene in enumerate(scenes):
        sid = scene["id"]
        start_ms = scene["start_ms"]
        end_ms = scene["end_ms"]
        narration = scene["narration"]

        # Multi-factor entropy seed combining project seed (+ optional variation_seed), scene index, sid, and narration
        scene_seed = int(hashlib.md5(f"{proj_seed}_{idx}_{sid}_{narration}".encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(scene_seed)

        # 1. Resolve registered layouts
        raw_layout = scene.get("layout_style") or scene.get("layout", "single_card")
        layout_style = raw_layout.lower()
        if layout_style not in ["full_screen", "single_card", "text_only", "split_info_slide"]:
            layout_style = "single_card"

        media = scene.get("media", {})
        if not media:
            elements = scene.get("elements", [])
            if elements:
                media = elements[0]

        # If there is no media, force text_only
        if layout_style != "text_only" and (not media or not media.get("query")):
            layout_style = "text_only"

        existing_params = dict(scene.get("layout_params", {})) if isinstance(scene.get("layout_params"), dict) else {}
        layout_params = {}

        if layout_style == "single_card":
            user_text_pos = existing_params.get("text_pos")
            if user_text_pos in ["top", "bottom"]:
                card_pos = "top" if user_text_pos == "bottom" else "bottom"
            else:
                if last_single_card_pos == "top":
                    card_pos = "bottom"
                elif last_single_card_pos == "bottom":
                    card_pos = "top"
                else:
                    card_pos = rng.choice(["top", "bottom"])
            last_single_card_pos = card_pos

            cx_jitter = round(rng.uniform(-0.03, 0.03), 3)
            cy_jitter = round(rng.uniform(-0.02, 0.02), 3)
            card_scale = existing_params.get("scale") or round(rng.uniform(0.72, 0.78), 3)
            chosen_frame = editorial_engine.select_card_frame_style(
                narration=narration,
                query=(media or {}).get("query", ""),
                mode=storyboard.get("mode", "default"),
                scene_idx=idx,
                prev_styles=prev_card_frame_styles,
                rng=rng,
                explicit_style=scene.get("frame_style") or existing_params.get("frame_style") or "",
            )
            prev_card_frame_styles.append(chosen_frame)

            if card_pos == "top":
                layout_params = {
                    "scale": card_scale,
                    "x": existing_params.get("x", cx_jitter),
                    "y": existing_params.get("y", round(-0.09 + cy_jitter, 3)),
                    "text_pos": "bottom",
                    "frame_style": chosen_frame,
                }
            else:
                layout_params = {
                    "scale": card_scale,
                    "x": existing_params.get("x", cx_jitter),
                    "y": existing_params.get("y", round(0.09 + cy_jitter, 3)),
                    "text_pos": "top",
                    "frame_style": chosen_frame,
                }
        elif layout_style == "split_info_slide":
            user_split_type = existing_params.get("split_type")
            user_side = existing_params.get("side")
            user_text_pos = existing_params.get("text_pos")

            if user_split_type in ["horizontal", "vertical"]:
                split_type = user_split_type
            else:
                if last_split_type == "horizontal" and rng.random() < 0.35:
                    split_type = "vertical"
                else:
                    split_type = "horizontal"
            last_split_type = split_type

            card_scale = existing_params.get("scale") or round(rng.uniform(0.68, 0.74), 3)
            chosen_frame = editorial_engine.select_card_frame_style(
                narration=narration,
                query=(media or {}).get("query", ""),
                mode=storyboard.get("mode", "default"),
                scene_idx=idx,
                prev_styles=prev_card_frame_styles,
                rng=rng,
                explicit_style=scene.get("frame_style") or existing_params.get("frame_style") or "",
            )
            prev_card_frame_styles.append(chosen_frame)

            if split_type == "horizontal":
                if user_side in ["left", "right"]:
                    side = user_side
                else:
                    if last_split_side == "left":
                        side = "right"
                    elif last_split_side == "right":
                        side = "left"
                    else:
                        side = rng.choice(["left", "right"])
                last_split_side = side

                cx_jitter = round(rng.uniform(-0.02, 0.02), 3)
                cy_jitter = round(rng.uniform(-0.03, 0.03), 3)
                target_x = round((-0.25 if side == "left" else 0.25) + cx_jitter, 3)

                layout_params = {
                    "split_type": "horizontal",
                    "scale": card_scale,
                    "x": existing_params.get("x", target_x),
                    "y": existing_params.get("y", cy_jitter),
                    "side": side,
                    "frame_style": chosen_frame,
                }
            else:  # vertical
                if user_text_pos in ["top", "bottom"]:
                    text_pos = user_text_pos
                else:
                    text_pos = "top" if last_single_card_pos == "bottom" else "bottom"

                cx_jitter = round(rng.uniform(-0.03, 0.03), 3)
                cy_jitter = round(rng.uniform(-0.02, 0.02), 3)
                target_y = round((0.09 if text_pos == "top" else -0.09) + cy_jitter, 3)

                layout_params = {
                    "split_type": "vertical",
                    "scale": card_scale,
                    "x": existing_params.get("x", cx_jitter),
                    "y": existing_params.get("y", target_y),
                    "text_pos": text_pos,
                    "frame_style": chosen_frame,
                }
        elif layout_style == "full_screen":
            layout_params = {
                "scale": existing_params.get("scale", 1.0),
                "x": existing_params.get("x", 0.0),
                "y": existing_params.get("y", 0.0),
            }

        # 2. Pure #000000 clean black base unless explicit light bg was requested
        explicit_bg = scene.get("bg_color") or scene.get("background_color") or ""
        light_bgs = {"#FAF9F6", "#F5F5F7", "#F9F9FB", "#F4F4F5", "#FAF6F0", "#F5EFEB", "#EDE7E1", "#F6F0E5", "#FFFFFF"}
        if explicit_bg in light_bgs:
            bg_color = explicit_bg
            is_light_bg = True
            text_color = "#111827"
        else:
            bg_color = "#000000"
            is_light_bg = False
            text_color = "#FFFFFF"

        scene["background_color"] = bg_color

        # 3. Cohesive Editorial Typography & Positioning
        if layout_style == "text_only":
            text_font, font_weight = disp_font, disp_weight
        else:
            text_font, font_weight = body_font, body_weight

        text_align = "center"
        use_pill_bg = False
        if layout_style == "text_only":
            text_x = 0.0
            text_y = 0.0
            text_font_size = rng.randint(78, 92)
        elif layout_style == "split_info_slide":
            split_type = layout_params.get("split_type", "horizontal")
            if split_type == "horizontal":
                text_x = 0.25 if layout_params.get("side") == "left" else -0.25
                text_y = round(rng.uniform(-0.03, 0.03), 3)
                text_font_size = rng.randint(60, 68)
                text_align = "left"
            else:
                text_x = 0.0
                text_pos = layout_params.get("text_pos", "bottom")
                base_y = -0.34 if text_pos == "top" else 0.34
                text_y = round(base_y + rng.uniform(-0.02, 0.02), 3)
                text_font_size = rng.randint(60, 68)
                text_align = "center"
        elif layout_style == "single_card":
            text_x = 0.0
            text_pos = layout_params.get("text_pos", "bottom")
            base_y = 0.34 if text_pos == "bottom" else -0.34
            text_y = round(base_y + rng.uniform(-0.02, 0.02), 3)
            text_align = "center"
            text_font_size = rng.randint(62, 70)
        else:  # full_screen
            text_x = 0.0
            # Weighted ~78% classic cinema lower-third, ~22% upper editorial placement
            base_y = rng.uniform(0.30, 0.35) if rng.random() < 0.78 else rng.uniform(-0.35, -0.30)
            text_y = round(base_y + rng.uniform(-0.015, 0.015), 3)
            text_font_size = rng.randint(62, 72)
            use_pill_bg = rng.random() < 0.24

        entry_type = rng.choice(["fade-up", "rise", "cascade", "pop", "blur-in", "slide-mask", "typewriter"])
        exit_type = rng.choice(["fade-down", "sink", "blur-out", "pop-out"])

        # 4. Subtitle chunking (with dedicated full-scene dramatic card for `text_only`)
        global_subtitles = storyboard.get("subtitles", True)
        show_subtitles = (layout_style == "text_only") or (global_subtitles and scene.get("subtitles", True))
        text_overlays = []
        existing_overlays = scene.get("text_overlays", [])
        text_only_headline = (scene.get("text_only_text") or scene.get("text_overlay") or "").strip()

        if layout_style == "text_only":
            raw_hl = text_only_headline or narration.strip()
            hl_words = raw_hl.split()
            if not text_only_headline and len(hl_words) > 10:
                raw_hl = " ".join(hl_words[:8])
            text_overlays.append({
                "text": raw_hl.upper(),
                "appear_at_ms": start_ms,
                "duration_ms": max(800, end_ms - start_ms),
                "fontSize": text_font_size,
                "fontFamily": disp_font,
                "fontWeight": disp_weight,
                "x": 0.0,
                "y": 0.0,
                "entry": rng.choice(["rise", "blur-in", "slide-mask", "cascade"]),
                "exit": "fade-down",
            })
        elif existing_overlays and (not words or scene.get("custom_overlays")):
            for ov in existing_overlays:
                if not ov.get("text"):
                    continue
                ov_copy = dict(ov)
                fam_s, w_s = editorial_engine.sanitize_font_and_weight(
                    ov_copy.get("fontFamily", body_font),
                    ov_copy.get("fontWeight", body_weight),
                )
                ov_copy["fontFamily"] = fam_s
                ov_copy["fontWeight"] = w_s
                text_overlays.append(ov_copy)
        elif show_subtitles:
            scene_words = [
                w for w in words
                if w.get("start_ms") is not None and w.get("end_ms") is not None
                and w["start_ms"] >= start_ms - 200 and w["start_ms"] < end_ms
            ]
            scene_words.sort(key=lambda x: x["start_ms"])

            if scene_words:
                current_chunk = []
                chunk_start = None
                chunk_limit = rng.choice([2, 2, 3, 3, 4, 1])

                def _build_chunk_overlay(chunk_words, start_t, end_t):
                    w_count = len(chunk_words)
                    chunk_txt = " ".join(chunk_words)
                    if w_count == 1:
                        c_size = rng.randint(80, 92)
                        c_font, c_weight = disp_font, disp_weight
                        c_y = round(text_y + rng.choice([-0.015, 0.0, 0.015]), 3)
                        c_entry = rng.choice(["pop", "rise", "blur-in", "slide-mask"])
                    elif w_count == 2:
                        c_size = rng.randint(68, 76)
                        c_font, c_weight = body_font, body_weight
                        c_y = round(text_y + rng.choice([-0.01, 0.0, 0.01]), 3)
                        c_entry = rng.choice(["fade-up", "rise", "pop", "blur-in", "cascade"])
                    else:
                        c_size = rng.randint(60, 68)
                        c_font, c_weight = body_font, body_weight
                        c_y = text_y
                        c_entry = rng.choice(["fade-up", "rise", "slide-mask", "typewriter", "blur-in"])

                    c_exit = rng.choice(["fade-down", "blur-out", "sink"])
                    return {
                        "text": chunk_txt,
                        "appear_at_ms": start_t,
                        "duration_ms": max(750, end_t - start_t),
                        "fontSize": c_size,
                        "fontFamily": c_font,
                        "fontWeight": c_weight,
                        "x": text_x,
                        "y": c_y,
                        "entry": c_entry,
                        "exit": c_exit,
                    }

                for w in scene_words:
                    if not current_chunk:
                        chunk_start = w["start_ms"]
                    current_chunk.append(w["word"])
                    clean_word = w["word"].strip()
                    has_punct = any(p in clean_word for p in [".", ",", "!", "?", ";"])

                    if len(current_chunk) >= chunk_limit or has_punct or (w["end_ms"] - chunk_start > 1900):
                        text_overlays.append(_build_chunk_overlay(current_chunk, chunk_start, w["end_ms"]))
                        current_chunk = []
                        chunk_limit = rng.choice([2, 2, 3, 3, 4, 1])
                if current_chunk:
                    text_overlays.append(_build_chunk_overlay(current_chunk, chunk_start, end_ms))
            else:
                text_raw = scene.get("text_only_text") or scene.get("text_overlay") or narration
                text_overlays.append({
                    "text": text_raw.upper() if layout_style == "text_only" else text_raw,
                    "appear_at_ms": start_ms,
                    "duration_ms": end_ms - start_ms,
                    "fontSize": text_font_size,
                    "fontFamily": text_font,
                    "fontWeight": font_weight,
                    "x": text_x,
                    "y": text_y,
                    "entry": entry_type,
                    "exit": exit_type,
                })

            for i in range(len(text_overlays) - 1):
                curr_overlay = text_overlays[i]
                next_overlay = text_overlays[i + 1]
                if curr_overlay["appear_at_ms"] + curr_overlay["duration_ms"] > next_overlay["appear_at_ms"]:
                    curr_overlay["duration_ms"] = max(100, next_overlay["appear_at_ms"] - curr_overlay["appear_at_ms"])

        text_layout_obj = {
            "x": text_x,
            "y": text_y,
            "fontSize": text_font_size,
            "color": text_color,
            "fontFamily": text_font,
            "fontWeight": font_weight,
            "textAlign": text_align,
            "entry": entry_type,
            "exit": exit_type,
        }
        if use_pill_bg and not is_light_bg:
            text_layout_obj["pill_bg"] = palette.get("pill_bg", "rgba(10, 12, 18, 0.72)")

        rebuilt_scene = {
            "id": sid,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "narration": narration,
            "layout_style": layout_style,
            "layout_params": layout_params,
            "bg_color": bg_color,
            "transition": scene.get("transition", "crossfade"),
            "subtitles": show_subtitles,
            "text_layout": text_layout_obj,
            "text_overlays": text_overlays,
        }

        if text_only_headline:
            rebuilt_scene["text_only_text"] = text_only_headline
        if scene.get("frame_style"):
            rebuilt_scene["frame_style"] = scene["frame_style"]
        if scene.get("info_card"):
            rebuilt_scene["info_card"] = scene["info_card"]
        if scene.get("sfx"):
            rebuilt_scene["sfx"] = scene["sfx"]
        if scene.get("background"):
            rebuilt_scene["background"] = scene["background"]
        if scene.get("layers"):
            rebuilt_scene["layers"] = scene["layers"]
        if scene.get("cutout"):
            rebuilt_scene["cutout"] = scene["cutout"]
        if scene.get("foreground"):
            rebuilt_scene["foreground"] = scene["foreground"]
        if scene.get("camera_motion"):
            rebuilt_scene["camera_motion"] = scene["camera_motion"]
        if "rotation" in scene:
            rebuilt_scene["rotation"] = scene["rotation"]
        if layout_style != "text_only":
            rebuilt_scene["media"] = media

        new_scenes.append(rebuilt_scene)

    storyboard["scenes"] = new_scenes
    if new_scenes:
        storyboard["total_duration_ms"] = max(s.get("end_ms", 0) for s in new_scenes)
    with open(storyboard_path, "w", encoding="utf-8") as f:
        json.dump(storyboard, f, indent=2, ensure_ascii=False)
    print(f"  [OK] Storyboard reconstruído com paleta editorial '{palette['name']}' em: {storyboard_path}")
    return True

# ── FreeCut Zip Bundle Compiler ────────────────────────────────
TYPOGRAPHY_PRESETS = {
    "minimalist_dark": {
        "color_active": "#FFFFFF",
        "color_inactive": "rgba(255, 255, 255, 0.25)",
        "color_read": "rgba(255, 255, 255, 0.6)",
        "font_family": "Montserrat, sans-serif",
        "font_weight": "800",
        "gsap_active": "opacity: 1.0, scale: 1.08, color: '#FFFFFF', duration: 0.15",
        "gsap_read": "scale: 1.0, opacity: 0.6, color: '#FFFFFF', duration: 0.15",
        "extra_css": ""
    },
    "neon_cyberpunk": {
        "color_active": "#00F2FE",
        "color_inactive": "rgba(255, 255, 255, 0.2)",
        "color_read": "rgba(0, 242, 254, 0.5)",
        "font_family": "Inter, sans-serif",
        "font_weight": "900",
        "gsap_active": "opacity: 1.0, scale: 1.15, y: -10, color: '#00F2FE', duration: 0.2, ease: 'back.out(1.7)'",
        "gsap_read": "scale: 1.0, y: 0, opacity: 0.5, color: '#00F2FE', duration: 0.15",
        "extra_css": "text-shadow: 0 0 10px rgba(0, 242, 254, 0.8), 0 0 20px rgba(0, 242, 254, 0.4);"
    },
    "power_crimson": {
        "color_active": "#DC2626",
        "color_inactive": "rgba(255, 255, 255, 0.2)",
        "color_read": "rgba(220, 38, 38, 0.5)",
        "font_family": "Montserrat, sans-serif",
        "font_weight": "900",
        "gsap_active": "opacity: 1.0, scale: 1.2, color: '#DC2626', duration: 0.12",
        "gsap_read": "scale: 1.0, opacity: 0.5, color: '#DC2626', duration: 0.12",
        "extra_css": "text-decoration: underline; text-decoration-color: #DC2626;"
    },
    "eco_green": {
        "color_active": "#10B981",
        "color_inactive": "rgba(255, 255, 255, 0.2)",
        "color_read": "rgba(16, 185, 129, 0.6)",
        "font_family": "Montserrat, sans-serif",
        "font_weight": "800",
        "gsap_active": "opacity: 1.0, scale: 1.1, color: '#10B981', duration: 0.18",
        "gsap_read": "scale: 1.0, opacity: 0.6, color: '#10B981', duration: 0.18",
        "extra_css": ""
    },
    "marker_yellow": {
        "color_active": "#000000",
        "color_inactive": "rgba(255, 255, 255, 0.25)",
        "color_read": "rgba(255, 255, 255, 0.6)",
        "font_family": "Montserrat, sans-serif",
        "font_weight": "800",
        "gsap_active": "opacity: 1.0, scale: 1.05, backgroundColor: '#FEF08A', color: '#000000', padding: '0 8px', borderRadius: '4px', duration: 0.15",
        "gsap_read": "scale: 1.0, opacity: 0.6, backgroundColor: 'transparent', color: '#FFFFFF', padding: '0 0', duration: 0.15",
        "extra_css": ""
    }
}

INFO_CARD_FONTS = {
    "paper_typewriter": ["Special Elite", "Courier Prime", "Courier New", "PT Mono"],
    "checklist_card": ["Architects Daughter", "Caveat", "Indie Flower", "Shadows Into Light"],
    "futuristic_hud": ["Share Tech Mono", "VT323", "Space Mono", "Fira Code"],
    "minimalist_tag": ["Montserrat", "Inter", "Roboto", "Outfit", "Plus Jakarta Sans"]
}

INFO_CARD_PALETTES = {
    "paper_typewriter": [
        {"bg": "#f4f1ea", "text": "#2b2a27", "border": "#dcd8cf", "accent": "#ff3c3c"},
        {"bg": "#e8e4d9", "text": "#1a1a19", "border": "#cdc8b7", "accent": "#d9534f"},
        {"bg": "#fcfaf2", "text": "#333332", "border": "#e5dfd3", "accent": "#c9302c"}
    ],
    "checklist_card": [
        {"bg": "#ffffea", "text": "#1b2a47", "border": "#e3e3b2", "accent": "#27ae60", "line": "#e74c3c"},
        {"bg": "#f3f9fe", "text": "#2c3e50", "border": "#d2e4f6", "accent": "#2980b9", "line": "#3498db"},
        {"bg": "#fafff5", "text": "#2d3436", "border": "#d5ebd1", "accent": "#2ecc71", "line": "#e17055"}
    ],
    "futuristic_hud": [
        {"bg": "rgba(10, 20, 40, 0.9)", "text": "#00F2FE", "border": "rgba(0, 242, 254, 0.6)", "accent": "#FFDD00", "glow": "0 0 15px rgba(0, 242, 254, 0.8)"},
        {"bg": "rgba(15, 15, 15, 0.9)", "text": "#39FF14", "border": "rgba(57, 255, 20, 0.6)", "accent": "#FF3131", "glow": "0 0 15px rgba(57, 255, 20, 0.8)"},
        {"bg": "rgba(15, 10, 25, 0.9)", "text": "#FF66CC", "border": "rgba(255, 102, 204, 0.6)", "accent": "#00FFFF", "glow": "0 0 15px rgba(255, 102, 204, 0.8)"}
    ],
    "minimalist_tag": [
        {"bg": "rgba(17, 24, 39, 0.9)", "text": "#FFFFFF", "border": "rgba(255, 255, 255, 0.2)", "accent": "#F3F4F6"},
        {"bg": "rgba(255, 255, 255, 0.95)", "text": "#111827", "border": "rgba(17, 24, 39, 0.15)", "accent": "#374151"},
        {"bg": "rgba(31, 41, 55, 0.9)", "text": "#F9FAFB", "border": "rgba(255, 255, 255, 0.2)", "accent": "#E5E7EB"}
    ]
}

EMPHASIS_WORDS = ["ferrari", "sprint", "hybrid", "power", "lights", "snowy", "waterfall", "crash", "desert"]

def select_typography_preset(query):
    q = query.lower()
    if any(k in q for k in ["nature", "forest", "green", "lake", "meadow", "eco", "river", "waterfall", "flower"]):
        return "eco_green"
    elif any(k in q for k in ["tech", "cyber", "digital", "city", "futuristic", "curved", "screen", "traffic", "neon", "lights"]):
        return "neon_cyberpunk"
    elif any(k in q for k in ["racing", "fast", "speed", "ferrari", "power", "crash", "wave", "lion", "sprint", "waves"]):
        return "power_crimson"
    elif any(k in q for k in ["desert", "sun", "sand", "heat", "yellow"]):
        return "marker_yellow"
    return "minimalist_dark"

def get_kinetic_preset_details(preset_index):
    presets = [
        {
            "name": "The Magic",
            "css": """
                @keyframes magicEntry {
                  0% { opacity: 0; letter-spacing: -2px; }
                  100% { opacity: 1; letter-spacing: 0px; }
                }
                .magic-text {
                  animation: magicEntry 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
            """,
            "container_class": "magic-text",
            "gsap_entry": ""
        },
        {
            "name": "Animation Brings",
            "css": """
                .crop-row {
                  opacity: 0;
                  animation: cropEntry 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes cropEntry {
                  0% { opacity: 0; transform: translateY(15px); }
                  100% { opacity: 1; transform: translateY(0); }
                }
            """,
            "container_class": "",
            "gsap_entry": "stagger_delay"
        },
        {
            "name": "Technology Meets",
            "css": """
                .slide-left-row {
                  opacity: 0;
                  animation: slideLeftEntry 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes slideLeftEntry {
                  0% { opacity: 0; transform: translateX(-15px); }
                  100% { opacity: 1; transform: translateX(0); }
                }
            """,
            "container_class": "",
            "gsap_entry": "slide_left_delay"
        },
        {
            "name": "Words Become",
            "css": """
                .col-row {
                  opacity: 0;
                  animation: simpleFade 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes simpleFade {
                  0% { opacity: 0; }
                  100% { opacity: 1; }
                }
            """,
            "container_class": "",
            "gsap_entry": "colision"
        },
        {
            "name": "Creative Animation",
            "css": """
                .track-open {
                  opacity: 0;
                  animation: simpleFade 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                .overshoot {
                  opacity: 0;
                  animation: simpleFade 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes simpleFade {
                  0% { opacity: 0; }
                  100% { opacity: 1; }
                }
            """,
            "container_class": "",
            "gsap_entry": "overshoot"
        },
        {
            "name": "Ideas In Motion",
            "css": """
                @keyframes irisEntry {
                  0% { opacity: 0; clip-path: inset(50% 0 50% 0); }
                  100% { opacity: 1; clip-path: inset(0% 0 0% 0); }
                }
                .iris-container {
                  animation: irisEntry 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
            """,
            "container_class": "iris-container",
            "gsap_entry": ""
        },
        {
            "name": "We Bring",
            "css": """
                .flip-row {
                  opacity: 0;
                  animation: slideLeftEntry 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes slideLeftEntry {
                  0% { opacity: 0; transform: translateX(15px); }
                  100% { opacity: 1; transform: translateX(0); }
                }
            """,
            "container_class": "",
            "gsap_entry": "flip_3d"
        },
        {
            "name": "Creativity In Frame",
            "css": """
                .stretch-row {
                  opacity: 0;
                  animation: slideUpEntry 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes slideUpEntry {
                  0% { opacity: 0; transform: translateY(15px); }
                  100% { opacity: 1; transform: translateY(0); }
                }
            """,
            "container_class": "",
            "gsap_entry": "stretch"
        },
        {
            "name": "Text Into Motion",
            "css": """
                @keyframes deepFocusEntry {
                  0% { opacity: 0; transform: scale(1.05); filter: blur(4px); }
                  100% { opacity: 1; transform: scale(1); filter: blur(0); }
                }
                .deep-focus {
                  animation: deepFocusEntry 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
            """,
            "container_class": "deep-focus",
            "gsap_entry": ""
        }
    ]
    return presets[preset_index]

def split_to_chars(text):
    if not text:
        return ""
    html = ""
    for c in text:
        if c == " ":
            html += '<span class="char" style="display: none;"> </span>'
        elif c == "\n":
            html += '<br/>'
        else:
            char_esc = c
            if char_esc == "<": char_esc = "&lt;"
            elif char_esc == ">": char_esc = "&gt;"
            elif char_esc == "&": char_esc = "&amp;"
            html += f'<span class="char" style="display: none;">{char_esc}</span>'
    return html

def render_hyperframes_subtitles(project_dir, storyboard, words):
    """Generates HTML templates and renders WebM transparent kinetic typography overlays for info_cards."""
    scenes = storyboard.get("scenes", [])
    if not words:
        return
    if not any(s.get("info_card") and (s.get("end_ms", 0) - s.get("start_ms", 0)) >= 5000 for s in scenes):
        return
        
    hf_config = {
      "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
      "paths": {
        "blocks": "compositions",
        "assets": "assets"
      }
    }
        
    # Check if node/npx is available
    import platform
    npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
    try:
        res = subprocess.run([npx_cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print("  [HyperFrames] Warning: npx is not available. Skipping kinetic text rendering (will use text fallback).")
            return
    except Exception:
        print("  [HyperFrames] Warning: npx is not available. Skipping kinetic text rendering (will use text fallback).")
        return
        
    for scene in scenes:
        has_subtitles = False  # Sempre usar legendas nativas do FreeCut, pulando render em WebM
        has_info_card = True if scene.get("info_card") else False
        if has_info_card:
            scene_dur_s = (scene.get("end_ms", 0) - scene.get("start_ms", 0)) / 1000.0
            if scene_dur_s < 5.0:
                has_info_card = False
                
        if not has_subtitles and not has_info_card:
            continue
            
        sid = scene["id"]
        start_ms = scene["start_ms"]
        end_ms = scene["end_ms"]
        duration_s = (end_ms - start_ms) / 1000.0
        
        # Filter words for this scene
        scene_words = [
            w for w in words
            if w.get("start_ms") is not None and w.get("end_ms") is not None
            and w["start_ms"] >= start_ms - 200 and w["start_ms"] < end_ms
        ]
        scene_words.sort(key=lambda x: x["start_ms"])
        
        dest_videos_dir = os.path.join(project_dir, "media", "videos")
        os.makedirs(dest_videos_dir, exist_ok=True)
        
        layout_style = scene.get("layout_style", "single_card")
        if layout_style == "split_info_slide" and has_subtitles:
            if len(scene_words) > 9:
                has_subtitles = False
                scene["subtitles"] = False
                dest_webm_txt = os.path.join(dest_videos_dir, f"{sid}_txt.webm")
                if os.path.exists(dest_webm_txt):
                    try:
                        os.remove(dest_webm_txt)
                        print(f"  [HyperFrames] Removida legenda em cache para {sid} pois tem mais de 9 palavras ({len(scene_words)}) em layout split_info_slide.")
                    except Exception as e:
                        print(f"  [HyperFrames] Falhou ao remover cache de legenda {sid}: {e}")
                        
        if not has_subtitles and not has_info_card:
            continue
            
        # 1. Render kinetic subtitles if active and has words
        if has_subtitles and scene_words:
            dest_webm_txt = os.path.join(dest_videos_dir, f"{sid}_txt.webm")
            if os.path.exists(dest_webm_txt):
                print(f"  [HyperFrames] Legenda cinética para {sid} já existe. Ignorando render.")
            else:
                temp_dir_txt = os.path.join(project_dir, "media", "temp_hyperframes", f"{sid}_txt")
                os.makedirs(temp_dir_txt, exist_ok=True)
                
                layout_style = scene.get("layout_style", "single_card")
                text_layout = scene.get("text_layout", {})
                text_x = text_layout.get("x", 0.0)
                
                if layout_style == "split_info_slide":
                    container_width = 990
                    left_px = 850 if text_x > 0 else 80
                    align = "left"
                    top_px = 340
                else:
                    container_width = 1200
                    left_px = 360
                    align = "center"
                    top_px = 340
                    
                media = scene.get("media", {})
                query = media.get("query", "")
                preset_name = select_typography_preset(query)
                preset = TYPOGRAPHY_PRESETS[preset_name]
                
                rng = random.Random(sid)
                font_choices = ["Montserrat", "Inter", "Google Sans", "Open Sans", "Roboto", "Noto Sans JP"]
                font_family = rng.choice(font_choices) if preset_name != "neon_cyberpunk" else "Inter"
                base_font_size = rng.randint(54, 60)
                
                motion_idx = rng.randint(0, 8)
                motion_preset = get_kinetic_preset_details(motion_idx)
                gsap_entry = motion_preset["gsap_entry"]
                container_class = motion_preset["container_class"]
                
                import math
                total_len = len(scene_words)
                if layout_style == "split_info_slide":
                    num_chunks = 1
                else:
                    num_chunks = max(1, math.ceil(total_len / 4.0))
                chunk_size = total_len // num_chunks
                remainder = total_len % num_chunks
                word_chunks = []
                start_idx = 0
                for idx in range(num_chunks):
                    size = chunk_size + (1 if idx < remainder else 0)
                    word_chunks.append(scene_words[start_idx : start_idx + size])
                    start_idx += size
                    
                glow_active_css = preset['extra_css'] if preset_name == "neon_cyberpunk" else "text-shadow: 0 0 8px rgba(0, 0, 0, 0.1);"
                
                html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Montserrat:wght@400;700;900&family=Open+Sans:wght@400;700&family=Outfit:wght@400;700&family=Plus+Jakarta+Sans:wght@400;700&family=Roboto:wght@400;700;900&family=Noto+Sans+JP&display=swap" rel="stylesheet">
    <style>
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html, body {{
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: transparent;
      }}
      body {{
        font-family: '{font_family}', sans-serif;
      }}
      .text-container {{
        position: absolute;
        width: {container_width}px;
        top: {top_px}px;
        left: {left_px}px;
        padding: 60px 80px;
        font-size: {base_font_size}px;
        line-height: 1.4;
        font-weight: {preset['font_weight']};
        color: {preset['color_inactive']};
        text-align: {align};
        overflow: visible !important;
      }}
      .text-chunk {{
        display: none;
        width: 100%;
        opacity: 0;
        transition: opacity 0.15s ease-in-out;
      }}
      .text-chunk.active-chunk {{
        display: block;
        opacity: 1;
      }}
      .word {{
        display: inline-block;
        opacity: 0.25;
        filter: blur(3px);
        margin-right: 15px;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        will-change: filter, opacity;
        backface-visibility: hidden;
      }}
      .word.active {{
        opacity: 1;
        filter: blur(0);
        color: {preset['color_active']};
        {glow_active_css}
      }}
      .word.passed {{
        opacity: 0.6;
        filter: blur(0);
        color: {preset['color_read']};
      }}
      .word.active.is-red {{
        color: #ff3c3c !important;
        text-shadow: 0 0 20px rgba(255, 60, 60, 0.8) !important;
      }}
      .word.active.is-fire {{
        font-weight: 900;
        background: linear-gradient(135deg, #ff4d00, #ff8c00, #ff0055);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: heat-wave 1s infinite ease-in-out;
      }}
      @keyframes heat-wave {{
        0%, 100% {{ transform: skewX(0deg) scale(1.05); filter: drop-shadow(0 0 0px rgba(255, 77, 0, 0)); }}
        50% {{ transform: skewX(2deg) scale(1.1); filter: drop-shadow(0 0 15px rgba(255, 77, 0, 0.3)); }}
      }}
      {motion_preset['css']}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{duration_s}"
      data-width="1920"
      data-height="1080"
    >
      <div class="text-container {container_class}" id="text-box">
"""
                word_idx_global = 0
                for chunk_idx, chunk_words in enumerate(word_chunks):
                    if not chunk_words:
                        continue
                    chunk_classes = ["text-chunk"]
                    if chunk_idx == 0:
                        chunk_classes.append("active-chunk")
                    if gsap_entry == "stagger_delay":
                        chunk_classes.append("crop-row")
                    elif gsap_entry == "slide_left_delay":
                        chunk_classes.append("slide-left-row")
                    elif gsap_entry == "colision":
                        chunk_classes.append("col-row")
                    elif gsap_entry == "overshoot":
                        chunk_classes.append("track-open")
                    elif gsap_entry == "flip_3d":
                        chunk_classes.append("flip-row")
                    elif gsap_entry == "stretch":
                        chunk_classes.append("stretch-row")
                        
                    chunk_class_str = " ".join(chunk_classes)
                    html_content += f'        <div class="{chunk_class_str}" id="chunk-{chunk_idx}">\n'
                    for w in chunk_words:
                        word_clean = w["word"].lower().strip(".,!?;;()\"'")
                        class_list = ["word"]
                        if word_clean in ["red", "light"]:
                            class_list.append("is-red")
                        elif word_clean in ["blowtorch", "fire", "hot", "sun", "desert", "heat"]:
                            class_list.append("is-fire")
                        class_str = " ".join(class_list)
                        html_content += f'          <span class="{class_str}" id="w{word_idx_global}" data-chunk="{chunk_idx}">{w["word"]}</span>\n'
                        word_idx_global += 1
                    html_content += '        </div>\n'
                    
                html_content += """      </div>
    </div>

    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      
      let currentActiveIndex = -1;
      const totalWords = """ + str(len(scene_words)) + """;
      
      function toggleWordState(index, state) {
        if (state === "active") {
          currentActiveIndex = index;
        } else if (state === "passed" && index === currentActiveIndex) {
          currentActiveIndex = index + 0.5;
        }
        updateHighlight();
      }
      
      function updateHighlight() {
        let activeChunkIdx = 0;
        const activeWordEl = document.getElementById("w" + Math.floor(currentActiveIndex));
        if (activeWordEl) {
          activeChunkIdx = parseInt(activeWordEl.getAttribute("data-chunk"));
        } else if (currentActiveIndex >= totalWords) {
          activeChunkIdx = Math.max(0, document.querySelectorAll('.text-chunk').length - 1);
        }
        
        const chunks = document.querySelectorAll('.text-chunk');
        chunks.forEach((chunk, idx) => {
          if (idx === activeChunkIdx) {
            chunk.classList.add("active-chunk");
          } else {
            chunk.classList.remove("active-chunk");
          }
        });

        for (let i = 0; i < totalWords; i++) {
          const el = document.getElementById("w" + i);
          if (!el) continue;
          el.classList.remove("active", "passed");
          if (i < Math.floor(currentActiveIndex)) {
            el.classList.add("passed");
          } else if (i === currentActiveIndex) {
            el.classList.add("active");
          }
        }
      }
      
      updateHighlight();
"""
                for idx, w in enumerate(scene_words):
                    word_start_s = max(0.0, (w["start_ms"] - start_ms) / 1000.0)
                    word_dur_s = max(0.1, (w["end_ms"] - w["start_ms"]) / 1000.0)
                    html_content += f'      tl.call(toggleWordState, [{idx}, "active"], {word_start_s});\n'
                    html_content += f'      tl.call(toggleWordState, [{idx}, "passed"], {word_start_s + word_dur_s});\n'
                    
                fade_start_s = max(0.1, duration_s - 0.5)
                html_content += f"""
      tl.to("#text-box", {{ opacity: 0, y: -20, duration: 0.4 }}, {fade_start_s});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
                html_path = os.path.join(temp_dir_txt, "index.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                    
                hf_config = {
                  "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                  "paths": {
                    "blocks": "compositions",
                    "assets": "assets"
                  }
                }
                with open(os.path.join(temp_dir_txt, "hyperframes.json"), "w", encoding="utf-8") as f:
                    json.dump(hf_config, f, indent=2)
                    
                print(f"  [HyperFrames] Renderizando legenda cinética para {sid}...")
                render_cmd = [npx_cmd, "-y", "hyperframes", "render", "--format", "webm", "-o", dest_webm_txt]
                try:
                    res_render = subprocess.run(render_cmd, cwd=temp_dir_txt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res_render.returncode == 0 and os.path.exists(dest_webm_txt):
                        print(f"    - [OK] HyperFrames: Legenda cinética WebM criada: {sid}_txt.webm")
                    else:
                        print(f"    - [Warning] HyperFrames falhou ao renderizar {sid}_txt.webm. Stderr: {res_render.stderr}")
                except Exception as e:
                    print(f"    - [Warning] Erro ao processar legenda para {sid}_txt: {e}")
                    
        # 2. Render Info Card if active
        if has_info_card:
            dest_webm_card = os.path.join(dest_videos_dir, f"{sid}_card.webm")
            if os.path.exists(dest_webm_card):
                print(f"  [HyperFrames] Card de informação para {sid} já existe. Ignorando render.")
            else:
                temp_dir_card = os.path.join(project_dir, "media", "temp_hyperframes", f"{sid}_card")
                os.makedirs(temp_dir_card, exist_ok=True)
                
                info_card = scene.get("info_card") or {}
                card_style = info_card.get("style", "paper_typewriter")
                if card_style not in ["paper_typewriter", "checklist_card", "futuristic_hud", "minimalist_tag"]:
                    card_style = "paper_typewriter"
                    
                rng_card = random.Random(sid + "_card")
                position = info_card.get("position")
                if not position or position == "random":
                    position = rng_card.choice(["top_left", "top_right", "bottom_left", "bottom_right"])
                    
                title = info_card.get("title", "")
                content = info_card.get("content", "")
                items = info_card.get("items", [])
                
                # Robust fallback: if all text fields are missing/empty, populate them from scene narration
                if not title and not content and not items:
                    scene_narration = scene.get("narration", "")
                    if card_style == "checklist_card":
                        words_split = scene_narration.split()
                        if len(words_split) > 6:
                            half = len(words_split) // 2
                            items = [" ".join(words_split[:half]), " ".join(words_split[half:])]
                        else:
                            items = [scene_narration] if scene_narration else ["Anotação"]
                        title = "CHECKLIST"
                    else:
                        title = "INFO"
                        if scene_narration:
                            content = scene_narration if len(scene_narration) <= 50 else scene_narration[:47] + "..."
                        else:
                            content = "Detalhe importante"
                
                card_font = rng_card.choice(INFO_CARD_FONTS[card_style])
                card_palette = rng_card.choice(INFO_CARD_PALETTES[card_style])
                card_rotation = rng_card.uniform(-2.5, 2.5) if card_style in ["paper_typewriter", "checklist_card"] else rng_card.uniform(-0.8, 0.8)
                card_scale = round(rng_card.uniform(0.9, 1.1), 3)
                
                pos_styles = ""
                if position == "top_left":
                    pos_styles = "top: 60px; left: 80px;"
                elif position == "top_right":
                    pos_styles = "top: 60px; left: 1300px;"
                elif position == "bottom_left":
                    pos_styles = "top: 570px; left: 80px;"
                else:
                    pos_styles = "top: 570px; left: 1300px;"
                    
                # Regenerate card CSS, HTML, and JS bindings for this index.html
                card_css = f"""
      .info-card {{
        position: absolute;
        width: 540px;
        z-index: 100;
        opacity: 0;
        transform: scale(0.9);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        {pos_styles}
      }}
      .cursor {{
        display: none;
        font-weight: bold;
        opacity: 1;
      }}
                """
                if card_style == "paper_typewriter":
                    card_css += f"""
      .info-card.paper_typewriter {{
        background: {card_palette['bg']};
        border: 1px solid {card_palette['border']};
        border-top: 15px solid {card_palette['accent']};
        border-radius: 4px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15), 0 3px 6px rgba(0,0,0,0.1);
        padding: 30px;
        font-family: '{card_font}', Courier, monospace;
        color: {card_palette['text']};
        transform: rotate({card_rotation}deg) scale({card_scale});
      }}
      .info-card.paper_typewriter .card-title {{
        font-size: 28px;
        font-weight: bold;
        border-bottom: 2px dashed {card_palette['border']};
        padding-bottom: 12px;
        margin-bottom: 18px;
        text-transform: uppercase;
        color: {card_palette['accent']};
      }}
      .info-card.paper_typewriter .card-body {{
        font-size: 23px;
        line-height: 1.6;
        white-space: pre-wrap;
      }}
                    """
                elif card_style == "checklist_card":
                    card_css += f"""
      .info-card.checklist_card {{
        background: {card_palette['bg']};
        border-left: 6px solid {card_palette['line']};
        border-radius: 8px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.06);
        padding: 30px 30px 30px 45px;
        font-family: '{card_font}', cursive;
        color: {card_palette['text']};
        transform: rotate({card_rotation}deg) scale({card_scale});
        background-image: linear-gradient({card_palette['border']} 1px, transparent 1px);
        background-size: 100% 44px;
        line-height: 44px;
      }}
      .info-card.checklist_card .card-title {{
        font-size: 32px;
        font-weight: 900;
        margin-bottom: 24px;
        color: {card_palette['text']};
        text-decoration: underline;
        text-transform: uppercase;
      }}
      .info-card.checklist_card .checklist-item {{
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        font-size: 25px;
      }}
      .info-card.checklist_card .checkbox {{
        width: 30px;
        height: 30px;
        border: 2px solid {card_palette['text']};
        border-radius: 4px;
        margin-right: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        font-weight: bold;
        line-height: 1;
        flex-shrink: 0;
      }}
      .info-card.checklist_card .checkbox .check-mark {{
        opacity: 0;
        transform: scale(0);
        color: {card_palette['accent']};
      }}
                    """
                elif card_style == "futuristic_hud":
                    card_css += f"""
      .info-card.futuristic_hud {{
        background: {card_palette['bg']};
        border: 1px solid {card_palette['border']};
        box-shadow: {card_palette['glow']};
        padding: 26px;
        font-family: '{card_font}', monospace;
        color: #FFFFFF;
        backdrop-filter: blur(10px);
        border-radius: 2px;
        transform: scale({card_scale});
      }}
      .info-card.futuristic_hud::before {{
        content: '';
        position: absolute;
        top: -1px; left: -1px;
        width: 20px; height: 20px;
        border-top: 3px solid {card_palette['text']};
        border-left: 3px solid {card_palette['text']};
      }}
      .info-card.futuristic_hud::after {{
        content: '';
        position: absolute;
        bottom: -1px; right: -1px;
        width: 20px; height: 20px;
        border-bottom: 3px solid {card_palette['text']};
        border-right: 3px solid {card_palette['text']};
      }}
      .info-card.futuristic_hud .card-title {{
        font-size: 26px;
        font-weight: bold;
        letter-spacing: 2px;
        margin-bottom: 12px;
        text-transform: uppercase;
        border-bottom: 1px solid {card_palette['border']};
        padding-bottom: 8px;
        color: {card_palette['text']};
      }}
      .info-card.futuristic_hud .card-body {{
        font-size: 22px;
        line-height: 1.5;
        white-space: pre-wrap;
        color: #E2E8F0;
      }}
                    """
                elif card_style == "minimalist_tag":
                    card_css += f"""
      .info-card.minimalist_tag {{
        background: {card_palette['bg']};
        border: 1px solid {card_palette['border']};
        padding: 24px 30px;
        border-radius: 6px;
        font-family: '{card_font}', sans-serif;
        color: {card_palette['text']};
        transform: scale({card_scale});
      }}
      .info-card.minimalist_tag .card-title {{
        font-size: 22px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
        color: {card_palette['accent']};
      }}
      .info-card.minimalist_tag .card-body {{
        font-size: 24px;
        font-weight: 500;
        white-space: pre-wrap;
      }}
                    """

                if card_style == "checklist_card":
                    items_html = ""
                    for item_idx, item in enumerate(items):
                        item_chars = split_to_chars(item)
                        items_html += f"""
          <div class="checklist-item" id="item-{item_idx}">
            <div class="checkbox">
              <span class="check-mark" style="opacity: 0; transform: scale(0);">✓</span>
            </div>
            <span class="item-text">{item_chars}<span class="cursor">_</span></span>
          </div>
                        """
                    title_chars = split_to_chars(title)
                    card_html = f"""
      <div class="info-card {card_style}">
        <div class="card-title">{title_chars}<span class="cursor">_</span></div>
        <div class="card-body">
          {items_html}
        </div>
      </div>
                    """
                else:
                    title_chars = split_to_chars(title) if title else ""
                    content_chars = split_to_chars(content) if content else ""
                    card_html = f"""
      <div class="info-card {card_style}">
        {"<div class='card-title'>" + title_chars + "<span class='cursor'>_</span></div>" if title else ""}
        <div class="card-body">{content_chars}<span class="cursor">_</span></div>
      </div>
                    """

                if card_style == "checklist_card":
                    card_js_call = "setupChecklistAnimation();"
                    card_js_funcs = """
      function setupChecklistAnimation() {
        const card = document.querySelector('.info-card');
        tl.to(card, { opacity: 1, scale: 1.0, duration: 0.4, ease: "back.out(1.2)" }, 0.1);
        
        const duration = parseFloat(document.getElementById('root').getAttribute('data-duration'));
        
        const titleCursor = document.querySelector('.card-title .cursor');
        const titleChars = document.querySelectorAll('.card-title .char');
        const items = document.querySelectorAll('.checklist-item');
        const numItems = items.length;
        
        const hasTitle = titleChars.length > 0;
        const itemOverhead = numItems * 0.3;
        const overhead = 0.4 + (hasTitle ? 0.15 : 0) + itemOverhead;
        const availableTime = Math.max(0.5, duration - 2.0 - overhead);
        
        let titleTime = 0;
        let itemsTime = availableTime;
        
        if (hasTitle) {
          titleTime = Math.min(availableTime * 0.3, titleChars.length * 0.035);
          itemsTime = availableTime - titleTime;
        }
        
        if (titleCursor && titleChars.length > 0) {
          const titleStagger = titleTime / titleChars.length;
          tl.set(titleCursor, { display: "inline-block", opacity: 1 }, 0.4);
          tl.to(titleCursor, { opacity: 0, duration: 0.2, repeat: Math.ceil(titleTime / 0.4) * 2, yoyo: true, ease: "steps(1)" }, 0.4);
          tl.to(titleChars, { display: "inline", duration: 0.001, stagger: titleStagger }, 0.4);
          tl.set(titleCursor, { display: "none" }, 0.4 + titleTime);
        }
        
        let nextStartTime = 0.4 + titleTime + 0.15;
        
        if (numItems > 0) {
          const timePerItem = itemsTime / numItems;
          
          items.forEach((item, index) => {
            const itemChars = item.querySelectorAll('.item-text .char');
            const checkMark = item.querySelector('.check-mark');
            const itemCursor = item.querySelector('.cursor');
            
            const checkMarkDur = Math.min(0.2, timePerItem * 0.3);
            const pauseDur = Math.min(0.2, timePerItem * 0.2);
            const typingDur = Math.max(0.1, timePerItem - checkMarkDur - pauseDur);
            
            const itemStagger = itemChars.length > 0 ? typingDur / itemChars.length : 0.03;
            
            tl.set(itemCursor, { display: "inline-block", opacity: 1 }, nextStartTime);
            tl.to(itemCursor, { opacity: 0, duration: 0.2, repeat: Math.ceil(typingDur / 0.4) * 2, yoyo: true, ease: "steps(1)" }, nextStartTime);
            tl.to(itemChars, { display: "inline", duration: 0.001, stagger: itemStagger }, nextStartTime);
            
            const itemEndTime = nextStartTime + typingDur;
            tl.set(itemCursor, { display: "none" }, itemEndTime);
            tl.to(checkMark, { opacity: 1, scale: 1.0, duration: checkMarkDur, ease: "back.out(1.5)" }, itemEndTime);
            
            nextStartTime = itemEndTime + checkMarkDur + pauseDur;
          });
        }
        
        tl.to(card, { opacity: 0, scale: 0.9, duration: 0.3, ease: "power2.in" }, duration - 0.3);
      }
                    """
                else:
                    card_js_call = "setupCardAnimation();"
                    card_js_funcs = """
      function setupCardAnimation() {
        const card = document.querySelector('.info-card');
        tl.to(card, { opacity: 1, scale: 1.0, duration: 0.4, ease: "back.out(1.2)" }, 0.1);
        
        const duration = parseFloat(document.getElementById('root').getAttribute('data-duration'));
        
        const titleCursor = document.querySelector('.card-title .cursor');
        const titleChars = document.querySelectorAll('.card-title .char');
        const bodyCursor = document.querySelector('.card-body .cursor');
        const bodyChars = document.querySelectorAll('.card-body .char');
        
        const overhead = (titleChars.length > 0 && bodyChars.length > 0) ? 0.55 : 0.4;
        const availableTime = Math.max(0.5, duration - 2.0 - overhead);
        
        let titleTime = 0;
        let bodyTime = availableTime;
        
        if (titleChars.length > 0 && bodyChars.length > 0) {
          titleTime = Math.min(availableTime * 0.35, titleChars.length * 0.035);
          bodyTime = availableTime - titleTime;
        } else if (titleChars.length > 0) {
          titleTime = availableTime;
          bodyTime = 0;
        }
        
        if (titleCursor && titleChars.length > 0) {
          const titleStagger = titleTime / titleChars.length;
          tl.set(titleCursor, { display: "inline-block", opacity: 1 }, 0.4);
          tl.to(titleCursor, { opacity: 0, duration: 0.2, repeat: Math.ceil(titleTime / 0.4) * 2, yoyo: true, ease: "steps(1)" }, 0.4);
          tl.to(titleChars, { display: "inline", duration: 0.001, stagger: titleStagger }, 0.4);
          tl.set(titleCursor, { display: "none" }, 0.4 + titleTime);
        }
        
        let bodyStartTime = 0.4;
        if (titleChars.length > 0) {
          bodyStartTime = 0.4 + titleTime + 0.15;
        }
        
        if (bodyCursor && bodyChars.length > 0) {
          const bodyStagger = bodyTime / bodyChars.length;
          tl.set(bodyCursor, { display: "inline-block", opacity: 1 }, bodyStartTime);
          tl.to(bodyCursor, { opacity: 0, duration: 0.2, repeat: Math.ceil(bodyTime / 0.4) * 2, yoyo: true, ease: "steps(1)" }, bodyStartTime);
          tl.to(bodyChars, { display: "inline", duration: 0.001, stagger: bodyStagger }, bodyStartTime);
          tl.set(bodyCursor, { display: "none" }, bodyStartTime + bodyTime);
        }
        
        tl.to(card, { opacity: 0, scale: 0.9, duration: 0.3, ease: "power2.in" }, duration - 0.3);
      }
                    """

                html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Architects+Daughter&family=Caveat:wght@400;700&family=Courier+Prime:ital,wght@0,400;0,700;1,400;1,700&family=Fira+Code:wght@400;700&family=Indie+Flower&family=Inter:wght@400;700;900&family=Montserrat:wght@400;700;900&family=Open+Sans:wght@400;700&family=Outfit:wght@400;700&family=PT+Mono&family=Plus+Jakarta+Sans:wght@400;700&family=Roboto:wght@400;700;900&family=Shadows+Into+Light&family=Share+Tech+Mono&family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700&family=Special+Elite&family=VT323&display=swap" rel="stylesheet">
    <style>
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html, body {{
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: transparent;
      }}
      {card_css}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{duration_s}"
      data-width="1920"
      data-height="1080"
    >
      {card_html}
    </div>

    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {card_js_call}
      window.__timelines["main"] = tl;
      {card_js_funcs}
    </script>
  </body>
</html>
"""
                html_path = os.path.join(temp_dir_card, "index.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                    
                with open(os.path.join(temp_dir_card, "hyperframes.json"), "w", encoding="utf-8") as f:
                    json.dump(hf_config, f, indent=2)
                    
                print(f"  [HyperFrames] Renderizando card de informação para {sid}...")
                dest_mov_temp = os.path.join(temp_dir_card, "temp_render.mov")
                render_cmd = [npx_cmd, "-y", "hyperframes", "render", "--format", "mov", "-o", dest_mov_temp]
                try:
                    res_render = subprocess.run(render_cmd, cwd=temp_dir_card, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res_render.returncode == 0 and os.path.exists(dest_mov_temp):
                        # Calculate crop offsets based on card position
                        crop_x, crop_y = 50, 35
                        if position == "top_right":
                            crop_x, crop_y = 1270, 35
                        elif position == "bottom_left":
                            crop_x, crop_y = 50, 545
                        elif position == "bottom_right":
                            crop_x, crop_y = 1270, 545
                            
                        # Crop and convert using FFmpeg to 600x500 WebM with yuva420p format
                        ffmpeg_cmd = [
                            "ffmpeg", "-y", "-i", dest_mov_temp,
                            "-filter_complex", f"crop=600:500:{crop_x}:{crop_y}",
                            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                            "-deadline", "realtime", dest_webm_card
                        ]
                        res_ffmpeg = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Clean up temp mov
                        try: os.remove(dest_mov_temp)
                        except Exception: pass
                        
                        if res_ffmpeg.returncode == 0 and os.path.exists(dest_webm_card):
                            print(f"    - [OK] HyperFrames: Card WebM recortado transparente criado: {sid}_card.webm")
                        else:
                            print(f"    - [Warning] FFmpeg falhou ao recortar e converter o card para WebM.")
                    else:
                        print(f"    - [Warning] HyperFrames falhou ao renderizar {sid}_card.webm. Stderr: {res_render.stderr}")
                except Exception as e:
                    print(f"    - [Warning] Erro ao processar card para {sid}_card: {e}")
                    
    # Clean up temp folder
    # temp_hf_dir = os.path.join(project_dir, "media", "temp_hyperframes")
    # if os.path.exists(temp_hf_dir):
    #     try:
    #         shutil.rmtree(temp_hf_dir)
    #     except Exception:
    #         pass

def _append_text_item_with_keyframes(
    items,
    all_keyframes,
    item_id,
    track_id,
    from_f,
    dur_f,
    label,
    text,
    font_size,
    font_family,
    font_weight,
    color,
    text_align,
    pos_x,
    pos_y,
    text_width,
    text_height,
    entry_type,
    exit_type,
    is_text_only=False,
    palette=None,
    layout_style="full_screen",
    is_light_bg=False,
    pill_bg=None,
):
    fam_clean, weight_clean = editorial_engine.sanitize_font_and_weight(font_family, font_weight)
    rng_txt = random.Random(int(hashlib.md5(f"{item_id}_{text}".encode("utf-8")).hexdigest()[:8], 16))
    palette_eff = palette or editorial_engine.EDITORIAL_FONT_PALETTES["editorial_documentary"]

    word_count = max(1, len(text.split()))
    if fam_clean in editorial_engine.SINGLE_WEIGHT_FONTS or is_text_only:
        letter_spacing = float(palette_eff.get("display_tracking", 1.5))
    else:
        letter_spacing = float(palette_eff.get("body_tracking", -0.5))

    if is_light_bg:
        stroke_opt = {"width": 0, "color": "transparent"}
        shadow_opt = {"offsetX": 0, "offsetY": 0, "blur": 0, "color": "transparent"}
    elif pill_bg and not is_text_only:
        stroke_opt = {"width": 2, "color": "rgba(0,0,0,0.65)"}
        shadow_opt = {"offsetX": 0, "offsetY": 4, "blur": 14, "color": "rgba(0,0,0,0.85)"}
    else:
        stroke_w = 3 if font_size <= 82 else 4
        stroke_opt = {"width": stroke_w, "color": "rgba(0,0,0,0.92)"}
        shadow_opt = {"offsetX": 0, "offsetY": 6, "blur": 20, "color": "rgba(0,0,0,0.92)"}

    spans, span_layout = editorial_engine.build_editorial_spans(
        text=text,
        palette=palette_eff,
        base_color=color,
        rng=rng_txt,
        layout_style=layout_style,
        is_light_bg=is_light_bg,
    )

    text_motion = editorial_engine.build_native_text_motion(
        entry_hint=entry_type,
        exit_hint=exit_type,
        dur_f=dur_f,
        word_count=word_count,
        rng=rng_txt,
        is_text_only=is_text_only,
    )

    text_item = {
        "id": item_id,
        "trackId": track_id,
        "from": from_f,
        "durationInFrames": dur_f,
        "label": label,
        "type": "text",
        "text": "\n".join(s["text"] for s in spans) if (spans and span_layout == "stack") else text,
        "fontSize": font_size,
        "fontFamily": fam_clean,
        "fontWeight": weight_clean,
        "color": color,
        "textAlign": text_align,
        "verticalAlign": "middle",
        "lineHeight": 1.12 if is_text_only else 1.16,
        "letterSpacing": letter_spacing,
        "transform": {
            "x": pos_x,
            "y": pos_y,
            "width": text_width,
            "height": text_height,
        },
        "stroke": stroke_opt,
        "textShadow": shadow_opt,
        "textMotion": text_motion,
        "originId": item_id,
    }
    if spans and span_layout:
        text_item["textSpans"] = spans
        text_item["spanLayout"] = span_layout
    if pill_bg and not is_light_bg and not is_text_only and span_layout != "stack":
        text_item["backgroundColor"] = pill_bg
        text_item["backgroundRadius"] = 14
        text_item["textPadding"] = 16

    items.append(text_item)


def _build_ptbr_subtitles(project_dir, scenes, items, all_keyframes, font_family="Inter Tight"):
    """Adds full-video PT-BR translation subtitles positioned in the center/middle of the screen (y=0)."""
    ptbr_path = os.path.join(project_dir, "scenes_ptbr.json")
    pt_map = {}
    if os.path.exists(ptbr_path):
        try:
            with open(ptbr_path, "r", encoding="utf-8") as f:
                pt_list = json.load(f)
            pt_map = {s["id"]: s.get("narration_pt", "") for s in pt_list}
        except Exception as e:
            print(f"  [Warning] Error loading scenes_ptbr.json: {e}")

    fam_clean, weight_clean = editorial_engine.sanitize_font_and_weight(font_family, "bold")
    has_any = False
    for scene in scenes:
        sid = scene["id"]
        pt_text = pt_map.get(sid) or scene.get("narration_pt", "")
        if not pt_text or not pt_text.strip():
            continue

        has_any = True
        start_ms = scene["start_ms"]
        end_ms = scene["end_ms"]
        start_f = ms_to_frames(start_ms)
        dur_f = max(1, ms_to_frames(end_ms - start_ms))
        item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sub_ptbr"))
        rng_pt = random.Random(int(hashlib.md5(item_id.encode("utf-8")).hexdigest()[:8], 16))
        tm = editorial_engine.build_native_text_motion("fade-up", "fade-down", dur_f, len(pt_text.split()), rng_pt)

        items.append({
            "id": item_id,
            "trackId": "track_sub_ptbr",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_sub_ptbr",
            "type": "text",
            "text": pt_text.strip(),
            "fontSize": 46,
            "fontFamily": fam_clean,
            "fontWeight": weight_clean,
            "color": "#FFFFFF",
            "textAlign": "center",
            "verticalAlign": "middle",
            "lineHeight": 1.25,
            "letterSpacing": -0.4,
            "transform": {
                "x": 0,
                "y": 0,
                "width": 1600,
                "height": 220,
            },
            "stroke": {"width": 3, "color": "rgba(0,0,0,0.90)"},
            "textShadow": {"offsetX": 0, "offsetY": 5, "blur": 18, "color": "rgba(0,0,0,0.92)"},
            "textMotion": tm,
            "originId": item_id,
        })
    return has_any


def _build_subtitles(project_dir, scene, items, all_keyframes, add_media_fn, font_family="Inter Tight", palette=None):
    sid = scene["id"]
    start_ms = scene["start_ms"]
    end_ms = scene["end_ms"]
    start_f = ms_to_frames(start_ms)
    dur_f = ms_to_frames(end_ms - start_ms)
    palette_eff = palette or editorial_engine.EDITORIAL_FONT_PALETTES["editorial_documentary"]

    # Add info card overlay (if rendered) on track_fg_2 (ABOVE media and separate from adjustment layers)
    card_filename = f"{sid}_card.webm"
    card_filepath = os.path.join(project_dir, "media", "videos", card_filename)

    if os.path.exists(card_filepath):
        info_card = scene.get("info_card") or {}
        position = info_card.get("position")
        if not position or position == "random":
            rng_card = random.Random(sid + "_card")
            position = rng_card.choice(["top_left", "top_right", "bottom_left", "bottom_right"])

        center_x, center_y = -610, -255
        if position == "top_right":
            center_x, center_y = 610, -255
        elif position == "bottom_left":
            center_x, center_y = -610, 255
        elif position == "bottom_right":
            center_x, center_y = 610, 255

        media_id = add_media_fn(card_filepath)
        overlay_id = get_uid()

        card_meta = get_video_metadata(card_filepath)
        card_dur = card_meta["duration"] if card_meta["duration"] > 0.0 else dur_f / 30.0
        card_dur_f = max(1, int(round(card_dur * 30.0)))
        card_end_f = min(dur_f, card_dur_f)

        items.append({
            "id": overlay_id,
            "trackId": "track_fg_2",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_info_card",
            "type": "video",
            "mediaRef": media_id,
            "sourceWidth": 600,
            "sourceHeight": 500,
            "sourceStart": 0,
            "sourceEnd": card_end_f,
            "sourceDuration": card_dur_f,
            "sourceFps": FPS,
            "volume": -60,
            "transform": {
                "x": center_x,
                "y": center_y,
                "width": 600,
                "height": 500,
            },
            "originId": overlay_id,
        })

    # Detect if media is missing to show custom text overlay
    media_missing = False
    entry_type = "rise"
    exit_type = "fade-down"
    pill_bg = None

    filepath_mp4 = os.path.join(project_dir, "media", "videos", f"{sid}.mp4")
    layout_style = scene.get("layout_style", "single_card")
    if os.path.exists(filepath_mp4):
        filepath = filepath_mp4
    elif layout_style == "text_only":
        filename_png = f"{sid}_bg.png"
        filepath = os.path.join(project_dir, "media", "processed", filename_png)
        if not os.path.exists(filepath):
            filepath = os.path.join(project_dir, "media", "images", filename_png)
    else:
        filename_png = f"{sid}_E01.png"
        filepath = os.path.join(project_dir, "media", "processed", filename_png)
        if not os.path.exists(filepath):
            filepath = os.path.join(project_dir, "media", "images", filename_png)

    if not os.path.exists(filepath):
        matches = (
            glob.glob(os.path.join(project_dir, "media", "processed", f"{sid}_*.png"))
            + glob.glob(os.path.join(project_dir, "media", "images", f"{sid}_*"))
            + glob.glob(os.path.join(project_dir, "media", "videos", f"{sid}.*"))
            + glob.glob(os.path.join(project_dir, "media", "videos", f"{sid}_*"))
        )
        if not matches:
            media_missing = True

    bg_color_hex = str(scene.get("bg_color") or scene.get("background_color") or "#000000").upper()
    is_light_bg = bg_color_hex in {"#FAF9F6", "#F5F5F7", "#F9F9FB", "#F4F4F5", "#FAF6F0", "#F5EFEB", "#EDE7E1", "#F6F0E5", "#FFFFFF"}

    if media_missing:
        words_path = os.path.join(project_dir, "words.json")
        words = load_words_normalized(words_path)
        scene_words = [
            w for w in words
            if w.get("start_ms") is not None and w.get("end_ms") is not None
            and w["start_ms"] >= start_ms - 200 and w["start_ms"] < end_ms
        ]
        scene_words.sort(key=lambda x: x["start_ms"])

        text_overlays = []
        if scene_words:
            current_chunk = []
            chunk_start = None
            for w in scene_words:
                if not current_chunk:
                    chunk_start = w["start_ms"]
                current_chunk.append(w["word"])
                clean_word = w["word"].strip()
                has_punct = any(p in clean_word for p in [".", ",", "!", "?", ";"])
                if len(current_chunk) >= 4 or has_punct or (w["end_ms"] - chunk_start > 2200):
                    text_overlays.append({
                        "text": " ".join(current_chunk),
                        "appear_at_ms": chunk_start,
                        "duration_ms": max(800, w["end_ms"] - chunk_start),
                    })
                    current_chunk = []
                    chunk_start = None
            if current_chunk:
                text_overlays.append({
                    "text": " ".join(current_chunk),
                    "appear_at_ms": chunk_start if chunk_start is not None else start_ms,
                    "duration_ms": max(800, end_ms - (chunk_start if chunk_start is not None else start_ms)),
                })
        else:
            text_overlays = [{
                "text": scene.get("narration", ""),
                "appear_at_ms": start_ms,
                "duration_ms": end_ms - start_ms,
            }]

        font_size = 72
        font_color = "#111827" if is_light_bg else "#FFFFFF"
        font_family = palette_eff.get("body_font", font_family)
        font_weight = palette_eff.get("body_weight", "bold")
        text_align = "center"
        text_x = 0.0
        text_y = 0.0
        pos_x = 0
        pos_y = 0
        text_width = 1600
        entry_type = "rise"
        exit_type = "fade-down"
    else:
        text_overlays = scene.get("text_overlays", [])
        if not text_overlays:
            return

        text_layout = scene.get("text_layout", {})
        font_size = text_layout.get("fontSize", 65)
        font_color = text_layout.get("color", "#111827" if is_light_bg else "#FFFFFF")
        font_family = text_layout.get("fontFamily", font_family)
        font_weight = text_layout.get("fontWeight", "bold")
        text_align = text_layout.get("textAlign", "center")
        text_x = text_layout.get("x", 0.0)
        text_y = text_layout.get("y", 0.32)
        entry_type = text_layout.get("entry", "rise")
        exit_type = text_layout.get("exit", "fade-down")
        pill_bg = text_layout.get("pill_bg")

        pos_x, pos_y = norm_to_px(text_x, text_y)
        if layout_style == "split_info_slide":
            layout_params = scene.get("layout_params", {})
            split_type = layout_params.get("split_type", "horizontal")
            if split_type == "horizontal":
                text_width = 780
                pos_x = 470 if text_x > 0 else -470
            else:
                text_width = min(1500, (960 - abs(pos_x)) * 2 - 40)
        else:
            text_width = min(1500, (960 - abs(pos_x)) * 2 - 40)

    is_text_only = (layout_style == "text_only")
    is_solid_bg = layout_style in ("text_only", "single_card", "split_info_slide")

    for idx, overlay in enumerate(text_overlays):
        txt = overlay.get("text", "")
        if not txt.strip():
            continue

        t_start = max(start_ms, overlay.get("appear_at_ms", start_ms))
        t_dur = min(end_ms - t_start, overlay.get("duration_ms", end_ms - t_start))

        t_start_f = ms_to_frames(t_start)
        t_dur_f = max(1, ms_to_frames(t_dur))

        if idx < len(text_overlays) - 1:
            next_overlay = text_overlays[idx + 1]
            next_start = max(start_ms, next_overlay.get("appear_at_ms", start_ms))
            next_start_f = ms_to_frames(next_start)
            if next_start_f > t_start_f:
                t_dur_f = min(t_dur_f, next_start_f - t_start_f)

        text_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sub_{idx}"))
        display_txt = txt.upper() if is_text_only else txt

        o_font_size = overlay.get("fontSize", font_size)
        o_font_family = overlay.get("fontFamily", font_family)
        o_font_weight = overlay.get("fontWeight", font_weight)
        o_x = overlay.get("x", text_x)
        o_y = overlay.get("y", text_y)
        if layout_style == "split_info_slide" and (scene.get("layout_params") or {}).get("split_type", "horizontal") == "horizontal":
            o_pos_x = pos_x
            _, o_pos_y = norm_to_px(0.0, o_y)
        else:
            o_pos_x, o_pos_y = norm_to_px(o_x, o_y) if (o_x != text_x or o_y != text_y) else (pos_x, pos_y)
        o_entry = overlay.get("entry", entry_type)
        o_exit = overlay.get("exit", exit_type)

        hl_size = o_font_size + 4 if (is_solid_bg and not is_text_only) else o_font_size
        if is_text_only:
            box_h = 420
        elif layout_style == "split_info_slide":
            box_h = 290
        else:
            box_h = 245

        _append_text_item_with_keyframes(
            items=items,
            all_keyframes=all_keyframes,
            item_id=text_id,
            track_id="track_text",
            from_f=t_start_f,
            dur_f=t_dur_f,
            label=f"{sid}_sub_{idx}",
            text=display_txt,
            font_size=hl_size,
            font_family=o_font_family,
            font_weight=o_font_weight,
            color=font_color,
            text_align=text_align,
            pos_x=o_pos_x,
            pos_y=o_pos_y,
            text_width=text_width,
            text_height=box_h,
            entry_type=o_entry,
            exit_type=o_exit,
            is_text_only=is_text_only,
            palette=palette_eff,
            layout_style=layout_style,
            is_light_bg=is_light_bg,
            pill_bg=pill_bg,
        )

def _build_scene_items(project_dir, scene, items, all_keyframes, add_media_fn, global_style="editorial_film", palette=None):
    sid = scene["id"]
    layout_style = scene.get("layout_style", "single_card")
    start_ms = scene["start_ms"]
    end_ms = scene["end_ms"]
    duration_ms = end_ms - start_ms
    start_f = ms_to_frames(start_ms)
    dur_f = max(2, ms_to_frames(duration_ms))
    palette_eff = palette or editorial_engine.EDITORIAL_FONT_PALETTES["editorial_documentary"]
    accent_hex = (palette_eff.get("accents") or ["#FBBF24"])[0]

    is_video = False
    is_lottie = False

    if layout_style == "text_only":
        filename_png = f"{sid}_bg.png"
        filepath = os.path.join(project_dir, "media", "processed", filename_png)
        if not os.path.exists(filepath):
            filepath = os.path.join(project_dir, "media", "images", filename_png)
    else:
        media = scene.get("media", {})
        source_type = media.get("source_type", "image")

        vid_candidates = (
            [os.path.join(project_dir, "media", "videos", f"{sid}{ext}") for ext in (".mp4", ".webm", ".mov")]
            + sorted(glob.glob(os.path.join(project_dir, "media", "videos", f"{sid}_*")))
        )
        vid_match = next((vp for vp in vid_candidates if os.path.isfile(vp)), None)
        lottie_rel_path = media.get("lottie_path")

        if source_type == "lottie" and lottie_rel_path:
            is_lottie = True
            filepath = os.path.join(project_dir, lottie_rel_path)
        elif source_type == "video" and vid_match:
            is_video = True
            filepath = vid_match
        else:
            filename_png = f"{sid}_E01.png"
            filepath = os.path.join(project_dir, "media", "processed", filename_png)
            if not os.path.exists(filepath):
                proc_matches = sorted(glob.glob(os.path.join(project_dir, "media", "processed", f"{sid}_*.png")))
                if proc_matches:
                    filepath = proc_matches[0]
                else:
                    filepath = os.path.join(project_dir, "media", "images", filename_png)

    if not os.path.exists(filepath):
        matches = sorted(glob.glob(os.path.join(project_dir, "media", "images", f"{sid}_*")))
        if matches:
            filepath = matches[0]
            if filepath.lower().endswith(".json"):
                is_lottie = True
        else:
            vid_fallbacks = (
                [os.path.join(project_dir, "media", "videos", f"{sid}{ext}") for ext in (".mp4", ".webm", ".mov")]
                + sorted(glob.glob(os.path.join(project_dir, "media", "videos", f"{sid}_*")))
            )
            vid_fb = next((vp for vp in vid_fallbacks if os.path.isfile(vp)), None)
            if vid_fb:
                filepath = vid_fb
                is_video = True
            else:
                print(f"      [Warning] Nenhuma mídia encontrada no disco para a cena {sid}")
                return

    media_id = add_media_fn(filepath)
    item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_anchor"))

    if is_video:
        meta = get_video_metadata(filepath)
        src_w, src_h = meta["width"], meta["height"]
    elif is_lottie:
        src_w, src_h = get_lottie_dimensions(filepath)
    else:
        try:
            with Image.open(filepath) as img_file:
                src_w, src_h = img_file.size
        except Exception:
            src_w, src_h = 1024, 768

    params = scene.get("layout_params", {"scale": 1.0, "x": 0.0, "y": 0.0})
    scale = params.get("scale", 1.0)
    lx = params.get("x", 0.0)
    ly = params.get("y", 0.0)

    pos_x, pos_y = norm_to_px(lx, ly)

    has_info_card = True if scene.get("info_card") else False
    if has_info_card and duration_ms < 5000:
        has_info_card = False

    # ── Multi-Layer Composition: track_bg (opt-in only, clean black #000000 default) ──
    bg_config = scene.get("background")
    if bg_config and isinstance(bg_config, dict) and bg_config.get("enabled", True) and bg_config.get("source") != "none":
        bg_cat = bg_config.get("category")
        bg_mood = bg_config.get("mood")
        if not bg_cat:
            query_str = (scene.get("media", {}).get("query", "") + " " + scene.get("narration", "")).lower()
            if any(w in query_str for w in ["mapa", "geopolitica", "fronteira", "territorio", "map", "topographic"]):
                bg_cat = asset_catalog.CATEGORY_TOPOGRAPHIC
            elif any(w in query_str for w in ["papel", "processo", "documento", "jornal", "dossie", "relatorio", "paper", "crumpled"]):
                bg_cat = asset_catalog.CATEGORY_PAPER
            elif any(w in query_str for w in ["antigo", "passado", "flashback", "historico", "luto", "vintage", "grain", "filme"]):
                bg_cat = asset_catalog.CATEGORY_FILM_GRAIN
            elif any(w in query_str for w in ["batalha", "combate", "guerra", "violencia", "destruicao", "grunge", "distort"]):
                bg_cat = asset_catalog.CATEGORY_GRUNGE
            elif any(w in query_str for w in ["tecnologia", "digital", "rede", "cyber", "dados", "tech", "futuristic"]):
                bg_cat = asset_catalog.CATEGORY_PARTICLES_TECH
            elif any(w in query_str for w in ["clean", "white", "claro", "corporativo", "editorial"]):
                bg_cat = asset_catalog.CATEGORY_BRIGHT_WHITE
            else:
                bg_cat = asset_catalog.CATEGORY_DARK_MINIMAL

        bg_asset = asset_catalog.get_background(
            category=bg_cat,
            mood=bg_mood,
            fallback=True,
            deterministic_seed=f"{sid}_bg"
        )

        if bg_asset and bg_asset.exists():
            bg_media_id = add_media_fn(bg_asset.path)
            bg_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_bg"))
            bg_start_w = int(CANVAS_W * 1.02)
            bg_start_h = int(CANVAS_H * 1.02)
            bg_end_w = int(CANVAS_W * 1.06)
            bg_end_h = int(CANVAS_H * 1.06)

            bg_item = {
                "id": bg_item_id,
                "trackId": "track_bg",
                "from": start_f,
                "durationInFrames": dur_f,
                "label": f"bg_{sid}_{bg_asset.category}",
                "type": bg_asset.media_type,
                "mediaRef": bg_media_id,
                "sourceWidth": bg_asset.width,
                "sourceHeight": bg_asset.height,
                "transform": {
                    "x": 0,
                    "y": 0,
                    "width": bg_start_w,
                    "height": bg_start_h,
                    "opacity": 0.78,
                },
                "originId": bg_item_id,
            }

            if bg_asset.media_type == "video":
                bg_dur_s = bg_asset.duration_s if bg_asset.duration_s > 0 else (duration_ms / 1000.0)
                bg_dur_f = max(dur_f, int(round(bg_dur_s * FPS)))
                bg_end_f = min(dur_f, bg_dur_f)
                bg_item.update({
                    "volume": -60,
                    "sourceStart": 0,
                    "sourceEnd": bg_end_f,
                    "sourceDuration": bg_dur_f,
                    "sourceFps": FPS,
                })
            items.append(bg_item)

            all_keyframes.append({
                "itemId": bg_item_id,
                "animationVersion": 2,
                "properties": [
                    {"property": "width", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": bg_start_w, "easing": "ease-in-out"},
                        {"id": get_uid(), "frame": dur_f, "value": bg_end_w, "easing": "linear"},
                    ]},
                    {"property": "height", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": bg_start_h, "easing": "ease-in-out"},
                        {"id": get_uid(), "frame": dur_f, "value": bg_end_h, "easing": "linear"},
                    ]},
                ]
            })

    # ── Active Foreground Layer Support: track_fg_4 (non-overlapping with adjustments/cards) ──
    fg_config = scene.get("cutout") or scene.get("foreground")
    if fg_config and isinstance(fg_config, dict):
        fg_path = fg_config.get("path")
        if fg_path and os.path.exists(fg_path):
            fg_media_id = add_media_fn(fg_path)
            fg_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_fg_4"))
            fg_rot = editorial_engine.normalize_angle_deg(
                max(-3.0, min(3.0, float(fg_config.get("rotation", 0.0))))
            )
            fg_scale = float(fg_config.get("scale", 0.7))
            fg_w = int(CANVAS_W * fg_scale)
            fg_h = int(CANVAS_H * fg_scale)
            fg_x, fg_y = norm_to_px(float(fg_config.get("x", 0.15)), float(fg_config.get("y", 0.0)))
            items.append({
                "id": fg_item_id,
                "trackId": "track_fg_4",
                "from": start_f,
                "durationInFrames": dur_f,
                "label": f"{sid}_fg_cutout",
                "type": "image",
                "mediaRef": fg_media_id,
                "transform": {
                    "x": fg_x,
                    "y": fg_y,
                    "width": fg_w,
                    "height": fg_h,
                    "rotation": fg_rot,
                },
                "originId": fg_item_id,
            })

    if layout_style in ["full_screen", "text_only"] and not is_lottie:
        rng = random.Random(sid)
        base_w = CANVAS_W
        base_h = CANVAS_H

        # Smooth editorial camera push/pull on full_screen scenes
        apply_zoom = (not has_info_card and layout_style != "text_only")
        kb_bezier = {"type": "cubic-bezier", "bezier": {"x1": 0.25, "y1": 0.1, "x2": 0.25, "y2": 1.0}}

        if apply_zoom:
            c_motion = str(scene.get("camera_motion") or "").lower().strip()
            rng_kb = random.Random(f"{sid}_kb_motion")

            if c_motion in ["zoom_out_center", "slow_pull_out", "pull_out"]:
                motion_type, pan_dir = "zoom_out", "center"
            elif c_motion in ["zoom_in_center", "slow_push_in", "push_in"]:
                motion_type, pan_dir = "zoom_in", "center"
            elif c_motion in ["pan_left", "pan_right_left"]:
                motion_type, pan_dir = "pan", "left"
            elif c_motion in ["pan_right", "pan_left_right"]:
                motion_type, pan_dir = "pan", "right"
            elif c_motion in ["tilt_up", "pan_bottom_top"]:
                motion_type, pan_dir = "pan", "top"
            elif c_motion in ["tilt_down", "pan_top_bottom"]:
                motion_type, pan_dir = "pan", "bottom"
            elif c_motion in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                motion_type, pan_dir = "zoom_in", c_motion
            else:
                motion_type = rng_kb.choices(
                    ["zoom_in", "zoom_out", "pan", "diagonal"],
                    weights=[42, 33, 15, 10],
                    k=1,
                )[0]
                if motion_type == "zoom_in":
                    pan_dir = rng_kb.choice(["center", "top_left", "top_right", "bottom_left", "bottom_right"])
                elif motion_type == "zoom_out":
                    pan_dir = rng_kb.choice(["center", "top", "bottom", "left", "right"])
                elif motion_type == "pan":
                    pan_dir = rng_kb.choice(["left", "right", "top", "bottom"])
                else:
                    pan_dir = rng_kb.choice(["top_left", "top_right", "bottom_left", "bottom_right"])

            jitter_x = rng_kb.randint(-3, 3)
            jitter_y = rng_kb.randint(-2, 2)
            zoom_delta = round(rng_kb.uniform(0.03, 0.055) if is_video else rng_kb.uniform(0.055, 0.095), 3)
            base_safety_margin = 0.035 if is_video else 0.05

            if motion_type == "zoom_in":
                start_scale = 1.0 + base_safety_margin
                end_scale = 1.0 + base_safety_margin + zoom_delta
                start_w, start_h = int(base_w * start_scale), int(base_h * start_scale)
                end_w, end_h = int(base_w * end_scale), int(base_h * end_scale)
                max_x, max_y = (end_w - base_w) // 2, (end_h - base_h) // 2
                start_x, start_y = jitter_x, jitter_y
                dir_map = {
                    "center": (0, 0),
                    "top_left": (max_x, max_y),
                    "bottom_right": (-max_x, -max_y),
                    "top_right": (-max_x, max_y),
                    "bottom_left": (max_x, -max_y),
                    "left": (max_x, 0),
                    "right": (-max_x, 0),
                    "top": (0, max_y),
                    "bottom": (0, -max_y),
                }
                end_x, end_y = dir_map.get(pan_dir, (0, 0))
            elif motion_type == "zoom_out":
                start_scale = 1.0 + base_safety_margin + zoom_delta
                end_scale = 1.0 + base_safety_margin
                start_w, start_h = int(base_w * start_scale), int(base_h * start_scale)
                end_w, end_h = int(base_w * end_scale), int(base_h * end_scale)
                max_x, max_y = (start_w - base_w) // 2, (start_h - base_h) // 2
                end_x, end_y = jitter_x, jitter_y
                dir_map = {
                    "center": (0, 0),
                    "top_left": (max_x, max_y),
                    "bottom_right": (-max_x, -max_y),
                    "top_right": (-max_x, max_y),
                    "bottom_left": (max_x, -max_y),
                    "left": (max_x, 0),
                    "right": (-max_x, 0),
                    "top": (0, max_y),
                    "bottom": (0, -max_y),
                }
                start_x, start_y = dir_map.get(pan_dir, (0, 0))
            else:
                fixed_scale = 1.0 + base_safety_margin + (zoom_delta / 2.0)
                start_w = end_w = int(base_w * fixed_scale)
                start_h = end_h = int(base_h * fixed_scale)
                max_x, max_y = (start_w - base_w) // 2, (start_h - base_h) // 2
                if pan_dir in ["left", "top_left", "bottom_left"]:
                    start_x, end_x = -max_x + jitter_x, max_x
                elif pan_dir in ["right", "top_right", "bottom_right"]:
                    start_x, end_x = max_x + jitter_x, -max_x
                else:
                    start_x, end_x = jitter_x, -jitter_x
                if pan_dir in ["top", "top_left", "top_right"]:
                    start_y, end_y = -max_y + jitter_y, max_y
                elif pan_dir in ["bottom", "bottom_left", "bottom_right"]:
                    start_y, end_y = max_y + jitter_y, -max_y
                else:
                    start_y, end_y = jitter_y, -jitter_y
        else:
            safety_scale = 1.01
            start_w = end_w = int(base_w * safety_scale)
            start_h = end_h = int(base_h * safety_scale)
            start_x = end_x = start_y = end_y = 0

        full_screen_item = {
            "id": item_id,
            "trackId": "track_anchor",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_fullscreen",
            "type": "video" if is_video else "image",
            "mediaRef": media_id,
            "sourceWidth": src_w,
            "sourceHeight": src_h,
            "transform": {
                "x": start_x,
                "y": start_y,
                "width": start_w,
                "height": start_h,
            },
            "originId": item_id,
        }
        if layout_style == "full_screen" and not has_info_card:
            fs_mods = editorial_engine.build_fullscreen_motion_modifiers(sid, rng)
            if fs_mods:
                full_screen_item["motionModifiers"] = fs_mods

        if is_video:
            video_duration = meta["duration"] if "meta" in locals() else duration_ms / 1000.0
            source_dur = video_duration if video_duration > 0.0 else duration_ms / 1000.0
            source_dur_f = max(dur_f, int(round(source_dur * float(FPS))))
            handle_f = min(14, max(0, (source_dur_f - dur_f) // 2))
            source_start_f = handle_f
            source_end_f = min(source_dur_f, source_start_f + dur_f)
            full_screen_item.update({
                "volume": -60,
                "sourceStart": source_start_f,
                "sourceEnd": source_end_f,
                "sourceDuration": source_dur_f,
                "sourceFps": FPS,
            })
        items.append(full_screen_item)

        if apply_zoom:
            all_keyframes.append({
                "itemId": item_id,
                "animationVersion": 2,
                "properties": [
                    {"property": "width", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": start_w, "easing": "cubic-bezier", "easingConfig": kb_bezier},
                        {"id": get_uid(), "frame": dur_f, "value": end_w, "easing": "linear"},
                    ]},
                    {"property": "height", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": start_h, "easing": "cubic-bezier", "easingConfig": kb_bezier},
                        {"id": get_uid(), "frame": dur_f, "value": end_h, "easing": "linear"},
                    ]},
                    {"property": "x", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": start_x, "easing": "cubic-bezier", "easingConfig": kb_bezier},
                        {"id": get_uid(), "frame": dur_f, "value": end_x, "easing": "linear"},
                    ]},
                    {"property": "y", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": start_y, "easing": "cubic-bezier", "easingConfig": kb_bezier},
                        {"id": get_uid(), "frame": dur_f, "value": end_y, "easing": "linear"},
                    ]},
                ]
            })

        # Handcrafted editorial accent rule on text_only title cards
        if layout_style == "text_only":
            rule_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_editorial_rule"))
            items.append({
                "id": rule_id,
                "trackId": "track_fg_3",
                "from": start_f,
                "durationInFrames": dur_f,
                "label": f"{sid}_editorial_rule",
                "type": "shape",
                "shapeType": "rectangle",
                "fillColor": accent_hex,
                "fillEnabled": True,
                "fillType": "solid",
                "strokeEnabled": False,
                "fadeIn": 0.22,
                "fadeOut": 0.18,
                "transform": {
                    "x": 0,
                    "y": 132,
                    "width": 116,
                    "height": 4,
                    "cornerRadius": 2,
                    "opacity": 0.92,
                },
                "originId": rule_id,
            })

        # Causal SFX for kinetic transitions only (frame units + dB gain)
        if start_f > 0 and scene.get("transition") in ["slide", "lensWarpZoom", "wipe", "flip", "filmGateSlip"]:
            sfx_config = scene.get("sfx")
            allow_sfx = not (isinstance(sfx_config, dict) and sfx_config.get("enabled") is False)
            if allow_sfx:
                rng_sfx = random.Random(f"{sid}_trans_sfx")
                if rng_sfx.random() < 0.35 or (isinstance(sfx_config, dict) and sfx_config.get("enabled")):
                    sfx_asset = asset_catalog.get_sfx(kind="whoosh", fallback=True, deterministic_seed=f"{sid}_sfx")
                    if sfx_asset and sfx_asset.exists():
                        sfx_media_id = add_media_fn(sfx_asset.path)
                        sfx_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sfx"))
                        rng_vol = random.Random(f"{sid}_vol")
                        jitter_db = rng_vol.uniform(-1.5, 1.5)
                        base_db = getattr(sfx_asset, "default_gain_db", -24.0)
                        final_sfx_db = round(base_db + jitter_db, 1)
                        sfx_dur_f = max(2, int(sfx_asset.duration_frames_30fps))
                        clip_dur_f = min(18, sfx_dur_f, dur_f)
                        items.append({
                            "id": sfx_item_id,
                            "trackId": "track_sfx",
                            "from": start_f,
                            "durationInFrames": clip_dur_f,
                            "label": sfx_asset.filename,
                            "type": "audio",
                            "mediaRef": sfx_media_id,
                            "sourceStart": 0,
                            "sourceEnd": clip_dur_f,
                            "sourceDuration": sfx_dur_f,
                            "sourceFps": FPS,
                            "volume": final_sfx_db,
                            "audioFadeOut": 0.12,
                            "originId": sfx_item_id,
                        })
    else:  # single_card, split_info_slide, or is_lottie
        card_h = int(1024 * scale)
        card_w = int(card_h * (src_w / src_h)) if src_h > 0 else int(1024 * scale)
        max_card_w = 900 if layout_style == "split_info_slide" else 1400
        if card_w > max_card_w:
            card_w = max_card_w
            card_h = int(card_w * (src_h / src_w)) if src_w > 0 else card_h

        rng = random.Random(sid)
        base_x = pos_x
        base_y = pos_y
        base_w = card_w
        base_h = card_h

        apply_zoom = (not has_info_card and not is_lottie and rng.random() < 0.55)
        zoom_pct = round(rng.uniform(0.035, 0.065), 3)
        zoom_in = rng.choice([True, False])

        if apply_zoom:
            if zoom_in:
                start_w, end_w = base_w, int(base_w * (1.0 + zoom_pct))
                start_h, end_h = base_h, int(base_h * (1.0 + zoom_pct))
            else:
                start_w, end_w = int(base_w * (1.0 + zoom_pct)), base_w
                start_h, end_h = int(base_h * (1.0 + zoom_pct)), base_h
            start_x, end_x = base_x, base_x
            start_y, end_y = base_y, base_y
        else:
            start_w, end_w = base_w, base_w
            start_h, end_h = base_h, base_h
            start_x, end_x = base_x, base_x
            start_y, end_y = base_y, base_y

        sfx_config = scene.get("sfx")
        if isinstance(sfx_config, dict) and sfx_config.get("enabled"):
            apply_entrance = True
        else:
            apply_entrance = rng.random() < 0.68
        entrance_dir = rng.choice(["left", "right", "top", "bottom"])
        intro_dur = 15  # 0.50s tactile card entrance at 30 FPS
        if intro_dur >= dur_f - 2:
            apply_entrance = False

        init_x = start_x
        init_y = start_y

        if apply_entrance:
            # FreeCut canvas coordinates: X in [-960, +960], Y in [-540 (top), +540 (bottom)]
            if entrance_dir == "left":
                init_x = -960 - (start_w // 2) - 60
            elif entrance_dir == "right":
                init_x = 960 + (start_w // 2) + 60
            elif entrance_dir == "top":
                init_y = -540 - (start_h // 2) - 60
            elif entrance_dir == "bottom":
                init_y = 540 + (start_h // 2) + 60

        card_rotation = 0.0
        if "rotation" in scene:
            try:
                card_rotation = max(-3.0, min(3.0, float(scene["rotation"])))
            except (ValueError, TypeError):
                card_rotation = 0.0
        elif not is_lottie:
            rng_rot = random.Random(sid + "_rot")
            sign = rng_rot.choice([-1, 1])
            card_rotation = round(sign * rng_rot.uniform(0.8, 2.5), 1)
            card_rotation = max(-3.0, min(3.0, card_rotation))

        raw_card_rotation = round(float(card_rotation), 2)
        card_rotation = editorial_engine.normalize_angle_deg(raw_card_rotation)
        rng_mot = random.Random(sid + "_motion")
        card_motion_mods = editorial_engine.build_card_motion_modifiers(sid, rng_mot)

        card_item = {
            "id": item_id,
            "trackId": "track_anchor",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_lottie" if is_lottie else f"{sid}_card",
            "type": "lottie" if is_lottie else ("video" if is_video else "image"),
            "mediaRef": media_id,
            "sourceWidth": src_w,
            "sourceHeight": src_h,
            "transform": {
                "x": init_x,
                "y": init_y,
                "width": start_w,
                "height": start_h,
                "rotation": card_rotation,
                "cornerRadius": 28 if is_video else 0,
            },
            "motionModifiers": card_motion_mods,
            "originId": item_id,
        }
        if is_video:
            video_duration = meta["duration"] if "meta" in locals() else duration_ms / 1000.0
            source_dur = video_duration if video_duration > 0.0 else duration_ms / 1000.0
            source_dur_f = max(dur_f, int(round(source_dur * float(FPS))))
            source_end_f = min(dur_f, source_dur_f)
            card_item.update({
                "volume": -60,
                "sourceStart": 0,
                "sourceEnd": source_end_f,
                "sourceDuration": source_dur_f,
                "sourceFps": FPS,
            })
        items.append(card_item)

        # Subtle center-gutter editorial accent bar on horizontal split_info_slide scenes
        if layout_style == "split_info_slide" and params.get("split_type", "horizontal") == "horizontal":
            div_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_split_divider"))
            items.append({
                "id": div_id,
                "trackId": "track_fg_3",
                "from": start_f,
                "durationInFrames": dur_f,
                "label": f"{sid}_split_divider",
                "type": "shape",
                "shapeType": "rectangle",
                "fillColor": accent_hex,
                "fillEnabled": True,
                "fillType": "solid",
                "strokeEnabled": False,
                "fadeIn": 0.25,
                "fadeOut": 0.20,
                "transform": {
                    "x": 0,
                    "y": 0,
                    "width": 3,
                    "height": 260,
                    "cornerRadius": 2,
                    "opacity": 0.42,
                },
                "originId": div_id,
            })

        # Causal SFX tied strictly to physical slide entrance of card (frame units + dB)
        if apply_entrance and start_f > 0:
            sfx_config = scene.get("sfx")
            allow_sfx = not (isinstance(sfx_config, dict) and sfx_config.get("enabled") is False)
            if allow_sfx:
                sfx_asset = asset_catalog.get_sfx(kind="whoosh", fallback=True, deterministic_seed=f"{sid}_sfx")
                if sfx_asset and sfx_asset.exists():
                    sfx_media_id = add_media_fn(sfx_asset.path)
                    sfx_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sfx"))
                    rng_vol = random.Random(f"{sid}_vol")
                    jitter_db = rng_vol.uniform(-1.5, 1.5)
                    base_db = getattr(sfx_asset, "default_gain_db", -24.0)
                    final_sfx_db = round(base_db + jitter_db, 1)
                    if isinstance(sfx_config, dict) and "volume" in sfx_config:
                        try:
                            raw_v = float(sfx_config["volume"])
                            if raw_v < 0:
                                final_sfx_db = max(-45.0, min(-12.0, raw_v))
                        except (ValueError, TypeError):
                            pass
                    sfx_dur_f = max(2, int(sfx_asset.duration_frames_30fps))
                    clip_dur_f = min(intro_dur + 3, sfx_dur_f, dur_f)
                    items.append({
                        "id": sfx_item_id,
                        "trackId": "track_sfx",
                        "from": start_f,
                        "durationInFrames": clip_dur_f,
                        "label": sfx_asset.filename,
                        "type": "audio",
                        "mediaRef": sfx_media_id,
                        "sourceStart": 0,
                        "sourceEnd": clip_dur_f,
                        "sourceDuration": sfx_dur_f,
                        "sourceFps": FPS,
                        "volume": final_sfx_db,
                        "audioFadeOut": 0.12,
                        "originId": sfx_item_id,
                    })

        # Tactile spring / expo-out keyframes (Schema v15 animationVersion: 2, zero linear sine spam)
        drift_bezier = {"type": "cubic-bezier", "bezier": {"x1": 0.25, "y1": 0.1, "x2": 0.25, "y2": 1.0}}
        use_spring = rng.random() < 0.55
        if use_spring:
            entrance_easing = "spring"
            entrance_cfg = {
                "type": "spring",
                "spring": {
                    "tension": rng.randint(175, 215),
                    "friction": rng.randint(20, 25),
                    "mass": 1.0,
                },
            }
        else:
            entrance_easing = "cubic-bezier"
            entrance_cfg = {
                "type": "cubic-bezier",
                "bezier": {"x1": 0.16, "y1": 1.0, "x2": 0.3, "y2": 1.0},
            }

        kf_props = []
        if start_w != end_w or start_h != end_h:
            kf_props.append({
                "property": "width",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_w, "easing": "cubic-bezier", "easingConfig": drift_bezier},
                    {"id": get_uid(), "frame": dur_f, "value": end_w, "easing": "linear"},
                ],
            })
            kf_props.append({
                "property": "height",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_h, "easing": "cubic-bezier", "easingConfig": drift_bezier},
                    {"id": get_uid(), "frame": dur_f, "value": end_h, "easing": "linear"},
                ],
            })

        if apply_entrance:
            kf_props.append({
                "property": "x",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": init_x, "easing": entrance_easing, "easingConfig": entrance_cfg},
                    {"id": get_uid(), "frame": intro_dur, "value": start_x, "easing": "linear"},
                    {"id": get_uid(), "frame": dur_f, "value": end_x, "easing": "linear"},
                ],
            })
            kf_props.append({
                "property": "y",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": init_y, "easing": entrance_easing, "easingConfig": entrance_cfg},
                    {"id": get_uid(), "frame": intro_dur, "value": start_y, "easing": "linear"},
                    {"id": get_uid(), "frame": dur_f, "value": end_y, "easing": "linear"},
                ],
            })
            settled_rot = card_rotation
            intro_rot = round(
                settled_rot + (2.2 if entrance_dir in ["left", "top"] else -2.2),
                2,
            )
            kf_props.append({
                "property": "rotation",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": intro_rot, "easing": entrance_easing, "easingConfig": entrance_cfg},
                    {"id": get_uid(), "frame": intro_dur, "value": settled_rot, "easing": "linear"},
                ],
            })
        elif start_x != end_x or start_y != end_y:
            kf_props.append({
                "property": "x",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_x, "easing": "cubic-bezier", "easingConfig": drift_bezier},
                    {"id": get_uid(), "frame": dur_f, "value": end_x, "easing": "linear"},
                ],
            })
            kf_props.append({
                "property": "y",
                "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_y, "easing": "cubic-bezier", "easingConfig": drift_bezier},
                    {"id": get_uid(), "frame": dur_f, "value": end_y, "easing": "linear"},
                ],
            })

        if kf_props:
            all_keyframes.append({
                "itemId": item_id,
                "animationVersion": 2,
                "properties": kf_props,
            })


def _build_scene_adjustments(project_id, scenes, items, palette=None, explicit_style="", variation_seed=""):
    if not scenes:
        return

    import random as prng
    rng = prng.Random(f"{project_id}_{variation_seed}_adjustments")
    palette_eff = palette or editorial_engine.EDITORIAL_FONT_PALETTES["editorial_documentary"]

    eligible_indices = [i for i, s in enumerate(scenes) if s.get("layout_style") != "text_only"]
    if not eligible_indices:
        return

    num_eligible = len(eligible_indices)
    pct = rng.uniform(0.30, 0.48)
    num_effects = max(1, min(num_eligible, int(round(num_eligible * pct))))
    effect_indices = sorted(rng.sample(eligible_indices, num_effects))
    print(f"  [Color Grading] Aplicando WebGPU film grade + micro-textura em {num_effects} de {num_eligible} cenas")

    explicit_norm = (explicit_style or "").strip().lower()

    for idx in effect_indices:
        scene = scenes[idx]
        sid = scene["id"]
        start_f = ms_to_frames(scene["start_ms"])
        dur_f = max(2, ms_to_frames(scene["end_ms"] - scene["start_ms"]))
        rng_scene = prng.Random(f"{sid}_{variation_seed}_effects_calib")
        effects_list = []

        if explicit_norm in ("vhs_leak", "cinematic_retro", "noir_bw"):
            style_label = explicit_norm.upper().replace("_", " ")
            if explicit_norm == "noir_bw":
                effects_list.append({
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grayscale")),
                    "effect": {"type": "gpu-effect", "gpuEffectType": "gpu-grayscale", "params": {"amount": 1.0}},
                    "enabled": True,
                })
                effects_list.append({
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_contrast")),
                    "effect": {"type": "gpu-effect", "gpuEffectType": "gpu-contrast", "params": {"amount": round(rng_scene.uniform(1.12, 1.24), 2)}},
                    "enabled": True,
                })
            else:
                effects_list.append({
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                    "effect": {"type": "gpu-effect", "gpuEffectType": "gpu-grain", "params": {"amount": round(rng_scene.uniform(0.025, 0.045), 3), "size": 0.9, "speed": 1}},
                    "enabled": True,
                })
        else:
            style_label, effects_list = editorial_engine.build_editorial_grade_effects(
                sid=sid,
                palette=palette_eff,
                layout_style=scene.get("layout_style") or "full_screen",
                rng=rng_scene,
            )

        adjustment_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_adjustment"))
        items.append({
            "id": adjustment_id,
            "type": "adjustment",
            "trackId": "track_fg_1",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": style_label,
            "effects": effects_list,
            "effectOpacity": 1,
            "originId": adjustment_id,
        })


def build_freecut_bundle(project_dir):
    print(f"  Iniciando compilação do FreeCut bundle para: {project_dir}")
    storyboard_file = os.path.join(project_dir, "storyboard.json")
    if not os.path.exists(storyboard_file):
        print(f"  Erro: storyboard.json não encontrado em: {project_dir}")
        return False

    ensure_storyboard_rebuilt(project_dir)

    with open(storyboard_file, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    words_file = os.path.join(project_dir, "words.json")
    words = load_words_normalized(words_file)

    render_hyperframes_subtitles(project_dir, storyboard, words)

    scenes = storyboard.get("scenes", [])
    total_dur_ms = storyboard.get("total_duration_ms", 0)
    if not total_dur_ms and scenes:
        total_dur_ms = max(s.get("end_ms", 0) for s in scenes)
    title = storyboard.get("title", "freecut-project")

    audio_file = find_narration_audio(project_dir)
    if not audio_file:
        print(f"  Erro: Nenhum arquivo de áudio ({', '.join(SUPPORTED_AUDIO_EXTS)}) encontrado na raiz do projeto")
        return False
    raw_audio_dur = get_audio_duration_ms(audio_file) or total_dur_ms
    audio_dur_ms = min(raw_audio_dur, total_dur_ms) if total_dur_ms > 0 else raw_audio_dur

    safe_title = "".join(c if c.isalnum() or c in "_- " else "" for c in title).replace(" ", "_")[:40] or "freecut_project"
    project_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, safe_title))

    proj_seed = _project_editorial_seed(project_dir, storyboard)
    variation_seed = str(storyboard.get("variation_seed") or "")
    sample_narration = " ".join(s.get("narration", "") for s in scenes[:12])
    palette_key, palette = editorial_engine.select_project_typography_palette(
        project_seed=proj_seed,
        title=title,
        mode=storyboard.get("mode", "default"),
        universe=storyboard.get("universe", ""),
        sample_text=sample_narration,
        explicit_theme=storyboard.get("font_theme", ""),
    )
    chosen_font = palette["body_font"]
    explicit_style = str(storyboard.get("global_style", "") or "")
    print(f"  [Typography] Paleta editorial selecionada: {palette['name']} ({palette_key} -> body='{palette['body_font']}', display='{palette['display_font']}')")

    items = []
    all_keyframes = []
    manifest_media = []
    media_files_to_zip = []
    seen_media_ids = set()
    media_id_to_filepath = {}

    def add_media(filepath, override_duration_s=None):
        sha256 = compute_sha256(filepath)
        media_id = str(uuid.uuid5(uuid.NAMESPACE_OID, sha256))
        media_id_to_filepath[media_id] = filepath
        if media_id in seen_media_ids:
            return media_id
        seen_media_ids.add(media_id)
        safe_fname = editorial_engine.sanitize_workspace_filename(os.path.basename(filepath))
        rel_path = f"media/{safe_fname}"
        mime = detect_mime(filepath)

        w, h = CANVAS_W, CANVAS_H
        duration = 0.0
        codec = "unknown"
        fps = FPS

        if mime.startswith("video/"):
            meta = get_video_metadata(filepath)
            w = meta["width"]
            h = meta["height"]
            duration = meta["duration"]
            codec = meta["codec"]
            fps = meta["fps"]
        elif mime.startswith("audio/"):
            w = 0
            h = 0
            if override_duration_s is not None and override_duration_s > 0:
                duration = float(override_duration_s)
            else:
                dur_ms = get_audio_duration_ms(filepath)
                duration = (dur_ms / 1000.0) if dur_ms else 1.0
            ext_a = os.path.splitext(filepath)[1].lower()
            codec = {
                ".mp3": "mp3",
                ".wav": "pcm",
                ".m4a": "aac",
                ".aac": "aac",
                ".ogg": "opus",
                ".opus": "opus",
                ".flac": "flac",
            }.get(ext_a, "pcm")
            fps = FPS
        else:
            try:
                with Image.open(filepath) as img:
                    w, h = img.size
            except Exception:
                pass

        manifest_media.append({
            "originalId": media_id,
            "relativePath": rel_path,
            "fileName": safe_fname,
            "fileSize": os.path.getsize(filepath),
            "sha256": sha256,
            "mimeType": mime,
            "metadata": {
                "duration": duration,
                "width": w,
                "height": h,
                "fps": fps,
                "codec": codec,
                "bitrate": 0,
            },
        })
        media_files_to_zip.append((filepath, rel_path))
        return media_id

    # 1. Register narration audio via add_media and append Schema v15 frame-unit audio item
    audio_media_id = add_media(audio_file, override_duration_s=audio_dur_ms / 1000.0)
    audio_dur_f = max(2, ms_to_frames(audio_dur_ms))
    audio_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_id}_audio"))
    items.append({
        "id": audio_item_id,
        "trackId": "track_audio",
        "from": 0,
        "durationInFrames": audio_dur_f,
        "label": editorial_engine.sanitize_workspace_filename(os.path.basename(audio_file)),
        "type": "audio",
        "mediaRef": audio_media_id,
        "sourceStart": 0,
        "sourceEnd": audio_dur_f,
        "sourceDuration": audio_dur_f,
        "sourceFps": FPS,
        "volume": 0,
        "originId": audio_item_id,
    })

    # 2. Add scene items and subtitles using cohesive typography palette
    scene_by_anchor_id = {}
    for scene in scenes:
        sid = scene["id"]
        scene_by_anchor_id[str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_anchor"))] = scene
        _build_scene_items(
            project_dir,
            scene,
            items,
            all_keyframes,
            add_media,
            global_style=explicit_style or "editorial_film",
            palette=palette,
        )
        _build_subtitles(
            project_dir,
            scene,
            items,
            all_keyframes,
            add_media,
            font_family=chosen_font,
            palette=palette,
        )

    # 2.1 Add PT-BR guide subtitles if available
    has_ptbr = _build_ptbr_subtitles(project_dir, scenes, items, all_keyframes, font_family=chosen_font)

    # 3. Add tasteful manual-feel transitions between consecutive full_screen / text_only clips on track_anchor
    transitions_list = []
    anchor_items = [
        item for item in items
        if item.get("trackId") == "track_anchor" and item.get("type") in ["video", "image", "lottie"]
    ]
    anchor_items.sort(key=lambda x: x["from"])

    import random as prng
    rng = prng.Random(f"{project_id}:{variation_seed}")
    prev_trans_preset = None

    for i in range(len(anchor_items) - 1):
        left_item = anchor_items[i]
        right_item = anchor_items[i + 1]

        # Ensure clips are strictly adjacent before attaching a crossfade transition
        if left_item["from"] + left_item["durationInFrames"] != right_item["from"]:
            continue

        left_label = left_item.get("label", "").lower()
        right_label = right_item.get("label", "").lower()
        is_card = "card" in left_label or "card" in right_label or "lottie" in left_label or "lottie" in right_label
        if is_card:
            prev_trans_preset = None
            continue

        right_scene = scene_by_anchor_id.get(right_item["id"], {})
        scene_hint = str(right_scene.get("transition") or "")
        choice = editorial_engine.select_editorial_transition(
            left_label=left_label,
            right_label=right_label,
            scene_hint=scene_hint,
            prev_preset=prev_trans_preset,
            rng=rng,
        )
        if not choice:
            prev_trans_preset = None
            continue

        preset, desired_dur_f, direction = choice
        max_by_clip = min(left_item["durationInFrames"], right_item["durationInFrames"]) // 2 - 1
        max_allowed = max_by_clip

        # Respect video source handles so FreeCut never drops handle-starved video transitions
        if left_item.get("type") == "video":
            left_tail = max(0, int(left_item.get("sourceDuration", 0)) - int(left_item.get("sourceEnd", 0)))
            max_allowed = min(max_allowed, left_tail * 2)
        if right_item.get("type") == "video":
            right_head = max(0, int(right_item.get("sourceStart", 0)))
            max_allowed = min(max_allowed, right_head * 2)

        if max_allowed < 6:
            prev_trans_preset = None
            continue

        duration_frames = max(6, min(desired_dur_f, max_allowed))
        prev_trans_preset = preset

        trans = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_id}_trans_{i}")),
            "leftClipId": left_item["id"],
            "rightClipId": right_item["id"],
            "trackId": "track_anchor",
            "type": "crossfade",
            "durationInFrames": duration_frames,
            "presentation": preset,
            "timing": "cubic-bezier" if preset in ("slide", "wipe", "filmGateSlip", "smoothCut") else "linear",
            "alignment": 0.5,
        }
        if trans["timing"] == "cubic-bezier":
            trans["bezierPoints"] = {"x1": 0.25, "y1": 0.1, "x2": 0.25, "y2": 1.0}
        if direction:
            trans["direction"] = direction

        transitions_list.append(trans)

    # 4. Add native WebGPU color grading + micro-grain adjustment layers
    _build_scene_adjustments(
        project_id,
        scenes,
        items,
        palette=palette,
        explicit_style=explicit_style,
        variation_seed=variation_seed,
    )

    # 5. Prune unused empty foreground/background tracks so the timeline opens fast and clutter-free
    raw_tracks = (
        [
            {
                "id": "track_sub_ptbr",
                "name": "Legenda PT-BR (Guia de Sincronia)",
                "kind": "video",
                "height": 100,
                "locked": False,
                "visible": True,
                "muted": False,
                "solo": False,
                "order": 0,
                "syncLock": True,
                "volume": 0,
            },
            {
                "id": "track_text",
                "name": "Legenda Original",
                "kind": "video",
                "height": 100,
                "locked": False,
                "visible": True,
                "muted": False,
                "solo": False,
                "order": 1,
                "syncLock": True,
                "volume": 0,
            },
        ]
        + [{**tr, "order": tr["order"] + 1} for tr in TRACKS[1:]]
    ) if has_ptbr else [dict(tr) for tr in TRACKS]

    used_track_ids = {it.get("trackId") for it in items}
    core_keep_ids = {"track_text", "track_anchor", "track_sfx", "track_audio"}
    if has_ptbr:
        core_keep_ids.add("track_sub_ptbr")

    pruned_tracks = []
    for tr in raw_tracks:
        tid = tr["id"]
        if tid in core_keep_ids or tid in used_track_ids:
            tr_copy = dict(tr)
            tr_copy["order"] = len(pruned_tracks)
            pruned_tracks.append(tr_copy)

    now_ms = int(time.time() * 1000)
    output_zip = os.path.join(project_dir, f"{safe_title}.freecut.zip")

    # Generate cover thumbnail bytes from first visual media asset
    first_visual_path = None
    first_visual_mime = ""
    for entry in manifest_media:
        m_mime = entry.get("mimeType", "")
        if m_mime.startswith(("image/", "video/")):
            cand_path = media_id_to_filepath.get(entry["originalId"])
            if cand_path and os.path.isfile(cand_path) and not cand_path.endswith("_bg.png"):
                first_visual_path = cand_path
                first_visual_mime = m_mime
                break
    cover_bytes = editorial_engine.generate_project_cover_bytes(first_visual_path, first_visual_mime)

    project_json = {
        "id": project_id,
        "name": safe_title,
        "description": f"Generated by FreeCut v3 Editorial Pipeline ({palette['name']})",
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "duration": round(audio_dur_ms / 1000.0, 3),
        "metadata": {
            "width": CANVAS_W,
            "height": CANVAS_H,
            "fps": FPS,
            "backgroundColor": "#000000",
        },
        "timeline": {
            "tracks": pruned_tracks,
            "items": items,
            "transitions": transitions_list,
            "keyframes": all_keyframes,
            "masterBusDb": 0,
            "currentFrame": 0,
            "zoomLevel": 1,
            "scrollPosition": 0,
        },
        "schemaVersion": 15,
    }

    manifest = {
        "version": "1.0",
        "createdAt": now_ms,
        "editorVersion": "1.0.0",
        "projectId": project_id,
        "projectName": safe_title,
        "media": manifest_media,
        "checksum": "",
    }
    if cover_bytes:
        manifest["thumbnail"] = "cover.jpg"

    manifest["checksum"] = hashlib.sha256(
        json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(project_json, indent=2, ensure_ascii=False))
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        if cover_bytes:
            zf.writestr("cover.jpg", cover_bytes)
        for src_path, zip_rel in media_files_to_zip:
            zf.write(src_path, zip_rel)

    print(f"  [SUCCESS] Bundle compilado com sucesso em: {output_zip}")

    # 6. Compile instant-load Workspace v2 folder (with pre-warmed filmstrips, waveforms & thumbnails)
    workspace_dir = os.path.join(project_dir, "freecut_workspace")
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir, ignore_errors=True)

    projects_dir = os.path.join(workspace_dir, "projects", project_id)
    os.makedirs(projects_dir, exist_ok=True)

    with open(os.path.join(workspace_dir, ".freecut-workspace.json"), "w", encoding="utf-8") as f:
        json.dump({"schemaVersion": "2.0", "createdAt": now_ms}, f, ensure_ascii=False, indent=2)

    index = {
        "version": "1.0",
        "updatedAt": now_ms,
        "projects": [{"id": project_id, "name": safe_title, "updatedAt": now_ms}],
    }
    with open(os.path.join(workspace_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # Copy media files into workspace/media/{id}/{fileName} first so caches can also inspect them
    for entry in manifest_media:
        media_id = entry["originalId"]
        media_dir_path = os.path.join(workspace_dir, "media", media_id)
        os.makedirs(media_dir_path, exist_ok=True)
        src_file = media_id_to_filepath.get(media_id)
        dest_file = os.path.join(media_dir_path, entry["fileName"])
        if src_file and os.path.isfile(src_file):
            shutil.copy2(src_file, dest_file)
        else:
            for local_path, zip_rel in media_files_to_zip:
                if os.path.basename(zip_rel) == entry["fileName"]:
                    shutil.copy2(local_path, dest_file)
                    media_id_to_filepath[media_id] = dest_file
                    break

    video_priority_ranges = {}
    for it in items:
        if it.get("type") == "video" and it.get("mediaRef"):
            m_ref = it["mediaRef"]
            sfps = float(it.get("sourceFps") or FPS)
            s_st = float(it.get("sourceStart") or 0.0) / sfps
            s_en = float(it.get("sourceEnd") or it.get("durationInFrames") or 30.0) / sfps
            video_priority_ranges.setdefault(m_ref, []).append((s_st, max(s_st + 0.1, s_en)))

    t0_cache = time.time()
    thumb_map = editorial_engine.prewarm_workspace_media_caches(
        workspace_dir=workspace_dir,
        manifest_media=manifest_media,
        media_id_to_filepath=media_id_to_filepath,
        video_priority_ranges=video_priority_ranges,
    )
    print(f"  [FastOpen Cache] Filmstrips v2 (buildTargetIndices), Waveforms (meta+bins+WFORM v1) e Thumbnails gerados em {time.time() - t0_cache:.2f}s")

    for entry in manifest_media:
        media_id = entry["originalId"]
        mime = entry["mimeType"]
        media_dir_path = os.path.join(workspace_dir, "media", media_id)
        src_file = media_id_to_filepath.get(media_id) or os.path.join(media_dir_path, entry["fileName"])
        mtime_ms = int(os.path.getmtime(src_file) * 1000) if os.path.isfile(src_file) else now_ms

        meta = {
            "id": media_id,
            "storageType": "workspace",
            "fileName": entry["fileName"],
            "fileSize": entry["fileSize"],
            "fileLastModified": mtime_ms,
            "mimeType": mime,
            "contentHash": entry["sha256"],
            "duration": entry["metadata"]["duration"],
            "width": entry["metadata"]["width"],
            "height": entry["metadata"]["height"],
            "fps": entry["metadata"]["fps"],
            "codec": entry["metadata"]["codec"],
            "bitrate": 0,
            "tags": [],
            "createdAt": now_ms,
            "updatedAt": now_ms,
        }
        if thumb_map.get(media_id):
            meta["thumbnailId"] = media_id
        if mime.startswith("video/"):
            # Omit audioCodec on silent B-roll videos so FreeCut skips waveform worker decode!
            meta["videoCodecSupported"] = True
        elif mime.startswith("audio/"):
            meta["audioCodecSupported"] = True

        with open(os.path.join(media_dir_path, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # Deep-copy project_json for workspace so .freecut.zip keeps mediaRef while workspace uses mediaId
    ws_project = copy.deepcopy(project_json)
    ws_items = []
    for item in ws_project["timeline"]["items"]:
        if "mediaRef" in item:
            item["mediaId"] = item.pop("mediaRef")
        ws_items.append(item)
    ws_project["timeline"]["items"] = ws_items

    if cover_bytes:
        with open(os.path.join(projects_dir, "thumbnail.jpg"), "wb") as tf:
            tf.write(cover_bytes)
        ws_project["thumbnailId"] = f"project:{project_id}:cover"

    with open(os.path.join(projects_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(ws_project, f, ensure_ascii=False, indent=2)

    media_links = {
        "version": "1.0",
        "mediaIds": [{"id": entry["originalId"], "addedAt": now_ms} for entry in manifest_media],
    }
    with open(os.path.join(projects_dir, "media-links.json"), "w", encoding="utf-8") as f:
        json.dump(media_links, f, ensure_ascii=False, indent=2)

    print(f"  [OK] Workspace v2 instant-load compilado com sucesso em: {workspace_dir}")
    return True


# ── Main Entry Point ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FreeCut v3 Video Automation Tool")
    sub = parser.add_subparsers(dest="command", required=True)

    rebuild_cmd = sub.add_parser("rebuild", help="Aplica os novos arquétipos e legendas fatiadas no storyboard.")
    rebuild_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    rebuild_cmd.add_argument("--variation", default=None, help="Semente opcional (ou 'random') para gerar nova variação editorial manual.")

    download_cmd = sub.add_parser("download", help="Faz download das mídias das APIs (Pexels/Pixabay) ou scrapers.")
    download_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")

    build_cmd = sub.add_parser("build", help="Processa imagens com Pillow e compila o bundle .freecut.zip")
    build_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    build_cmd.add_argument("--variation", default=None, help="Semente opcional (ou 'random') para gerar nova variação editorial manual.")

    run_cmd = sub.add_parser("run-project", help="Executa todo o pipeline de ponta a ponta.")
    run_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    run_cmd.add_argument("--variation", default=None, help="Semente opcional (ou 'random') para gerar nova variação editorial manual.")

    args = parser.parse_args()
    project_dir = os.path.abspath(args.project_dir)
    load_env(project_dir)

    if args.command == "rebuild":
        if not rebuild_storyboard(project_dir, variation=args.variation):
            sys.exit(1)
    elif args.command == "download":
        if not run_media_downloads(project_dir):
            sys.exit(1)
    elif args.command == "build":
        if not ensure_storyboard_rebuilt(project_dir, variation=args.variation):
            sys.exit(1)
        if not process_images_pipeline(project_dir):
            sys.exit(1)
        if not build_freecut_bundle(project_dir):
            sys.exit(1)
    elif args.command == "run-project":
        print(f"=== Iniciando Pipeline Completo (v3) em: {project_dir} ===")
        if not rebuild_storyboard(project_dir, variation=args.variation):
            sys.exit(1)
        if not run_media_downloads(project_dir):
            sys.exit(1)
        if not process_images_pipeline(project_dir):
            sys.exit(1)
        if not build_freecut_bundle(project_dir):
            sys.exit(1)
        print("=== Pipeline v3 Finalizado com Sucesso ===")


if __name__ == "__main__":
    main()
