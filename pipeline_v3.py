import os
import re
import sys
import json
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
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import asset_catalog


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
        "muted": False,
        "solo": False,
        "order": 9,
        "syncLock": True,
        "volume": 0
    },
    {
        "id": "track_sfx",
        "name": "Sound Effects",
        "kind": "audio",
        "height": 80,
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
def load_env(project_dir):
    """Loads variables from .env in the project directory, repo root, or cwd, and ensures FFmpeg is on PATH."""
    if not shutil.which("ffmpeg"):
        local_app = os.environ.get("LOCALAPPDATA", "")
        for pat in [
            os.path.join(local_app, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]:
            matches = glob.glob(pat, recursive=True)
            if matches:
                os.environ["PATH"] = os.path.dirname(matches[0]) + os.pathsep + os.environ.get("PATH", "")
                break

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

def detect_mime(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        '.mp4': 'video/mp4', '.mov': 'video/quicktime',
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
        '.json': 'application/json', '.lottie': 'application/octet-stream'
    }.get(ext, 'application/octet-stream')

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
            "-show_entries", "stream=width,height,avg_frame_rate,codec_name,duration:format=duration",
            "-of", "json",
            video_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        
        duration = 0.0
        width = CANVAS_W
        height = CANVAS_H
        codec = "unknown"
        fps = FPS
        
        if streams:
            s = streams[0]
            width = s.get("width", CANVAS_W)
            height = s.get("height", CANVAS_H)
            codec = s.get("codec_name", "unknown")
            duration = float(s.get("duration", 0.0))
            fr = s.get("avg_frame_rate", "30/1")
            if "/" in fr:
                num, den = fr.split("/")
                if float(den) > 0:
                    fps = int(round(float(num) / float(den)))
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

# ── Pillow Image Processor (Corners + Shadows) ─────────
def apply_card_styling(input_path, output_path, border_radius=48):
    """Applies rounded corners and a soft baked drop shadow to card images."""
    try:
        img = Image.open(input_path).convert("RGBA")
        orig_w, orig_h = img.size
        aspect = orig_w / float(orig_h) if orig_h > 0 else 1.0
        
        if aspect <= 1.0:
            target_h = 1024
            target_w = int(target_h * aspect)
        else:
            target_w = 1024
            target_h = int(target_w / aspect)
            
        target_w = max(100, (target_w // 2) * 2)
        target_h = max(100, (target_h // 2) * 2)
        
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Rounded corner mask
        mask = Image.new("L", (target_w, target_h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, target_w, target_h), radius=border_radius, fill=255)
        img.putalpha(mask)
        
        # Bake drop shadow
        pad = 80
        shadow_w = target_w + 2 * pad
        shadow_h = target_h + 2 * pad
        
        final_canvas = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
        shadow_mask = Image.new("L", (shadow_w, shadow_h), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        
        offset_x, offset_y = 0, 16
        shadow_draw.rounded_rectangle(
            (pad + offset_x, pad + offset_y, pad + target_w + offset_x, pad + target_h + offset_y),
            radius=border_radius,
            fill=110
        )
        shadow_blur = shadow_mask.filter(ImageFilter.GaussianBlur(24))
        
        final_canvas.paste((0, 0, 0, 255), (0, 0), mask=shadow_blur)
        final_canvas.paste(img, (pad, pad), mask=img)
        final_canvas.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"      [Pillow Error] Falha ao formatar card: {os.path.basename(input_path)}: {e}")
        return False

def apply_blur_background_styling(input_path, output_path):
    """Creates a 1920x1080 canvas. If the image is native 16:9, fits cleanly.
    If the image is vertical, square, 4:3 or ultrawide, places the ENTIRE image intact in center
    (never cropped), with a cinematic blurred and darkened background filling the 1920x1080 canvas.
    """
    try:
        img = Image.open(input_path).convert("RGBA")
        orig_w, orig_h = img.size
        aspect = orig_w / float(orig_h) if orig_h > 0 else 1.0

        # If already native 16:9 widescreen (within 3% of 1.777), fit directly
        if 1.72 <= aspect <= 1.84:
            final_img = ImageOps.fit(img, (CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
            final_img.convert("RGB").save(output_path, "PNG")
            return True

        # For ALL vertical, square, 4:3, and ultrawide images:
        # 1. Create blurred + darkened background filling 1920x1080
        scale_bg = max(CANVAS_W / float(orig_w), CANVAS_H / float(orig_h))
        bg_w = int(orig_w * scale_bg) + 4
        bg_h = int(orig_h * scale_bg) + 4
        bg_resized = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)

        left = (bg_w - CANVAS_W) // 2
        top = (bg_h - CANVAS_H) // 2
        bg_cropped = bg_resized.crop((left, top, left + CANVAS_W, top + CANVAS_H))

        # Cinematic blur + darkening
        bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(40))
        dark_overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 110))
        bg_composite = Image.alpha_composite(bg_blurred, dark_overlay)

        # 2. Scale foreground image so it is 100% INTACT (NEVER cropped!)
        # Safe bounds: max_h 980 (out of 1080), max_w 1760 (out of 1920)
        # Guarantees vertical images leave safe margins so Ken Burns camera zoom never cuts them off!
        max_fg_w = 1760
        max_fg_h = 980
        scale_fg = min(max_fg_w / float(orig_w), max_fg_h / float(orig_h))
        fg_w = int(orig_w * scale_fg)
        fg_h = int(orig_h * scale_fg)

        fg_resized = img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)

        # 3. Create soft drop shadow for depth
        pad = 40
        shadow_mask = Image.new("L", (fg_w + 2 * pad, fg_h + 2 * pad), 0)
        s_draw = ImageDraw.Draw(shadow_mask)
        s_draw.rectangle((pad, pad, pad + fg_w, pad + fg_h), fill=160)
        shadow_blur = shadow_mask.filter(ImageFilter.GaussianBlur(20))

        shadow_layer = Image.new("RGBA", (fg_w + 2 * pad, fg_h + 2 * pad), (0, 0, 0, 0))
        shadow_layer.paste((0, 0, 0, 255), (0, 0), mask=shadow_blur)

        # 4. Composite onto canvas
        canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 255))
        canvas.paste(bg_composite, (0, 0))

        paste_x = (CANVAS_W - fg_w) // 2
        paste_y = (CANVAS_H - fg_h) // 2

        # Paste shadow with slight vertical offset (+8px) for natural lighting
        canvas.paste(shadow_layer, (paste_x - pad, paste_y - pad + 8), mask=shadow_layer)

        # Add subtle 1px clean border to foreground image for crisp distinction
        fg_canvas = fg_resized.copy()
        fg_draw = ImageDraw.Draw(fg_canvas)
        fg_draw.rectangle((0, 0, fg_w - 1, fg_h - 1), outline=(255, 255, 255, 60), width=1)

        # Paste foreground
        canvas.paste(fg_canvas, (paste_x, paste_y), mask=fg_canvas)

        canvas.convert("RGB").save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"      [Blur Background Error] Falha ao aplicar blur de fundo: {os.path.basename(input_path)}: {e}")
        return False

def process_images_pipeline(project_dir):
    images_dir = os.path.join(project_dir, "media", "images")
    processed_dir = os.path.join(project_dir, "media", "processed")
    os.makedirs(processed_dir, exist_ok=True)
    
    # Load storyboard to determine layout style for each image
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    storyboard_scenes = []
    if os.path.exists(storyboard_path):
        try:
            with open(storyboard_path, "r", encoding="utf-8") as f:
                sb_data = json.load(f)
                storyboard_scenes = sb_data.get("scenes", [])
        except Exception as e:
            print(f"    [Warning] Erro ao ler storyboard para processamento de imagem: {e}")

    # 1. Process standard images
    image_files = glob.glob(os.path.join(images_dir, "*.png")) + glob.glob(os.path.join(images_dir, "*.jpg"))
    for filepath in image_files:
        filename = os.path.basename(filepath)
        out_path = os.path.join(processed_dir, filename)
        if os.path.exists(out_path):
            continue
            
        layout_style = "single_card"
        scene = None
        for s in storyboard_scenes:
            sid = s.get("id")
            if filename.startswith(f"{sid}_"):
                scene = s
                break
        if scene:
            layout_style = scene.get("layout_style", "single_card")
                
        if layout_style == "full_screen":
            print(f"    - Processando Pillow blurred background para: {filename}")
            apply_blur_background_styling(filepath, out_path)
        else:
            print(f"    - Processando Pillow card styling para: {filename}")
            apply_card_styling(filepath, out_path)
        
    # 2. Generate custom background color images for text_only scenes
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    if os.path.exists(storyboard_path):
        with open(storyboard_path, "r", encoding="utf-8") as f:
            storyboard = json.load(f)
        for scene in storyboard.get("scenes", []):
            if scene.get("layout_style") == "text_only":
                sid = scene["id"]
                bg_color = scene.get("bg_color", scene.get("background_color", "#121212"))
                out_bg_path = os.path.join(processed_dir, f"{sid}_bg.png")
                if not os.path.exists(out_bg_path):
                    print(f"    - Gerando background sólido ({bg_color}) para cena de texto {sid}")
                    img = Image.new("RGB", (CANVAS_W, CANVAS_H), bg_color)
                    img.save(out_bg_path, "PNG")
    return True

