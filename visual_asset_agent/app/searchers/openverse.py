import urllib.parse
import requests
from typing import List
from ..models import MediaCandidate

class OpenverseSearcher:
    """Buscador oficial no Openverse (mais de 700 milhões de fotos livres e de alta qualidade)."""
    
    API_URL = "https://api.openverse.org/v1/images/"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "VisualAssetAgent/1.0 (freecut video automation pipeline)"
        }
        
    def search(self, query: str, limit: int = 15) -> List[MediaCandidate]:
        candidates = []
        try:
            params = {
                "q": query,
                "page_size": str(limit),
                "license_type": "commercial,modification"
            }
            resp = requests.get(self.API_URL, params=params, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return candidates
                
            data = resp.json()
            results = data.get("results", [])
            
            for item in results:
                url = item.get("url")
                thumb_url = item.get("thumbnail", url)
                title = item.get("title", "")
                width = item.get("width", 0)
                height = item.get("height", 0)
                source_domain = item.get("source", "openverse")
                
                # Coleta tags como legendas
                tags = [t.get("name", "") for t in item.get("tags", []) if t.get("name")]
                caption = ", ".join(tags[:5])
                
                if url:
                    candidates.append(MediaCandidate(
                        url=url,
                        thumbnail_url=thumb_url,
                        page_url=item.get("foreign_landing_url", ""),
                        title=title,
                        alt=title,
                        caption=caption,
                        source=f"openverse ({source_domain})",
                        media_type="image",
                        width=width,
                        height=height
                    ))
        except Exception:
            pass
            
        return candidates
