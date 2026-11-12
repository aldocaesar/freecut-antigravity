import os
import requests
from typing import List
from ..models import MediaCandidate

class StockSearcher:
    """Busca em APIs oficiais de bancos de imagens e vídeos (Pexels e Pixabay)."""
    
    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.pexels_key = os.environ.get("PEXELS_API_KEY", "")
        self.pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
        
    def search_pexels_videos(self, query: str, limit: int = 10) -> List[MediaCandidate]:
        candidates = []
        if not self.pexels_key:
            return candidates
        try:
            headers = {"Authorization": self.pexels_key}
            url = f"https://api.pexels.com/videos/search?query={query}&per_page={limit}&orientation=landscape"
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for video in data.get("videos", []):
                    # Seleciona melhor arquivo HD/1080p
                    video_files = video.get("video_files", [])
                    best_file = None
                    for vf in video_files:
                        if vf.get("width") == 1920 or vf.get("height") == 1080:
                            best_file = vf
                            break
                    if not best_file and video_files:
                        best_file = video_files[0]
                    if best_file:
                        candidates.append(MediaCandidate(
                            url=best_file.get("link"),
                            thumbnail_url=video.get("image", ""),
                            page_url=video.get("url", ""),
                            title=f"Pexels Video {query}",
                            source="pexels",
                            media_type="video",
                            width=best_file.get("width", 1920),
                            height=best_file.get("height", 1080)
                        ))
        except Exception:
            pass
        return candidates

    def search_pixabay_videos(self, query: str, limit: int = 12) -> List[MediaCandidate]:
        candidates = []
        if not self.pixabay_key:
            return candidates
        try:
            url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={query}&per_page={limit}&safesearch=true"
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", []):
                    videos = hit.get("videos", {})
                    best = videos.get("large") or videos.get("medium") or videos.get("small")
                    if best and best.get("url"):
                        candidates.append(MediaCandidate(
                            url=best["url"],
                            thumbnail_url=best.get("thumbnail", ""),
                            page_url=hit.get("pageURL", ""),
                            title=hit.get("tags", f"Pixabay Video {query}"),
                            alt=hit.get("tags", ""),
                            caption=hit.get("tags", ""),
                            source="pixabay",
                            media_type="video",
                            width=best.get("width", 1920),
                            height=best.get("height", 1080),
                        ))
        except Exception:
            pass
        return candidates
        
    def search_pixabay_images(self, query: str, limit: int = 15) -> List[MediaCandidate]:
        candidates = []
        if not self.pixabay_key:
            return candidates
        try:
            url = f"https://pixabay.com/api/?key={self.pixabay_key}&q={query}&image_type=photo&orientation=horizontal&per_page={limit}&safesearch=true"
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", []):
                    img_url = hit.get("largeImageURL", hit.get("webformatURL", ""))
                    if img_url:
                        candidates.append(MediaCandidate(
                            url=img_url,
                            thumbnail_url=hit.get("previewURL", img_url),
                            page_url=hit.get("pageURL", ""),
                            title=hit.get("tags", f"Pixabay {query}"),
                            alt=hit.get("tags", ""),
                            caption=hit.get("tags", ""),
                            source="pixabay",
                            media_type="image",
                            width=hit.get("imageWidth", 1920),
                            height=hit.get("imageHeight", 1080)
                        ))
        except Exception:
            pass
        return candidates