# ── Storyboard Rebuilder ──────────────────────────────────────
def rebuild_storyboard(project_dir):
    """Parses raw storyboard.json and words.json to assign archetypes and build subtitles."""
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    words_path = os.path.join(project_dir, "words.json")
    
    if not os.path.exists(storyboard_path):
        print(f"Erro: storyboard.json não encontrado em {project_dir}")
        return False
        
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)
        
    words = []
    if os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8") as f:
            words = json.load(f)
            
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
    
    # State tracking for balanced alternation across scenes
    last_split_side = None
    last_split_type = None
    last_single_card_pos = None
    
    for idx, scene in enumerate(scenes):
        sid = scene["id"]
        start_ms = scene["start_ms"]
        end_ms = scene["end_ms"]
        narration = scene["narration"]
        
        # Multi-factor entropy seed combining project path, scene index, sid, and narration hash
        scene_seed = int(hashlib.md5(f"{project_dir}_{idx}_{sid}_{narration}".encode("utf-8")).hexdigest()[:8], 16)
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
        if not media or not media.get("query"):
            layout_style = "text_only"
            
        existing_params = dict(scene.get("layout_params", {})) if isinstance(scene.get("layout_params"), dict) else {}
        layout_params = {}
        
        if layout_style == "single_card":
            # Split top/bottom: card is at top, text at bottom or vice-versa
            user_text_pos = existing_params.get("text_pos")
            if user_text_pos in ["top", "bottom"]:
                card_pos = "top" if user_text_pos == "bottom" else "bottom"
            else:
                # Balanced alternating state machine: alternate between top and bottom
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
            
            if card_pos == "top":
                layout_params = {
                    "scale": card_scale,
                    "x": existing_params.get("x", cx_jitter),
                    "y": existing_params.get("y", round(-0.09 + cy_jitter, 3)),
                    "text_pos": "bottom"
                }
            else:
                layout_params = {
                    "scale": card_scale,
                    "x": existing_params.get("x", cx_jitter),
                    "y": existing_params.get("y", round(0.09 + cy_jitter, 3)),
                    "text_pos": "top"
                }
        elif layout_style == "split_info_slide":
            user_split_type = existing_params.get("split_type")
            user_side = existing_params.get("side")
            user_text_pos = existing_params.get("text_pos")
            
            if user_split_type in ["horizontal", "vertical"]:
                split_type = user_split_type
            else:
                # Default to balanced alternation between horizontal and vertical
                if last_split_type == "horizontal" and rng.random() < 0.35:
                    split_type = "vertical"
                else:
                    split_type = "horizontal"
            last_split_type = split_type
            
            card_scale = existing_params.get("scale") or round(rng.uniform(0.68, 0.74), 3)
            
            if split_type == "horizontal":
                # Balanced side alternator: strictly alternates left and right
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
                    "side": side
                }
            else: # vertical
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
                    "text_pos": text_pos
                }
        elif layout_style == "full_screen":
            layout_params = {
                "scale": existing_params.get("scale", 1.0),
                "x": existing_params.get("x", 0.0),
                "y": existing_params.get("y", 0.0)
            }
            
        # 2. Premium background color scheme
        if layout_style == "text_only":
            bg_color = "#0B0B0C"
            text_color = "#FFFFFF"
        elif layout_style in ["single_card", "split_info_slide"]:
            bg_color = "#000000"
            text_color = "#FFFFFF"
        else: # full_screen
            bg_color = "#0B0B0C"
            text_color = "#FFFFFF"
            
        scene["background_color"] = bg_color
        
        # 3. Text layout & positioning
        is_arabic = bool(re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", narration))
        is_cyrillic = bool(re.search(r"[\u0400-\u04FF]", narration))
        if is_arabic:
            font_choices = ["Rubik", "Cairo", "Tajawal", "Almarai", "Roboto", "Segoe UI"]
        elif is_cyrillic:
            font_choices = ["Montserrat", "Inter", "Roboto", "Rubik", "Oswald"]
        else:
            font_choices = ["Montserrat", "Inter", "Bebas Neue", "Oswald", "Outfit", "Plus Jakarta Sans", "Poppins", "Anton", "Rubik", "Cinzel", "Roboto"]
        text_font = rng.choice(font_choices)
        
        # Check if background is light to prevent yellow or light colors on white/light grey
        is_light_bg = bg_color in ["#FAF9F6", "#F5F5F7", "#F9F9FB", "#F4F4F5", "#FAF6F0", "#F5EFEB", "#EDE7E1", "#F6F0E5", "#FFFFFF"]
        
        # Check if narration contains emphasis keywords
        narration_lower = narration.lower()
        if any(w in narration_lower for w in ["urgente", "exclusivo", "grave", "prisão", "denúncia", "operação"]):
            text_color = "#E53935" if is_light_bg else "#FF5252"
        elif any(w in narration_lower for w in ["provas", "revelação", "documento", "sigilo", "relatório"]):
            text_color = "#D97706" if is_light_bg else "#FFD54F"
        elif any(w in narration_lower for w in ["stf", "tribunal", "ministro", "juiz", "decisão", "governo", "congresso"]):
            text_color = "#1E3A8A" if is_light_bg else "#64B5F6"
            
        text_font_size = rng.randint(64, 76)
        font_weight = rng.choice(["bold", "black"])
        
        # Text alignments & positions
        text_align = "center"
        if layout_style == "text_only":
            text_x = 0.0
            text_y = 0.0
            text_font_size = rng.randint(78, 92)
        elif layout_style == "split_info_slide":
            split_type = layout_params.get("split_type", "horizontal")
            if split_type == "horizontal":
                text_x = 0.25 if layout_params.get("side") == "left" else -0.25
                text_y = round(rng.uniform(-0.03, 0.03), 3)
                text_font_size = rng.randint(64, 72)
                text_align = "left"
            else: # vertical split
                text_x = 0.0
                text_pos = layout_params.get("text_pos", "bottom")
                base_y = -0.34 if text_pos == "top" else 0.34
                text_y = round(base_y + rng.uniform(-0.02, 0.02), 3)
                text_font_size = rng.randint(64, 72)
                text_align = "center"
        elif layout_style == "single_card":
            text_x = 0.0
            text_pos = layout_params.get("text_pos", "bottom")
            base_y = 0.34 if text_pos == "bottom" else -0.34
            text_y = round(base_y + rng.uniform(-0.03, 0.03), 3)
            text_align = "center"
            text_font_size = rng.randint(64, 74)
        else: # Full Screen
            text_x = 0.0
            base_y = rng.choice([rng.uniform(0.30, 0.36), rng.uniform(-0.36, -0.30)])
            text_y = round(base_y + rng.uniform(-0.03, 0.03), 3)
            text_font_size = rng.randint(66, 76)
            
        entry_type = rng.choice(["typewriter", "cascade", "pop", "blur", "rise", "drop", "slide_left", "slide_right", "fade_in"])
        exit_type = rng.choice(["fade_out", "rise", "drop", "slide_left", "slide_right", "pop", "blur"])
        
        # 4. Words chunker subtitles - show for all scenes if global_subtitles is True
        global_subtitles = storyboard.get("subtitles", True)
        show_subtitles = global_subtitles and scene.get("subtitles", True)
        text_overlays = []
        existing_overlays = scene.get("text_overlays", [])
        if existing_overlays and any(ov.get("text") for ov in existing_overlays):
            text_overlays = existing_overlays
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
                chunk_limit = rng.choice([1, 2, 2, 3, 3, 4]) # Randomly 1, 2, 3, or 4 words per chunk
                
                def _build_chunk_overlay(chunk_words, start_t, end_t):
                    w_count = len(chunk_words)
                    chunk_txt = " ".join(chunk_words)
                    # Dynamic typography per chunk
                    if w_count == 1:
                        c_size = rng.randint(84, 98)
                        c_weight = "black"
                        c_y = round(text_y + rng.choice([-0.05, 0.0, 0.05]), 3)
                    elif w_count == 2:
                        c_size = rng.randint(72, 84)
                        c_weight = "bold"
                        c_y = round(text_y + rng.choice([-0.02, 0.0, 0.02]), 3)
                    else:
                        c_size = rng.randint(62, 72)
                        c_weight = "bold"
                        c_y = text_y
                    
                    c_font = rng.choice(font_choices) if rng.random() < 0.35 else text_font
                    c_entry = rng.choice(["pop", "blur", "rise", "typewriter", "fade_in"])
                    c_exit = rng.choice(["fade_out", "blur", "pop", "drop"])
                    
                    return {
                        "text": chunk_txt,
                        "appear_at_ms": start_t,
                        "duration_ms": max(800, end_t - start_t),
                        "fontSize": c_size,
                        "fontFamily": c_font,
                        "fontWeight": c_weight,
                        "x": text_x,
                        "y": c_y,
                        "entry": c_entry,
                        "exit": c_exit
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
                        chunk_limit = rng.choice([1, 2, 2, 3, 3, 4]) # Reset chunk limit randomly
                if current_chunk:
                    text_overlays.append(_build_chunk_overlay(current_chunk, chunk_start, end_ms))
            else:
                # Fallback to single text overlay using narrative
                text_raw = scene.get("text_overlay") or narration
                text_overlays.append({
                    "text": text_raw,
                    "appear_at_ms": start_ms,
                    "duration_ms": end_ms - start_ms,
                    "fontSize": text_font_size,
                    "fontFamily": text_font,
                    "fontWeight": font_weight,
                    "x": text_x,
                    "y": text_y,
                    "entry": entry_type,
                    "exit": exit_type
                })
            
            # Enforce sequential (non-overlapping) subtitles
            for i in range(len(text_overlays) - 1):
                curr_overlay = text_overlays[i]
                next_overlay = text_overlays[i+1]
                if curr_overlay["appear_at_ms"] + curr_overlay["duration_ms"] > next_overlay["appear_at_ms"]:
                    curr_overlay["duration_ms"] = max(100, next_overlay["appear_at_ms"] - curr_overlay["appear_at_ms"])
            
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
            "text_layout": {
                "x": text_x,
                "y": text_y,
                "fontSize": text_font_size,
                "color": text_color,
                "fontFamily": text_font,
                "fontWeight": font_weight,
                "textAlign": text_align,
                "entry": entry_type,
                "exit": exit_type
            },
            "text_overlays": text_overlays
        }
        
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
    print(f"  [OK] Storyboard reconstruído com novos arquétipos em: {storyboard_path}")
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
    """Generates HTML templates and renders WebM transparent kinetic typography overlays for subtitles."""
    scenes = storyboard.get("scenes", [])
    if not words:
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

def _append_text_item_with_keyframes(items, all_keyframes, item_id, track_id, from_f, dur_f, label, text, font_size, font_family, font_weight, color, text_align, pos_x, pos_y, text_width, text_height, entry_type, exit_type, is_text_only=False):
    # SNAPPY PREMIUM ANIMATIONS (5 frames transition, small subtle 30px offset)
    trans_dur = 5 if dur_f >= 12 else 3
    # High-contrast solid black stroke (3px to 5px) for 100% crisp legibility on any background
    stroke_opt = {"width": max(3, int(font_size * 0.045)), "color": "#000000"}
    shadow_opt = {"offsetX": 0, "offsetY": 4, "blur": 16, "color": "rgba(0,0,0,0.92)"}
    letter_spacing = -1.2 if font_weight == "bold" else -0.4

    # Native Text Animations mapping (typewriter, fade, pop, cascade, blur, etc.)
    # Map entry types to native FreeCut editor schema
    entry_map = {
        "typewriter": "typewriter",
        "fade_in": "fade",
        "rise": "slide_up",
        "drop": "slide_down",
        "slide_left": "slide_left",
        "slide_right": "slide_right",
        "cascade": "cascade",
        "pop": "pop",
        "blur": "blur"
    }
    
    exit_map = {
        "fade_out": "fade",
        "rise": "slide_up",
        "drop": "slide_down",
        "slide_left": "slide_left",
        "slide_right": "slide_right",
        "sink": "sink",
        "pop": "pop",
        "blur": "blur"
    }

    items.append({
        "id": item_id,
        "trackId": track_id,
        "from": from_f,
        "durationInFrames": dur_f,
        "label": label,
        "type": "text",
        "text": text,
        "fontSize": font_size,
        "fontFamily": font_family,
        "fontWeight": font_weight,
        "color": color,
        "textAlign": text_align,
        "verticalAlign": "middle",
        "lineHeight": 1.15,
        "letterSpacing": letter_spacing,
        "transform": {
            "x": pos_x,
            "y": pos_y,
            "width": text_width,
            "height": text_height
        },
        "stroke": stroke_opt,
        "textShadow": shadow_opt,
        "textAnimation": {
            "entry": {
                "type": entry_map.get(entry_type, "fade"),
                "durationInFrames": trans_dur
            },
            "exit": {
                "type": exit_map.get(exit_type, "fade"),
                "durationInFrames": trans_dur
            }
        },
        "originId": item_id
    })
    
    x_keyframes = []
    y_keyframes = []
    
    # SNAPPY PREMIUM ANIMATIONS (5 frames transition, small subtle 30px offset)
    trans_dur = 5 if dur_f >= 12 else 3
    
    # Entry x & y
    if entry_type == "slide_left":
        x_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_x + 30, "easing": "ease-out"})
        x_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_x, "easing": "ease-out"})
        y_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_y, "easing": "linear"})
    elif entry_type == "slide_right":
        x_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_x - 30, "easing": "ease-out"})
        x_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_x, "easing": "ease-out"})
        y_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_y, "easing": "linear"})
    elif entry_type == "rise":
        x_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_y + 20, "easing": "ease-out"})
        y_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_y, "easing": "ease-out"})
    elif entry_type == "drop":
        x_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_y - 20, "easing": "ease-out"})
        y_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_y, "easing": "ease-out"})
    else: # fade_in (stable x and y)
        x_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": 0, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": trans_dur, "value": pos_y, "easing": "linear"})
        
    # Exit x & y
    exit_start = max(0, dur_f - trans_dur)
    if exit_type == "slide_left":
        x_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_x, "easing": "ease-in"})
        x_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_x - 30, "easing": "ease-in"})
        y_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_y, "easing": "linear"})
    elif exit_type == "slide_right":
        x_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_x, "easing": "ease-in"})
        x_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_x + 30, "easing": "ease-in"})
        y_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_y, "easing": "linear"})
    elif exit_type == "rise":
        x_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_y, "easing": "ease-in"})
        y_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_y - 20, "easing": "ease-in"})
    elif exit_type == "drop":
        x_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_y, "easing": "ease-in"})
        y_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_y + 20, "easing": "ease-in"})
    else: # fade_out or stable exit (stable x and y)
        x_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_x, "easing": "linear"})
        x_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_x, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": exit_start, "value": pos_y, "easing": "linear"})
        y_keyframes.append({"id": get_uid(), "frame": dur_f, "value": pos_y, "easing": "linear"})
        
    # Opacity keyframes
    opacity_keyframes = [
        {"id": get_uid(), "frame": 0, "value": 0, "easing": "ease-out"},
        {"id": get_uid(), "frame": trans_dur, "value": 1, "easing": "ease-out"},
        {"id": get_uid(), "frame": exit_start, "value": 1, "easing": "ease-in"},
        {"id": get_uid(), "frame": dur_f, "value": 0, "easing": "ease-in"}
    ]
    
    all_keyframes.append({
        "itemId": item_id,
        "properties": [
            {"property": "x", "keyframes": x_keyframes},
            {"property": "y", "keyframes": y_keyframes},
            {"property": "opacity", "keyframes": opacity_keyframes}
        ]
    })



