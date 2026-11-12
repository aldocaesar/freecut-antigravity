import os
import re
import urllib.parse
import requests
from typing import List
from ..models import MediaCandidate

class YandexSearcher:
    """Scraper do Yandex Imagens para mídias nacionais e figuras públicas."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
    def search(self, query: str, limit: int = 15) -> List[MediaCandidate]:
        candidates = []
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://yandex.com/images/search?text={encoded_query}"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return candidates
                
            html = resp.text
            
            # Extrair blocos de dados de imagem com regex
            pattern = re.compile(r'&quot;img_href&quot;:&quot;(https?://[^&]+)&quot;')
            matches = pattern.findall(html)
            
            # Extrair descrições/títulos das imagens se disponíveis
            title_pattern = re.compile(r'&quot;description&quot;:&quot;([^&]+)&quot;')
            titles = title_pattern.findall(html)
            
            for idx, img_url in enumerate(matches[:limit]):
                img_url_clean = urllib.parse.unquote(img_url.replace(r'\/', '/'))
                # Usa a descrição real do Yandex se houver, ou extrai do slug da URL
                raw_title = titles[idx] if idx < len(titles) else ""
                if not raw_title:
                    slug = os.path.basename(urllib.parse.urlparse(img_url_clean).path)
                    raw_title = os.path.splitext(slug)[0].replace("-", " ").replace("_", " ")
                
                candidates.append(MediaCandidate(
                    url=img_url_clean,
                    thumbnail_url=img_url_clean,
                    title=raw_title,
                    alt=raw_title,
                    caption=raw_title,
                    source="yandex",
                    media_type="image",
                    width=0,
                    height=0
                ))
        except Exception:
            pass
        return candidates
