import urllib.parse
import requests
from typing import List
from ..models import MediaCandidate

class WikimediaSearcher:
    """Busca imagens de alta resolução na Wikimedia Commons (ideal para figuras públicas, marcas históricas, aviões, carros)."""
    
    API_URL = "https://commons.wikimedia.org/w/api.php"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "VisualAssetAgent/1.0 (freecut video automation pipeline)"
        }
        
    def search(self, query: str, limit: int = 15) -> List[MediaCandidate]:
        candidates = []
        try:
            params = {
                "action": "query",
                "generator": "search",
                "gsrnamespace": "6",  # 6 = File namespace
                "gsrsearch": query,
                "gsrlimit": str(limit),
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata|mime",
                "format": "json"
            }
            
            resp = requests.get(self.API_URL, params=params, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return candidates
                
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            
            for page_id, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if not imageinfo:
                    continue
                info = imageinfo[0]
                mime = info.get("mime", "")
                if not mime.startswith("image/"):
                    continue
                    
                url = info.get("url")
                thumb_url = info.get("thumburl", url)
                width = info.get("width", 0)
                height = info.get("height", 0)
                title = page.get("title", "").replace("File:", "")
                
                # Extrair descrição de metadados
                extmetadata = info.get("extmetadata", {})
                caption = ""
                if "ImageDescription" in extmetadata:
                    caption = extmetadata["ImageDescription"].get("value", "")
                elif "ObjectName" in extmetadata:
                    caption = extmetadata["ObjectName"].get("value", "")
                
                # Remove tags HTML simples
                if caption:
                    import re
                    caption = re.sub(r"<[^>]+>", "", caption).strip()
                
                if url:
                    candidates.append(MediaCandidate(
                        url=url,
                        thumbnail_url=thumb_url,
                        page_url=info.get("descriptionurl", ""),
                        title=title,
                        alt=title,
                        caption=caption,
                        source="wikimedia",
                        media_type="image",
                        width=width,
                        height=height,
                        metadata={
                            "categories": extmetadata.get("Categories", {}).get("value", ""),
                            "date": extmetadata.get("DateTimeOriginal", {}).get("value", "")
                        }
                    ))
        except Exception as e:
            # Falha silenciosa com fallback
            pass
            
        return candidates