def _build_ptbr_subtitles(project_dir, scenes, items, all_keyframes, font_family="Inter"):
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

        # High-legibility typography positioned dead-center (x=0, y=0) throughout the video
        items.append({
            "id": item_id,
            "trackId": "track_sub_ptbr",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_sub_ptbr",
            "type": "text",
            "text": pt_text.strip(),
            "fontSize": 46,
            "fontFamily": font_family,
            "fontWeight": "bold",
            "color": "#FFFFFF",
            "textAlign": "center",
            "verticalAlign": "middle",
            "lineHeight": 1.25,
            "letterSpacing": -0.5,
            "transform": {
                "x": 0,
                "y": 0,
                "width": 1600,
                "height": 220
            },
            "stroke": {"width": 4, "color": "#000000"},
            "textShadow": {"offsetX": 0, "offsetY": 4, "blur": 16, "color": "rgba(0,0,0,0.95)"},
            "textAnimation": {
                "entry": {"type": "fade", "durationInFrames": 3},
                "exit": {"type": "fade", "durationInFrames": 3}
            },
            "originId": item_id
        })
    return has_any

def _build_subtitles(project_dir, scene, items, all_keyframes, add_media_fn, font_family="Montserrat"):
    sid = scene["id"]
    start_ms = scene["start_ms"]
    end_ms = scene["end_ms"]
    start_f = ms_to_frames(start_ms)
    dur_f = ms_to_frames(end_ms - start_ms)
    
    # 1. Add subtitles overlay (if exists) on track_text (below media) - DEPRECATED: WebM subtitle overlay is disabled, always use native text
    has_kinetic_txt = False
    if False and scene.get("subtitles", False) and os.path.exists(txt_filepath):
        media_id = add_media_fn(txt_filepath)
        overlay_id = get_uid()
        items.append({
            "id": overlay_id,
            "trackId": "track_text",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": f"{sid}_kinetic_text",
            "type": "video",
            "mediaRef": media_id,
            "sourceWidth": 1920,
            "sourceHeight": 1080,
            "volume": 0.0,
            "transform": {
                "x": 0, "y": 0,
                "width": CANVAS_W, "height": CANVAS_H,
                "scaleX": 1.0, "scaleY": 1.0
            }
        })
        has_kinetic_txt = True
        
    # 2. Add info card overlay (if exists) on track_fg_1 (ABOVE media)
    card_filename = f"{sid}_card.webm"
    card_filepath = os.path.join(project_dir, "media", "videos", card_filename)
    
    if os.path.exists(card_filepath):
        # Resolve the card's position deterministically to match rendering
        info_card = scene.get("info_card") or {}
        position = info_card.get("position")
        if not position or position == "random":
            rng_card = random.Random(sid + "_card")
            position = rng_card.choice(["top_left", "top_right", "bottom_left", "bottom_right"])
            
        # Determine center offsets for timeline transform
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
        card_dur_f = int(round(card_dur * 30.0))
        if card_dur_f <= 0:
            card_dur_f = dur_f
        card_end_f = min(dur_f, card_dur_f)
        
        items.append({
            "id": overlay_id,
            "trackId": "track_fg_2",   # ABOVE media and separate from adjustment layers!
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
            "volume": 0.0,
            "transform": {
                "x": center_x, "y": center_y,
                "width": 600, "height": 500,
                "scaleX": 1.0, "scaleY": 1.0
            },
            "originId": overlay_id
        })
        
    if has_kinetic_txt:
        return

    # Detect if media is missing to show custom text overlay
    media_missing = False
    entry_type = "rise"
    exit_type = "fade_out"
    
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
        if layout_style in ["single_card", "split_info_slide"]:
            filepath = os.path.join(project_dir, "media", "processed", filename_png)
            if not os.path.exists(filepath):
                filepath = os.path.join(project_dir, "media", "images", filename_png)
        else: # Full Screen image
            filepath = os.path.join(project_dir, "media", "images", filename_png)
            
    if not os.path.exists(filepath):
        import glob
        matches = glob.glob(os.path.join(project_dir, "media", "images", f"{sid}_*"))
        if not matches:
            media_missing = True

    if media_missing:
        # Load words from words.json if possible to chunk narration to max 5 words
        words_path = os.path.join(project_dir, "words.json")
        scene_words = []
        if os.path.exists(words_path):
            try:
                with open(words_path, "r", encoding="utf-8") as f:
                    words = json.load(f)
                scene_words = [
                    w for w in words
                    if w.get("start_ms") is not None and w.get("end_ms") is not None
                    and w["start_ms"] >= start_ms - 200 and w["start_ms"] < end_ms
                ]
                scene_words.sort(key=lambda x: x["start_ms"])
            except Exception as we:
                print(f"      [Warning] Error loading words for missing media subtitle: {we}")
                
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
                if len(current_chunk) >= 5 or has_punct or (w["end_ms"] - chunk_start > 2200):
                    text_overlays.append({
                        "text": " ".join(current_chunk),
                        "appear_at_ms": chunk_start,
                        "duration_ms": max(800, w["end_ms"] - chunk_start)
                    })
                    current_chunk = []
                    chunk_start = None
            if current_chunk:
                text_overlays.append({
                    "text": " ".join(current_chunk),
                    "appear_at_ms": chunk_start if chunk_start is not None else start_ms,
                    "duration_ms": max(800, end_ms - (chunk_start if chunk_start is not None else start_ms))
                })
        else:
            text_overlays = [{
                "text": scene.get("narration", ""),
                "appear_at_ms": start_ms,
                "duration_ms": end_ms - start_ms
            }]
            
        font_size = 75
        font_color = "#FFFFFF"
        font_weight = "bold"
        text_align = "center"
        text_x = 0.0
        text_y = 0.0
        pos_x = 0
        pos_y = 0
        text_width = 1600
        entry_type = "rise"
        exit_type = "fade_out"
    else:
        text_overlays = scene.get("text_overlays", [])
        if not text_overlays:
            return
            
        text_layout = scene.get("text_layout", {})
        font_size = text_layout.get("fontSize", 65)
        font_color = text_layout.get("color", "#FFFFFF")
        font_family = text_layout.get("fontFamily", font_family)
        font_weight = text_layout.get("fontWeight", "bold")
        text_align = text_layout.get("textAlign", "center")
        text_x = text_layout.get("x", 0.0)
        text_y = text_layout.get("y", 0.32)
        entry_type = text_layout.get("entry", "rise")
        exit_type = text_layout.get("exit", "fade_out")
        
        pos_x, pos_y = norm_to_px(text_x, text_y)
        if scene.get("layout_style") == "split_info_slide":
            layout_params = scene.get("layout_params", {})
            split_type = layout_params.get("split_type", "horizontal")
            if split_type == "horizontal":
                text_width = 800
                pos_x = 480 if text_x > 0 else -480
            else: # vertical split (top/bottom)
                text_width = min(1500, (960 - abs(pos_x)) * 2 - 40)
        else:
            text_width = min(1500, (960 - abs(pos_x)) * 2 - 40)
    
    for idx, overlay in enumerate(text_overlays):
        txt = overlay.get("text", "")
        if not txt.strip():
            continue
            
        # Clamp subtitle timing strictly inside scene boundaries to prevent layout overlaps
        t_start = max(start_ms, overlay.get("appear_at_ms", start_ms))
        t_dur = min(end_ms - t_start, overlay.get("duration_ms", end_ms - t_start))
        
        t_start_f = ms_to_frames(t_start)
        t_dur_f = max(1, ms_to_frames(t_dur))
        
        # Enforce non-overlapping subtitles in frames to prevent rounding overlap
        if idx < len(text_overlays) - 1:
            next_overlay = text_overlays[idx + 1]
            next_start = max(start_ms, next_overlay.get("appear_at_ms", start_ms))
            next_start_f = ms_to_frames(next_start)
            if next_start_f > t_start_f:
                t_dur_f = min(t_dur_f, next_start_f - t_start_f)
        
        # Check if solid background layout to apply premium documentary styling
        is_text_only = (scene.get("layout_style") == "text_only")
        is_solid_bg = (scene.get("layout_style") in ["text_only", "single_card", "split_info_slide"])
        
        if False: # Disable kinetic text split entirely
            words_list = txt.split()
            highlight_word = None
            highlight_idx = 0
            
            # Encontra primeira palavra de ênfase
            emphasis_keywords = ["urgente", "exclusivo", "grave", "prisão", "denúncia", "operação", "provas", "revelação", "documento", "sigilo", "relatório", "stf", "tribunal", "decisão", "governo", "congresso"]
            for i, w in enumerate(words_list):
                w_clean = "".join(c for c in w if c.isalnum()).lower()
                if w_clean in emphasis_keywords:
                    highlight_word = w
                    highlight_idx = i
                    break
            
            # Se não achou palavra chave, destaca a palavra mais longa
            if not highlight_word:
                lengths = [len(w) for w in words_list]
                highlight_idx = lengths.index(max(lengths))
                highlight_word = words_list[highlight_idx]
                
            # Reconstrói a frase secundária sem a palavra de destaque
            sec_words = words_list[:highlight_idx] + words_list[highlight_idx+1:]
            sec_text = " ".join(sec_words)
            
            # Determina cor do destaque baseando-se na cor de fundo
            bg_color_hex = scene.get("bg_color", "#121212")
            is_light_bg = bg_color_hex in ["#FAF9F6", "#F5F5F7", "#F9F9FB", "#F4F4F5", "#FAF6F0", "#F5EFEB", "#EDE7E1", "#F6F0E5"]
            if is_light_bg:
                hl_color = "#991B1B" # Deep Rich Crimson Red
                font_color = "#111111" # Deep Graphite Black
            else:
                hl_color = "#FFCC00" # Premium Gold / Yellow
                font_color = "#FFFFFF" # Pure White
                
            # If not solid background, force standard text to be white
            if not is_solid_bg:
                font_color = "#FFFFFF"
                
            # 1. Adiciona o item de destaque (grande, em cima)
            hl_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sub_{idx}_hl"))
            _append_text_item_with_keyframes(
                items=items, all_keyframes=all_keyframes, item_id=hl_id, track_id="track_text",
                from_f=t_start_f, dur_f=t_dur_f, label=f"{sid}_sub_{idx}_hl",
                text=highlight_word.upper(), font_size=font_size + 16, font_family=font_family,
                font_weight="bold", color=hl_color, text_align="center",
                pos_x=pos_x, pos_y=pos_y - 65, text_width=text_width, text_height=140,
                entry_type=entry_type, exit_type=exit_type, is_text_only=is_solid_bg
            )
            
            # 2. Adiciona o item secundário (menor, embaixo)
            sec_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sub_{idx}_sec"))
            _append_text_item_with_keyframes(
                items=items, all_keyframes=all_keyframes, item_id=sec_id, track_id="track_text",
                from_f=t_start_f, dur_f=t_dur_f, label=f"{sid}_sub_{idx}_sec",
                text=sec_text, font_size=max(45, font_size - 14), font_family=font_family,
                font_weight="normal", color=font_color, text_align="center",
                pos_x=pos_x, pos_y=pos_y + 55, text_width=text_width, text_height=140,
                entry_type=entry_type, exit_type=exit_type, is_text_only=is_solid_bg
            )
        else:
            text_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sub_{idx}"))
            # If text_only and single word, display in uppercase
            display_txt = txt.upper() if is_text_only else txt
            
            # Dynamic overlay properties with scene-level fallback
            o_font_size = overlay.get("fontSize", font_size)
            o_font_family = overlay.get("fontFamily", font_family)
            o_font_weight = overlay.get("fontWeight", font_weight)
            o_x = overlay.get("x", text_x)
            o_y = overlay.get("y", text_y)
            o_pos_x, o_pos_y = norm_to_px(o_x, o_y) if (o_x != text_x or o_y != text_y) else (pos_x, pos_y)
            o_entry = overlay.get("entry", entry_type)
            o_exit = overlay.get("exit", exit_type)
            
            hl_size = o_font_size + 10 if is_solid_bg else o_font_size
            
            _append_text_item_with_keyframes(
                items=items, all_keyframes=all_keyframes, item_id=text_id, track_id="track_text",
                from_f=t_start_f, dur_f=t_dur_f, label=f"{sid}_sub_{idx}",
                text=display_txt, font_size=hl_size, font_family=o_font_family,
                font_weight=o_font_weight, color=font_color, text_align=text_align,
                pos_x=o_pos_x, pos_y=o_pos_y, text_width=text_width, text_height=200,
                entry_type=o_entry, exit_type=o_exit, is_text_only=is_solid_bg
            )

def _build_scene_items(project_dir, scene, items, all_keyframes, add_media_fn, global_style="modern_grain"):
    sid = scene["id"]
    layout_style = scene.get("layout_style", "single_card")
    start_ms = scene["start_ms"]
    end_ms = scene["end_ms"]
    duration_ms = end_ms - start_ms
    start_f = ms_to_frames(start_ms)
    dur_f = ms_to_frames(duration_ms)
    
    # (Background generation disabled as per user request to keep timeline clean and show only normal media)
        
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
        
        # 1. Resolve path of download
        filename_mp4 = f"{sid}.mp4"
        filepath_mp4 = os.path.join(project_dir, "media", "videos", filename_mp4)
        lottie_rel_path = media.get("lottie_path")
        
        if source_type == "lottie" and lottie_rel_path:
            is_lottie = True
            filepath = os.path.join(project_dir, lottie_rel_path)
        elif source_type == "video" and os.path.exists(filepath_mp4):
            is_video = True
            filepath = filepath_mp4
        else:
            filename_png = f"{sid}_E01.png"
            filepath = os.path.join(project_dir, "media", "processed", filename_png)
            if not os.path.exists(filepath):
                filepath = os.path.join(project_dir, "media", "images", filename_png)
            
    if not os.path.exists(filepath):
        # Scan fallback
        matches = glob.glob(os.path.join(project_dir, "media", "images", f"{sid}_*"))
        if matches:
            filepath = matches[0]
            if filepath.lower().endswith(".json"):
                is_lottie = True
        else:
            print(f"      [Warning] Nenhuma mídia encontrada no disco para a cena {sid}")
            return
            
    media_id = add_media_fn(filepath)
    item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_anchor"))
    
    # Determine aspect ratio
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
                "volume": 0.0,  # Background video clips strictly muted (volume: 0.0)
                "transform": {
                    "x": 0, "y": 0,
                    "width": CANVAS_W, "height": CANVAS_H,
                    "scaleX": 1.0, "scaleY": 1.0
                },
                "originId": bg_item_id
            }
            
            if bg_asset.media_type == "video":
                bg_dur_s = bg_asset.duration_s if bg_asset.duration_s > 0 else (duration_ms / 1000.0)
                bg_dur_f = int(round(bg_dur_s * FPS))
                if bg_dur_f <= 0:
                    bg_dur_f = dur_f
                bg_end_f = min(dur_f, bg_dur_f)
                bg_item.update({
                    "sourceStart": 0,
                    "sourceEnd": bg_end_f,
                    "sourceDuration": bg_dur_f
                })
            items.append(bg_item)
            
            bg_start_w = int(CANVAS_W * 1.02)
            bg_start_h = int(CANVAS_H * 1.02)
            bg_end_w = int(CANVAS_W * 1.06)
            bg_end_h = int(CANVAS_H * 1.06)
            all_keyframes.append({
                "itemId": bg_item_id,
                "properties": [
                    {"property": "width", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": bg_start_w, "easing": "linear"},
                        {"id": get_uid(), "frame": dur_f, "value": bg_end_w, "easing": "linear"}
                    ]},
                    {"property": "height", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": bg_start_h, "easing": "linear"},
                        {"id": get_uid(), "frame": dur_f, "value": bg_end_h, "easing": "linear"}
                    ]},
                    {"property": "x", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": 0, "easing": "linear"},
                        {"id": get_uid(), "frame": dur_f, "value": 0, "easing": "linear"}
                    ]},
                    {"property": "y", "keyframes": [
                        {"id": get_uid(), "frame": 0, "value": 0, "easing": "linear"},
                        {"id": get_uid(), "frame": dur_f, "value": 0, "easing": "linear"}
                    ]}
                ]
            })



    # ── Active Foreground Layer Support: track_fg_1 ──
    fg_config = scene.get("cutout") or scene.get("foreground")
    if fg_config and isinstance(fg_config, dict):
        fg_path = fg_config.get("path")
        if fg_path and os.path.exists(fg_path):
            fg_media_id = add_media_fn(fg_path)
            fg_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_fg_1"))
            fg_rot = max(-3.0, min(3.0, float(fg_config.get("rotation", 0.0))))
            fg_scale = float(fg_config.get("scale", 0.7))
            fg_w = int(CANVAS_W * fg_scale)
            fg_h = int(CANVAS_H * fg_scale)
            fg_x, fg_y = norm_to_px(float(fg_config.get("x", 0.15)), float(fg_config.get("y", 0.0)))
            items.append({
                "id": fg_item_id,
                "trackId": "track_fg_1",
                "from": start_f,
                "durationInFrames": dur_f,
                "label": f"{sid}_fg_cutout",
                "type": "image",
                "mediaRef": fg_media_id,
                "volume": 0.0,
                "transform": {
                    "x": fg_x, "y": fg_y,
                    "width": fg_w, "height": fg_h,
                    "scaleX": 1.0, "scaleY": 1.0,
                    "rotation": fg_rot
                },
                "originId": fg_item_id
            })

        
    # Sorteador dinâmico de efeitos GPU com jitter baseado no preset global
    effects_list = []
    rng_eff = random.Random(sid + "_effects")
    
    if global_style == "cinematic_retro":
        c_curve = round(rng_eff.uniform(0.20, 0.30), 2)
        c_scan = round(rng_eff.uniform(0.20, 0.30), 2)
        c_vig = round(rng_eff.uniform(0.25, 0.35), 2)
        c_chroma = round(rng_eff.uniform(0.25, 0.35), 2)
        effects_list.append({
            "id": get_uid(), "type": "CRT", "enabled": True,
            "params": {"curvature": c_curve, "scanlines": c_scan, "vignette": c_vig, "chroma": c_chroma},
            "parameters": {"curvature": c_curve, "scanlines": c_scan, "vignette": c_vig, "chroma": c_chroma}
        })
        g_amt = round(rng_eff.uniform(0.04, 0.07), 3)
        g_size = round(rng_eff.uniform(0.9, 1.2), 1)
        effects_list.append({
            "id": get_uid(), "type": "Film Grain", "enabled": True,
            "params": {"amount": g_amt, "size": g_size, "speed": 1.0},
            "parameters": {"amount": g_amt, "size": g_size, "speed": 1.0}
        })
        s_amt = round(rng_eff.uniform(1.00, 1.10), 2)
        effects_list.append({
            "id": get_uid(), "type": "Saturation", "enabled": True,
            "params": {"amount": s_amt},
            "parameters": {"amount": s_amt}
        })
    elif global_style == "vhs_leak":
        c_curve = round(rng_eff.uniform(0.30, 0.40), 2)
        c_scan = round(rng_eff.uniform(0.30, 0.40), 2)
        c_vig = round(rng_eff.uniform(0.30, 0.40), 2)
        c_chroma = round(rng_eff.uniform(0.40, 0.55), 2)
        effects_list.append({
            "id": get_uid(), "type": "CRT", "enabled": True,
            "params": {"curvature": c_curve, "scanlines": c_scan, "vignette": c_vig, "chroma": c_chroma},
            "parameters": {"curvature": c_curve, "scanlines": c_scan, "vignette": c_vig, "chroma": c_chroma}
        })
        g_amt = round(rng_eff.uniform(0.06, 0.10), 3)
        g_size = round(rng_eff.uniform(1.1, 1.4), 1)
        effects_list.append({
            "id": get_uid(), "type": "Film Grain", "enabled": True,
            "params": {"amount": g_amt, "size": g_size, "speed": 1.0},
            "parameters": {"amount": g_amt, "size": g_size, "speed": 1.0}
        })
        s_amt = round(rng_eff.uniform(0.90, 1.00), 2)
        effects_list.append({
            "id": get_uid(), "type": "Saturation", "enabled": True,
            "params": {"amount": s_amt},
            "parameters": {"amount": s_amt}
        })
    elif global_style == "documentary_clean":
        g_amt = round(rng_eff.uniform(0.02, 0.04), 3)
        g_size = round(rng_eff.uniform(0.7, 0.9), 1)
        effects_list.append({
            "id": get_uid(), "type": "Film Grain", "enabled": True,
            "params": {"amount": g_amt, "size": g_size, "speed": 1.0},
            "parameters": {"amount": g_amt, "size": g_size, "speed": 1.0}
        })
        s_amt = round(rng_eff.uniform(1.00, 1.06), 2)
        effects_list.append({
            "id": get_uid(), "type": "Saturation", "enabled": True,
            "params": {"amount": s_amt},
            "parameters": {"amount": s_amt}
        })
    elif global_style == "modern_grain":
        g_amt = round(rng_eff.uniform(0.03, 0.06), 3)
        g_size = round(rng_eff.uniform(0.9, 1.2), 1)
        effects_list.append({
            "id": get_uid(), "type": "Film Grain", "enabled": True,
            "params": {"amount": g_amt, "size": g_size, "speed": 1.0},
            "parameters": {"amount": g_amt, "size": g_size, "speed": 1.0}
        })
        s_amt = round(rng_eff.uniform(1.05, 1.15), 2)
        effects_list.append({
            "id": get_uid(), "type": "Saturation", "enabled": True,
            "params": {"amount": s_amt},
            "parameters": {"amount": s_amt}
        })
        v_amt = round(rng_eff.uniform(0.20, 0.30), 2)
        effects_list.append({
            "id": get_uid(), "type": "Vignette", "enabled": True,
            "params": {"amount": v_amt},
            "parameters": {"amount": v_amt}
        })
        
    # Sorteador dinâmico de modificadores procedimentais
    motion_modifiers = []
    rng_mot = random.Random(sid + "_motion")
    if layout_style in ["single_card", "split_info_slide"] or is_lottie:
        b_scale = round(rng_mot.uniform(1.03, 1.06), 3)
        b_speed = round(rng_mot.uniform(0.6, 1.0), 2)
        s_amp = rng_mot.randint(6, 12)
        s_speed = round(rng_mot.uniform(0.4, 0.7), 2)
        
        motion_modifiers = [
            {"type": "breath", "scale": b_scale, "speed": b_speed, "active": True, "enabled": True},
            {"type": "sway", "amplitude": s_amp, "speed": s_speed, "active": True, "enabled": True}
        ]

    if layout_style in ["full_screen", "text_only"] and not is_lottie:
        rng = random.Random(sid)
        base_x = 0
        base_y = 0
        base_w = CANVAS_W
        base_h = CANVAS_H
        
        # Procedural Ken Burns zoom engine with robust safety overflow to prevent any canvas border leak
        # Apply zoom to all full-screen images (we exclude text_only and videos to keep balance)
        apply_zoom = False
        if not has_info_card and layout_style != "text_only" and not is_video:
            apply_zoom = True
            
        if apply_zoom:
            # Check camera_motion from scene or choose dynamically
            c_motion = str(scene.get("camera_motion") or "").lower().strip()
            
            # Multi-factor entropy seed
            rng_kb = random.Random(f"{sid}_kb_motion")
            
            # Determine zoom direction and type:
            # Options: zoom_in (push-in), zoom_out (pull-out), pan_left, pan_right, tilt_up, tilt_down, diagonal
            if c_motion in ["zoom_out_center", "slow_pull_out", "pull_out"]:
                motion_type = "zoom_out"
                pan_dir = "center"
            elif c_motion in ["zoom_in_center", "slow_push_in", "push_in"]:
                motion_type = "zoom_in"
                pan_dir = "center"
            elif c_motion in ["pan_left", "pan_right_left"]:
                motion_type = "pan"
                pan_dir = "left"
            elif c_motion in ["pan_right", "pan_left_right"]:
                motion_type = "pan"
                pan_dir = "right"
            elif c_motion in ["tilt_up", "pan_bottom_top"]:
                motion_type = "pan"
                pan_dir = "top"
            elif c_motion in ["tilt_down", "pan_top_bottom"]:
                motion_type = "pan"
                pan_dir = "bottom"
            elif c_motion in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                motion_type = "zoom_in"
                pan_dir = c_motion
            else:
                # Organic balanced distribution:
                # ~40% Zoom In (Push-In), ~35% Zoom Out (Pull-Out), ~15% Pan, ~10% Diagonal
                motion_type = rng_kb.choices(
                    ["zoom_in", "zoom_out", "pan", "diagonal"],
                    weights=[40, 35, 15, 10],
                    k=1
                )[0]
                if motion_type == "zoom_in":
                    pan_dir = rng_kb.choice(["center", "top_left", "top_right", "bottom_left", "bottom_right"])
                elif motion_type == "zoom_out":
                    pan_dir = rng_kb.choice(["center", "top", "bottom", "left", "right"])
                elif motion_type == "pan":
                    pan_dir = rng_kb.choice(["left", "right", "top", "bottom"])
                else: # diagonal
                    pan_dir = rng_kb.choice(["top_left", "top_right", "bottom_left", "bottom_right"])

            # Humanized micro-jitter (subtle handheld camera imperfection, -4px to +4px)
            jitter_x = rng_kb.randint(-4, 4)
            jitter_y = rng_kb.randint(-3, 3)

            # Zoom magnitude (5% to 9% delta)
            zoom_delta = round(rng_kb.uniform(0.05, 0.09), 3)
            base_safety_margin = 0.05  # 5% safety scale so we never leak canvas borders

            if motion_type == "zoom_in":
                # Start at safety margin, zoom in to (safety + delta)
                start_scale = 1.0 + base_safety_margin
                end_scale = 1.0 + base_safety_margin + zoom_delta
                
                start_w = int(base_w * start_scale)
                start_h = int(base_h * start_scale)
                end_w = int(base_w * end_scale)
                end_h = int(base_h * end_scale)

                max_x = (end_w - base_w) // 2
                max_y = (end_h - base_h) // 2

                start_x = jitter_x
                start_y = jitter_y

                if pan_dir == "center":
                    end_x = 0
                    end_y = 0
                elif pan_dir == "top_left":
                    end_x = max_x
                    end_y = max_y
                elif pan_dir == "bottom_right":
                    end_x = -max_x
                    end_y = -max_y
                elif pan_dir == "top_right":
                    end_x = -max_x
                    end_y = max_y
                elif pan_dir == "bottom_left":
                    end_x = max_x
                    end_y = -max_y
                elif pan_dir == "left":
                    end_x = max_x
                    end_y = 0
                elif pan_dir == "right":
                    end_x = -max_x
                    end_y = 0
                elif pan_dir == "top":
                    end_x = 0
                    end_y = max_y
                else: # bottom
                    end_x = 0
                    end_y = -max_y

            elif motion_type == "zoom_out":
                # Start zoomed in (safety + delta), zoom out to safety margin
                start_scale = 1.0 + base_safety_margin + zoom_delta
                end_scale = 1.0 + base_safety_margin
                
                start_w = int(base_w * start_scale)
                start_h = int(base_h * start_scale)
                end_w = int(base_w * end_scale)
                end_h = int(base_h * end_scale)

                max_x = (start_w - base_w) // 2
                max_y = (start_h - base_h) // 2

                end_x = jitter_x
                end_y = jitter_y

                if pan_dir == "center":
                    start_x = 0
                    start_y = 0
                elif pan_dir == "top_left":
                    start_x = max_x
                    start_y = max_y
                elif pan_dir == "bottom_right":
                    start_x = -max_x
                    start_y = -max_y
                elif pan_dir == "top_right":
                    start_x = -max_x
                    start_y = max_y
                elif pan_dir == "bottom_left":
                    start_x = max_x
                    start_y = -max_y
                elif pan_dir == "left":
                    start_x = max_x
                    start_y = 0
                elif pan_dir == "right":
                    start_x = -max_x
                    start_y = 0
                elif pan_dir == "top":
                    start_x = 0
                    start_y = max_y
                else: # bottom
                    start_x = 0
                    start_y = -max_y

            else: # Pan or Diagonal constant scale drift
                fixed_scale = 1.0 + base_safety_margin + (zoom_delta / 2.0)
                start_w = int(base_w * fixed_scale)
                start_h = int(base_h * fixed_scale)
                end_w = start_w
                end_h = start_h

                max_x = (start_w - base_w) // 2
                max_y = (start_h - base_h) // 2

                if pan_dir in ["left", "top_left", "bottom_left"]:
                    start_x = -max_x + jitter_x
                    end_x = max_x
                elif pan_dir in ["right", "top_right", "bottom_right"]:
                    start_x = max_x + jitter_x
                    end_x = -max_x
                else:
                    start_x = jitter_x
                    end_x = -jitter_x

                if pan_dir in ["top", "top_left", "top_right"]:
                    start_y = -max_y + jitter_y
                    end_y = max_y
                elif pan_dir in ["bottom", "bottom_left", "bottom_right"]:
                    start_y = max_y + jitter_y
                    end_y = -max_y
                else:
                    start_y = jitter_y
                    end_y = -jitter_y

            # Organic Easing: ease-out or ease-in-out or linear
            kb_easing = rng_kb.choice(["linear", "ease-out", "ease-in-out"])
        else:
            # For static items, apply a 1% safety zoom so rounding errors never expose the canvas background
            safety_scale = 1.01
            start_w = int(base_w * safety_scale)
            start_h = int(base_h * safety_scale)
            end_w = start_w
            end_h = start_h
            start_x = 0
            end_x = 0
            start_y = 0
            end_y = 0
            kb_easing = "linear"

            
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
            "volume": 0.0 if is_video else 1.0,
            "transform": {
                "x": start_x, "y": start_y,
                "width": start_w, "height": start_h,
                "scaleX": 1.0, "scaleY": 1.0
            },
            # "effects": effects_list,
            # "motionModifiers": motion_modifiers,
            # "motion_modifiers": motion_modifiers,
            "originId": item_id
        }
        if is_video:
            video_duration = meta["duration"] if "meta" in locals() else duration_ms / 1000.0
            source_dur = video_duration if video_duration > 0.0 else duration_ms / 1000.0
            source_dur_f = int(round(source_dur * 30.0))
            if source_dur_f <= 0:
                source_dur_f = dur_f
            source_end_f = min(dur_f, source_dur_f)
            full_screen_item.update({
                "sourceStart": 0,
                "sourceEnd": source_end_f,
                "sourceDuration": source_dur_f
            })
        items.append(full_screen_item)
        
        all_keyframes.append({
            "itemId": item_id,
            "properties": [
                {"property": "width", "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_w, "easing": kb_easing},
                    {"id": get_uid(), "frame": dur_f, "value": end_w, "easing": kb_easing}
                ]},
                {"property": "height", "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_h, "easing": kb_easing},
                    {"id": get_uid(), "frame": dur_f, "value": end_h, "easing": kb_easing}
                ]},
                {"property": "x", "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_x, "easing": kb_easing},
                    {"id": get_uid(), "frame": dur_f, "value": end_x, "easing": kb_easing}
                ]},
                {"property": "y", "keyframes": [
                    {"id": get_uid(), "frame": 0, "value": start_y, "easing": kb_easing},
                    {"id": get_uid(), "frame": dur_f, "value": end_y, "easing": kb_easing}
                ]}
            ]
        })
        # Causal SFX for kinetic transitions only (slide, lensWarpZoom, wipe)
        if start_f > 0 and scene.get("transition") in ["slide", "lensWarpZoom", "wipe"]:
            sfx_config = scene.get("sfx")
            allow_sfx = True
            if isinstance(sfx_config, dict) and sfx_config.get("enabled") is False:
                allow_sfx = False
            if allow_sfx:
                rng_sfx = random.Random(f"{sid}_trans_sfx")
                if rng_sfx.random() < 0.35 or (isinstance(sfx_config, dict) and sfx_config.get("enabled")):
                    sfx_asset = asset_catalog.get_sfx(kind="whoosh", fallback=True, deterministic_seed=f"{sid}_sfx")
                    if sfx_asset and sfx_asset.exists():
                        sfx_media_id = add_media_fn(sfx_asset.path)
                        sfx_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sfx"))
                        # Organic SFX volume in dB directly (-20 dB to -32 dB based on native loudness)
                        rng_vol = random.Random(f"{sid}_vol")
                        jitter_db = rng_vol.uniform(-1.5, 1.5)
                        base_db = getattr(sfx_asset, "default_gain_db", -24.0)
                        final_sfx_db = round(base_db + jitter_db, 1)
                        items.append({
                            "id": sfx_item_id,
                            "trackId": "track_sfx",
                            "from": start_f,
                            "durationInFrames": sfx_asset.duration_frames_30fps,
                            "label": sfx_asset.filename,
                            "type": "audio",
                            "mediaRef": sfx_media_id,
                            "sourceStart": 0.0,
                            "sourceEnd": sfx_asset.duration_s,
                            "sourceDuration": sfx_asset.duration_s,
                            "volume": final_sfx_db,
                            "originId": sfx_item_id
                        })
    else: # single_card, split_info_slide, or is_lottie
        # Calculate bounding box
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
        
        apply_zoom = False
        if not has_info_card and not is_lottie:
            apply_zoom = rng.choice([True, False])
            
        zoom_pct = round(rng.uniform(0.04, 0.08), 3)
        zoom_in = rng.choice([True, False])
        pan_type = rng.choice(["center", "top_left", "bottom_right", "top_right", "bottom_left"])
        
        jitter_x = rng.randint(-3, 3)
        jitter_y = rng.randint(-3, 3)
        
        if apply_zoom:
            if zoom_in:
                start_w, end_w = base_w, int(base_w * (1.0 + zoom_pct))
                start_h, end_h = base_h, int(base_h * (1.0 + zoom_pct))
            else:
                start_w, end_w = int(base_w * (1.0 + zoom_pct)), base_w
                start_h, end_h = int(base_h * (1.0 + zoom_pct)), base_h
                
            dx_start = start_w - base_w
            dx_end = end_w - base_w
            dy_start = start_h - base_h
            dy_end = end_h - base_h
            
            if pan_type == "center":
                start_x = int(base_x - dx_start / 2) + jitter_x
                end_x = int(base_x - dx_end / 2)
                start_y = int(base_y - dy_start / 2) + jitter_y
                end_y = int(base_y - dy_end / 2)
            elif pan_type == "top_left":
                start_x = base_x + jitter_x
                end_x = base_x
                start_y = base_y + jitter_y
                end_y = base_y
            elif pan_type == "bottom_right":
                start_x = base_x - dx_start + jitter_x
                end_x = base_x - dx_end
                start_y = base_y - dy_start + jitter_y
                end_y = base_y - dy_end
            elif pan_type == "top_right":
                start_x = base_x - dx_start + jitter_x
                end_x = base_x - dx_end
                start_y = base_y + jitter_y
                end_y = base_y
            else: # bottom_left
                start_x = base_x + jitter_x
                end_x = base_x
                start_y = base_y - dy_start + jitter_y
                end_y = base_y - dy_end
        else:
            start_w, end_w = base_w, base_w
            start_h, end_h = base_h, base_h
            start_x, end_x = base_x, base_x
            start_y, end_y = base_y, base_y
 
        # Dynamic Animation Parameter Calculator for cards/lotties (entrance slide & slow float wave)
        # 1. Entrance parameters (slide from screen edges)
        sfx_config = scene.get("sfx")
        if isinstance(sfx_config, dict) and sfx_config.get("enabled"):
            apply_entrance = True
        else:
            apply_entrance = rng.choice([True, True, False]) # 66% chance of slide entrance
        entrance_dir = rng.choice(["left", "right", "top", "bottom"])
        intro_dur = 14 # ~0.45 seconds at 30 FPS
        if intro_dur >= dur_f:
            apply_entrance = False
            
        # 2. Float parameters (subtle, slow organic oscillation)
        apply_float = rng.choice([True, False, False, False]) # 25% chance of slow float
        float_amp = rng.randint(8, 16)
        float_period = rng.randint(85, 140) # Slower period: 2.8s to 4.6s (reduced speed by 30%+)
        
        # Calculate initial coordinates for default transform
        init_x = start_x
        init_y = start_y
        
        if apply_entrance:
            # Shift starting positions off-screen natively using center-based coordinates (1920x1080 canvas from -960 to 960 and -540 to 540)
            if entrance_dir == "left":
                init_x = -960 - (start_w // 2) - 50
            elif entrance_dir == "right":
                init_x = 960 + (start_w // 2) + 50
            elif entrance_dir == "top":
                init_y = 540 + (start_h // 2) + 50
            elif entrance_dir == "bottom":
                init_y = -540 - (start_h // 2) - 50

        # Organic card rotations clamped strictly between [-3.0°, +3.0°]
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
            "volume": 0.0 if (is_video or is_lottie) else 1.0,
            "transform": {
                "x": init_x, "y": init_y,
                "width": start_w, "height": start_h,
                "scaleX": 1.0, "scaleY": 1.0,
                "rotation": card_rotation,
                "cornerRadius": 0 if is_lottie else (85 if is_video else 48),
                "dropShadow": {"blur": 24, "color": "rgba(0,0,0,0.45)", "offsetX": 0, "offsetY": 8}
            },
            "originId": item_id
        }
        if is_video:
            video_duration = meta["duration"] if "meta" in locals() else duration_ms / 1000.0
            source_dur = video_duration if video_duration > 0.0 else duration_ms / 1000.0
            source_dur_f = int(round(source_dur * 30.0))
            if source_dur_f <= 0:
                source_dur_f = dur_f
            source_end_f = min(dur_f, source_dur_f)
            card_item.update({
                "sourceStart": 0,
                "sourceEnd": source_end_f,
                "sourceDuration": source_dur_f
            })
        items.append(card_item)
        
        # Causal SFX tied strictly to physical slide entrance of card
        if apply_entrance and start_f > 0:
            sfx_config = scene.get("sfx")
            allow_sfx = True
            if isinstance(sfx_config, dict) and sfx_config.get("enabled") is False:
                allow_sfx = False
            if allow_sfx:
                sfx_asset = asset_catalog.get_sfx(kind="whoosh", fallback=True, deterministic_seed=f"{sid}_sfx")
                if sfx_asset and sfx_asset.exists():
                    sfx_media_id = add_media_fn(sfx_asset.path)
                    sfx_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_sfx"))
                    # Organic SFX volume in dB directly (-20 dB to -32 dB based on native loudness)
                    rng_vol = random.Random(f"{sid}_vol")
                    jitter_db = rng_vol.uniform(-1.5, 1.5)
                    base_db = getattr(sfx_asset, "default_gain_db", -24.0)
                    final_sfx_db = round(base_db + jitter_db, 1)
                    if isinstance(sfx_config, dict) and "volume" in sfx_config:
                        try:
                            raw_v = float(sfx_config["volume"])
                            final_sfx_db = max(-45.0, min(-10.0, raw_v if raw_v < 0 else -abs(raw_v)))
                        except (ValueError, TypeError):
                            pass
                    items.append({
                        "id": sfx_item_id,
                        "trackId": "track_sfx",
                        "from": start_f,
                        "durationInFrames": min(intro_dur, sfx_asset.duration_frames_30fps),
                        "label": sfx_asset.filename,
                        "type": "audio",
                        "mediaRef": sfx_media_id,
                        "sourceStart": 0.0,
                        "sourceEnd": sfx_asset.duration_s,
                        "sourceDuration": sfx_asset.duration_s,
                        "volume": final_sfx_db,
                        "originId": sfx_item_id
                    })
        
        # Build width/height zoom keyframes
        width_kfs = [
            {"id": get_uid(), "frame": 0, "value": start_w, "easing": "linear"},
            {"id": get_uid(), "frame": dur_f, "value": end_w, "easing": "linear"}
        ]
        height_kfs = [
            {"id": get_uid(), "frame": 0, "value": start_h, "easing": "linear"},
            {"id": get_uid(), "frame": dur_f, "value": end_h, "easing": "linear"}
        ]
        
        # Build x and y keyframes
        x_kfs = []
        y_kfs = []
        
        if apply_entrance:
            x_kfs.append({"id": get_uid(), "frame": 0, "value": init_x, "easing": "ease-out"})
            y_kfs.append({"id": get_uid(), "frame": 0, "value": init_y, "easing": "ease-out"})
            
            # Interpolated base center positions at the end of entrance
            ratio_intro = intro_dur / float(dur_f)
            base_x_intro = int(start_x + (end_x - start_x) * ratio_intro)
            base_y_intro = int(start_y + (end_y - start_y) * ratio_intro)
            
            x_kfs.append({"id": get_uid(), "frame": intro_dur, "value": base_x_intro, "easing": "linear"})
            y_kfs.append({"id": get_uid(), "frame": intro_dur, "value": base_y_intro, "easing": "linear"})
            
            start_f_range = intro_dur
        else:
            x_kfs.append({"id": get_uid(), "frame": 0, "value": start_x, "easing": "linear"})
            y_kfs.append({"id": get_uid(), "frame": 0, "value": start_y, "easing": "linear"})
            start_f_range = 0
            
        # Add intermediate keyframes for floating/sway oscillation
        sample_step = 12
        for f in range(start_f_range + sample_step, dur_f, sample_step):
            t_ratio = (f - start_f_range) / float(dur_f - start_f_range) if dur_f > start_f_range else 1.0
            
            if apply_entrance:
                ratio_intro = start_f_range / float(dur_f)
                x_base_start = start_x + (end_x - start_x) * ratio_intro
                y_base_start = start_y + (end_y - start_y) * ratio_intro
                x_base = int(x_base_start + (end_x - x_base_start) * t_ratio)
                y_base = int(y_base_start + (end_y - y_base_start) * t_ratio)
            else:
                x_base = int(start_x + (end_x - start_x) * t_ratio)
                y_base = int(start_y + (end_y - start_y) * t_ratio)
                
            if apply_float:
                import math
                y_offset = int(float_amp * math.sin(2 * math.pi * (f - start_f_range) / float_period))
                x_offset = int((float_amp // 3) * math.cos(2 * math.pi * (f - start_f_range) / float_period))
                x_val = x_base + x_offset
                y_val = y_base + y_offset
            else:
                x_val = x_base
                y_val = y_base
                
            x_kfs.append({"id": get_uid(), "frame": f, "value": x_val, "easing": "linear"})
            y_kfs.append({"id": get_uid(), "frame": f, "value": y_val, "easing": "linear"})
            
        # Final keyframes
        x_kfs.append({"id": get_uid(), "frame": dur_f, "value": end_x, "easing": "linear"})
        y_kfs.append({"id": get_uid(), "frame": dur_f, "value": end_y, "easing": "linear"})
        
        rot_kfs = [
            {"id": get_uid(), "frame": 0, "value": card_rotation, "easing": "linear"},
            {"id": get_uid(), "frame": dur_f, "value": card_rotation, "easing": "linear"}
        ]
        
        all_keyframes.append({
            "itemId": item_id,
            "properties": [
                {"property": "width", "keyframes": width_kfs},
                {"property": "height", "keyframes": height_kfs},
                {"property": "x", "keyframes": x_kfs},
                {"property": "y", "keyframes": y_kfs},
                {"property": "rotation", "keyframes": rot_kfs}
            ]
        })
def _build_scene_adjustments(project_id, scenes, items):
    if not scenes:
        return
        
    # Seed random generator with the project id to keep it deterministic
    import random as prng
    rng = prng.Random(f"{project_id}_adjustments")
    
    # 1. Choose a random percentage of eligible scenes (not text_only) to have effects (10% to 40%)
    eligible_indices = [i for i, s in enumerate(scenes) if s.get("layout_style") != "text_only"]
    if not eligible_indices:
        print("  [Adjustment Layers] Nenhuma cena elegível para efeitos (todas são text_only).")
        return
        
    num_eligible = len(eligible_indices)
    pct = rng.uniform(0.10, 0.40)
    num_effects = max(1, int(round(num_eligible * pct)))
    num_effects = min(num_effects, num_eligible)
    
    # Randomly select which scene indices will have effects
    effect_indices = rng.sample(eligible_indices, num_effects)
    print(f"  [Adjustment Layers] Aplicando camadas de ajuste em {num_effects} de {num_eligible} cenas elegíveis (indices: {effect_indices})")
    
    project_styles = ["cinematic_retro", "vhs_leak", "vintage_sepia", "noir_bw", "modern_grain", "trigger_wave", "documentary_clean"]
    
    for idx in effect_indices:
        scene = scenes[idx]
        sid = scene["id"]
        start_f = ms_to_frames(scene["start_ms"])
        dur_f = ms_to_frames(scene["end_ms"] - scene["start_ms"])
        
        # Sorteia o estilo para esta cena específica
        style = rng.choice(project_styles)
        
        # Semente baseada no ID da cena para calibrar os valores deste clipe
        rng_scene = prng.Random(f"{sid}_effects_calib")
        
        effects_list = []
        
        if style == "cinematic_retro":
            # 1. CRT (Slightly warped analog monitor look)
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_crt")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-crt",
                    "params": {
                        "curvature": round(rng_scene.uniform(0.12, 0.18), 2),
                        "scanlines": round(rng_scene.uniform(0.15, 0.22), 2),
                        "vignette": round(rng_scene.uniform(0.18, 0.25), 2),
                        "chroma": round(rng_scene.uniform(0.15, 0.25), 2)
                    }
                },
                "enabled": True
            })
            # 2. Grain (Subtle film grain)
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grain",
                    "params": {
                        "amount": round(rng_scene.uniform(0.02, 0.045), 3),
                        "size": round(rng_scene.uniform(0.8, 1.1), 1),
                        "speed": 1
                    }
                },
                "enabled": True
            })
            # 3. Saturation (Warm cinematic boost)
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_sat")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-saturation",
                    "params": {
                        "amount": round(rng_scene.uniform(1.02, 1.12), 2)
                    }
                },
                "enabled": True
            })
        elif style == "vhs_leak":
            # 1. VHS (Slight tape damage)
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_vhs")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-vhs",
                    "params": {
                        "bleed": round(rng_scene.uniform(0.20, 0.30), 2),
                        "waviness": round(rng_scene.uniform(0.10, 0.20), 2),
                        "noise": round(rng_scene.uniform(0.06, 0.10), 2),
                        "scanline": round(rng_scene.uniform(0.10, 0.18), 2),
                        "speed": 1
                    }
                },
                "enabled": True
            })
            # 2. CRT
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_crt")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-crt",
                    "params": {
                        "curvature": round(rng_scene.uniform(0.10, 0.18), 2),
                        "scanlines": round(rng_scene.uniform(0.12, 0.20), 2),
                        "vignette": round(rng_scene.uniform(0.18, 0.25), 2),
                        "chroma": round(rng_scene.uniform(0.12, 0.22), 2)
                    }
                },
                "enabled": True
            })
            # 3. Grain
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grain",
                    "params": {
                        "amount": round(rng_scene.uniform(0.025, 0.045), 3),
                        "size": round(rng.uniform(0.9, 1.1), 1),
                        "speed": 1
                    }
                },
                "enabled": True
            })
        elif style == "vintage_sepia":
            # 1. Sepia
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_sepia")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-sepia",
                    "params": {
                        "amount": round(rng_scene.uniform(0.20, 0.35), 2)
                    }
                },
                "enabled": True
            })
            # 2. Contrast
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_contrast")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-contrast",
                    "params": {
                        "amount": round(rng_scene.uniform(1.05, 1.15), 2)
                    }
                },
                "enabled": True
            })
            # 3. Brightness
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_brightness")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-brightness",
                    "params": {
                        "amount": round(rng_scene.uniform(-0.08, -0.04), 2)
                    }
                },
                "enabled": True
            })
        elif style == "noir_bw":
            # 1. Grayscale
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grayscale")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grayscale",
                    "params": {
                        "amount": 1.0
                    }
                },
                "enabled": True
            })
            # 2. Contrast
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_contrast")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-contrast",
                    "params": {
                        "amount": round(rng_scene.uniform(1.15, 1.30), 2)
                    }
                },
                "enabled": True
            })
        elif style == "modern_grain":
            # 1. Grain
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grain",
                    "params": {
                        "amount": round(rng_scene.uniform(0.015, 0.035), 3),
                        "size": round(rng_scene.uniform(0.8, 1.1), 1),
                        "speed": 1
                    }
                },
                "enabled": True
            })
        elif style == "trigger_wave":
            # 1. Trigger Wave (disabled by default)
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_trigger")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-trigger-wave",
                    "params": {
                        "strength": 0.04, "radius": 0.9, "frequency": 20, "decay": 0.07,
                        "phase": 0, "speed": 0.8, "centerX": 0.5, "centerY": 0.5,
                        "chroma": 0.008, "scanlineMix": 0.2, "glowColor": "#2e6b8c"
                    }
                },
                "enabled": False
            })
            # 2. RGB Split
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_rgb")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-rgb-split",
                    "params": {
                        "amount": round(rng_scene.uniform(0.004, 0.007), 4),
                        "angle": 0
                    }
                },
                "enabled": True
            })
            # 3. Scanlines
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_scanlines")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-scanlines",
                    "params": {
                        "density": 8,
                        "opacity": round(rng_scene.uniform(0.10, 0.16), 2),
                        "speed": 0.6
                    }
                },
                "enabled": True
            })
            # 4. Grain
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grain",
                    "params": {
                        "amount": round(rng_scene.uniform(0.02, 0.045), 3),
                        "size": round(rng_scene.uniform(0.8, 1.1), 1),
                        "speed": 1
                    }
                },
                "enabled": True
            })
        elif style == "documentary_clean":
            # Subtle vignette + grain
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_vignette")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-vignette",
                    "params": {
                        "amount": round(rng_scene.uniform(0.35, 0.50), 2),
                        "size": 0.5,
                        "softness": 0.5,
                        "roundness": 1
                    }
                },
                "enabled": True
            })
            effects_list.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_effect_grain")),
                "effect": {
                    "type": "gpu-effect",
                    "gpuEffectType": "gpu-grain",
                    "params": {
                        "amount": 0.012,
                        "size": 0.8,
                        "speed": 1
                    }
                },
                "enabled": True
            })

        adjustment_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sid}_adjustment"))
        items.append({
            "id": adjustment_id,
            "type": "adjustment",
            "trackId": "track_fg_1",
            "from": start_f,
            "durationInFrames": dur_f,
            "label": style.upper().replace("_", " "),
            "effects": effects_list,
            "effectOpacity": 1,
            "originId": adjustment_id
        })


def build_freecut_bundle(project_dir):
    print(f"  Iniciando compilação do FreeCut bundle para: {project_dir}")
    storyboard_file = os.path.join(project_dir, "storyboard.json")
    if not os.path.exists(storyboard_file):
        print(f"  Erro: storyboard.json não encontrado em: {project_dir}")
        return False
        
    with open(storyboard_file, "r", encoding="utf-8") as f:
        storyboard = json.load(f)
        
    words = []
    words_file = os.path.join(project_dir, "words.json")
    if os.path.exists(words_file):
        with open(words_file, "r", encoding="utf-8") as f:
            words = json.load(f)
            
    # Render kinetic typography using HyperFrames first
    render_hyperframes_subtitles(project_dir, storyboard, words)
        
    scenes = storyboard.get("scenes", [])
    total_dur_ms = storyboard.get("total_duration_ms", 0)
    if not total_dur_ms and scenes:
        total_dur_ms = max(s.get("end_ms", 0) for s in scenes)
    title = storyboard.get("title", "freecut-project")
    
    has_cyrillic = any(re.search(r"[\u0400-\u04FF]", s.get("narration", "")) for s in scenes)
    if has_cyrillic:
        allowed_fonts = ["Roboto", "Open Sans", "Inter", "Montserrat"]
    else:
        allowed_fonts = ["Roboto", "Open Sans", "Google Sans", "Noto Sans JP", "Inter", "Montserrat"]
    chosen_font = random.choice(allowed_fonts)
    print(f"  [Font] Fonte selecionada aleatoriamente para o vídeo: {chosen_font}")
    
    audio_files = glob.glob(os.path.join(project_dir, "*.mp3")) + glob.glob(os.path.join(project_dir, "*.wav"))
    if not audio_files:
        print("  Erro: Nenhum arquivo de áudio (.wav ou .mp3) encontrado na raiz do projeto")
        return False
    audio_file = audio_files[0]
    raw_audio_dur = get_audio_duration_ms(audio_file) or total_dur_ms
    audio_dur_ms = min(raw_audio_dur, total_dur_ms) if total_dur_ms > 0 else raw_audio_dur
    
    safe_title = "".join(c if c.isalnum() or c in "_- " else "" for c in title).replace(" ", "_")[:40]
    project_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, safe_title))
    # 0. Sorteia o estilo de câmera global para o projeto (Editor virtual)
    rng_proj = random.Random(project_id)
    project_styles = ["cinematic_retro", "vhs_leak", "vintage_sepia", "noir_bw", "modern_grain", "trigger_wave", "documentary_clean"]
    global_style = rng_proj.choice(project_styles)
    print(f"  [Style] Estilo de câmera global selecionado para o projeto: {global_style}")
    
    items = []
    all_keyframes = []
    manifest_media = []
    media_files_to_zip = []
    seen_media_ids = set()
    media_id_to_filepath = {}
    
    def add_media(filepath):
        sha256 = compute_sha256(filepath)
        media_id = str(uuid.uuid5(uuid.NAMESPACE_OID, sha256))
        media_id_to_filepath[media_id] = filepath
        if media_id in seen_media_ids:
            return media_id
        seen_media_ids.add(media_id)
        rel_path = f"media/{os.path.basename(filepath)}"
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
            dur_ms = get_audio_duration_ms(filepath)
            duration = (dur_ms / 1000.0) if dur_ms else 1.0
            codec = "mp3" if filepath.lower().endswith(".mp3") else "wav"
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
            "fileName": os.path.basename(filepath),
            "fileSize": os.path.getsize(filepath),
            "sha256": sha256,
            "mimeType": mime,
            "metadata": {
                "duration": duration, "width": w, "height": h, "fps": fps,
                "codec": codec, "bitrate": 0
            }
        })
        media_files_to_zip.append((filepath, rel_path))
        return media_id

    # 1. Add audio media and item
    audio_sha256 = compute_sha256(audio_file)
    audio_media_id = str(uuid.uuid5(uuid.NAMESPACE_OID, audio_sha256))
    audio_rel = f"media/{os.path.basename(audio_file)}"
    manifest_media.append({
        "originalId": audio_media_id,
        "relativePath": audio_rel,
        "fileName": os.path.basename(audio_file),
        "fileSize": os.path.getsize(audio_file),
        "sha256": audio_sha256,
        "mimeType": detect_mime(audio_file),
        "metadata": {
            "duration": audio_dur_ms / 1000.0,
            "width": 0, "height": 0, "fps": FPS,
            "codec": "unknown", "bitrate": 0
        }
    })
    media_files_to_zip.append((audio_file, audio_rel))
    
    audio_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_id}_audio"))
    items.append({
        "id": audio_item_id, "trackId": "track_audio", "from": 0,
        "durationInFrames": ms_to_frames(audio_dur_ms),
        "label": os.path.basename(audio_file), "type": "audio",
        "mediaRef": audio_media_id,
        "sourceStart": 0, "sourceEnd": audio_dur_ms / 1000.0,
        "sourceDuration": audio_dur_ms / 1000.0, "volume": 1.0,
        "originId": audio_item_id
    })
    
    # 2. Add scene items and subtitles
    for scene in scenes:
        _build_scene_items(project_dir, scene, items, all_keyframes, add_media, global_style=global_style)
        _build_subtitles(project_dir, scene, items, all_keyframes, add_media, font_family=chosen_font)
        
    # 2.1 Add PT-BR subtitles if available (centered in the middle of the screen across the entire video)
    has_ptbr = _build_ptbr_subtitles(project_dir, scenes, items, all_keyframes, font_family="Inter")
        
    # 3. Add scene transitions between consecutive visual items on track_anchor
    transitions_list = []
    anchor_items = [item for item in items if item.get("trackId") == "track_anchor" and item.get("type") in ["video", "image", "lottie"]]
    anchor_items.sort(key=lambda x: x["from"])
    
    import random as prng
    rng = prng.Random(project_id)
    
    presets = [
        "dissolve", "additiveDissolve", "blurDissolve", "wipe", "slide", 
        "glitch", "pixelate", "liquidDistort", "lensWarpZoom", "filmGateSlip"
    ]
    directions = ["from-left", "from-right", "from-top", "from-bottom"]
    
    for i in range(len(anchor_items) - 1):
        left_item = anchor_items[i]
        right_item = anchor_items[i+1]
        
        # Check if either item is a card or Lottie
        left_label = left_item.get("label", "").lower()
        right_label = right_item.get("label", "").lower()
        is_card = "card" in left_label or "card" in right_label or "lottie" in left_label or "lottie" in right_label
        
        # Enable native transitions between all consecutive visual items on track_anchor EXCEPT when cards are involved
        if True:
            if is_card:
                continue # Skip transition, do a clean cut to allow custom entrance keyframe to run!
                
            preset = rng.choice(presets)
            duration_frames = rng.randint(14, 18) # 0.45s to 0.60s at 30 FPS
            
            trans = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_id}_trans_{i}")),
                "leftClipId": left_item["id"],
                "rightClipId": right_item["id"],
                "trackId": "track_anchor",
                "type": "crossfade",
                "durationInFrames": duration_frames,
                "presentation": preset,
                "timing": "linear",
                "alignment": 0.5
            }
            
            if preset in ["wipe", "slide"]:
                trans["direction"] = rng.choice(directions)
                
            transitions_list.append(trans)


    # 4. Add scene-specific adjustment layers (randomly selected 10% to 40% of scenes)
    _build_scene_adjustments(project_id, scenes, items)
        
    # safe_title is already computed at the beginning of the function
    output_zip = os.path.join(project_dir, f"{safe_title}.freecut.zip")
    
    project_json = {
        "id": project_id,
        "name": safe_title,
        "description": "Generated by FreeCut v3 Pipeline",
        "createdAt": int(time.time() * 1000),
        "updatedAt": int(time.time() * 1000),
        "duration": audio_dur_ms / 1000.0,
        "metadata": {
            "width": CANVAS_W, "height": CANVAS_H,
            "fps": FPS, "backgroundColor": "#000000"
        },
        "timeline": {
            "tracks": (
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
                        "volume": 0
                    },
                    {
                        "id": "track_text",
                        "name": "Legenda Original (Russo)",
                        "kind": "video",
                        "height": 100,
                        "locked": False,
                        "visible": True,
                        "muted": False,
                        "solo": False,
                        "order": 1,
                        "syncLock": True,
                        "volume": 0
                    }
                ] + [
                    {**tr, "order": tr["order"] + 1}
                    for tr in TRACKS[1:]
                ]
            ) if has_ptbr else TRACKS,
            "items": items,
            "transitions": transitions_list,
            "keyframes": all_keyframes
        },
        "schemaVersion": 15
    }
    
    manifest = {
        "version": "1.0",
        "createdAt": int(time.time() * 1000),
        "editorVersion": "1.0.0",
        "projectId": project_id,
        "projectName": safe_title,
        "media": manifest_media,
        "checksum": ""
    }
    
    manifest["checksum"] = hashlib.sha256(
        json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    ).hexdigest()
    
    # Write final zip bundle
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write project.json and manifest.json
        zf.writestr("project.json", json.dumps(project_json, indent=2, ensure_ascii=False))
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        
        # Write media files
        for src_path, zip_rel in media_files_to_zip:
            zf.write(src_path, zip_rel)
            
    print(f"  [SUCCESS] Bundle compilado com sucesso em: {output_zip}")
    
    # Compile the freecut_workspace folder directly openable by the editor
    workspace_dir = os.path.join(project_dir, "freecut_workspace")
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir, ignore_errors=True)
        
    projects_dir = os.path.join(workspace_dir, "projects", project_id)
    os.makedirs(projects_dir, exist_ok=True)
    
    with open(os.path.join(workspace_dir, ".freecut-workspace.json"), "w", encoding="utf-8") as f:
        json.dump({"schemaVersion": "2.0", "createdAt": int(time.time() * 1000)}, f, ensure_ascii=False, indent=2)
        
    index = {
        "version": "1.0",
        "updatedAt": int(time.time() * 1000),
        "projects": [{"id": project_id, "name": safe_title, "updatedAt": int(time.time() * 1000)}]
    }
    with open(os.path.join(workspace_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        
    # project.json inside workspace uses mediaId instead of mediaRef
    ws_items = []
    for item in items:
        ws_item = dict(item)
        if "mediaRef" in ws_item:
            ws_item["mediaId"] = ws_item.pop("mediaRef")
        ws_items.append(ws_item)
        
    ws_project = dict(project_json)
    ws_project["timeline"]["items"] = ws_items
    with open(os.path.join(projects_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(ws_project, f, ensure_ascii=False, indent=2)
        
    # Copy media assets into workspace/media/{id}/{fileName}
    for entry in manifest_media:
        media_id = entry["originalId"]
        media_dir_path = os.path.join(workspace_dir, "media", media_id)
        os.makedirs(media_dir_path, exist_ok=True)
        
        # metadata.json
        meta = {
            "id": media_id, "storageType": "workspace",
            "fileName": entry["fileName"], "fileSize": entry["fileSize"],
            "mimeType": entry["mimeType"], "contentHash": entry["sha256"],
            "duration": entry["metadata"]["duration"],
            "width": entry["metadata"]["width"], "height": entry["metadata"]["height"],
            "fps": entry["metadata"]["fps"], "codec": entry["metadata"]["codec"], "bitrate": 0,
            "tags": [], "createdAt": int(time.time() * 1000), "updatedAt": int(time.time() * 1000)
        }
        with open(os.path.join(media_dir_path, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            
        src_file = media_id_to_filepath.get(media_id)
        if src_file and os.path.isfile(src_file):
            shutil.copy2(src_file, os.path.join(media_dir_path, entry["fileName"]))
        else:
            for local_path, rel_path in media_files_to_zip:
                if os.path.basename(local_path) == entry["fileName"]:
                    shutil.copy2(local_path, os.path.join(media_dir_path, entry["fileName"]))
                    break
                
    # media-links.json
    media_links = {
        "version": "1.0",
        "mediaIds": [{"id": entry["originalId"], "addedAt": int(time.time() * 1000)} for entry in manifest_media]
    }
    with open(os.path.join(projects_dir, "media-links.json"), "w", encoding="utf-8") as f:
        json.dump(media_links, f, ensure_ascii=False, indent=2)
        
    print(f"  [OK] Workspace compilado com sucesso em: {workspace_dir}")
    return True

# ── Main Entry Point ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FreeCut v3 Video Automation Tool")
    sub = parser.add_subparsers(dest="command", required=True)
    
    rebuild_cmd = sub.add_parser("rebuild", help="Aplica os novos arquétipos e legendas fatiadas no storyboard.")
    rebuild_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    
    download_cmd = sub.add_parser("download", help="Faz download das mídias das APIs (Pexels/Pixabay) ou scrapers.")
    download_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    
    build_cmd = sub.add_parser("build", help="Processa imagens com Pillow e compila o bundle .freecut.zip")
    build_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    
    run_cmd = sub.add_parser("run-project", help="Executa todo o pipeline de ponta a ponta.")
    run_cmd.add_argument("project_dir", help="Caminho para o diretório do projeto.")
    
    args = parser.parse_args()
    project_dir = os.path.abspath(args.project_dir)
    load_env(project_dir)
    
    if args.command == "rebuild":
        rebuild_storyboard(project_dir)
    elif args.command == "download":
        run_media_downloads(project_dir)
    elif args.command == "build":
        process_images_pipeline(project_dir)
        build_freecut_bundle(project_dir)
    elif args.command == "run-project":
        print(f"=== Iniciando Pipeline Completo (v3) em: {project_dir} ===")
        if not rebuild_storyboard(project_dir):
            sys.exit(1)
        if not run_media_downloads(project_dir):
            sys.exit(1)
        if not process_images_pipeline(project_dir):
            sys.exit(1)
        # Render transparent kinetic titles / cards if configured
        with open(os.path.join(project_dir, "storyboard.json"), "r", encoding="utf-8") as f:
            sb_data = json.load(f)
        with open(os.path.join(project_dir, "words.json"), "r", encoding="utf-8") as f:
            w_data = json.load(f)
        render_hyperframes_subtitles(project_dir, sb_data, w_data)
        if not build_freecut_bundle(project_dir):
            sys.exit(1)
        print("=== Pipeline v3 Finalizado com Sucesso ===")

if __name__ == "__main__":
    main()
