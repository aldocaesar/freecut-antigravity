import subprocess
import time
import requests
import urllib.parse
from typing import List
from ..models import MediaCandidate

class SearXNGSearcher:
    """
    Buscador via meta-engine SearXNG.
    Funciona com instância local (Docker em http://localhost:8080) sem bloqueios ou limites.
    Inclui auto-inicialização do container Docker.
    """
    
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 6):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
    def _ensure_container_started(self):
        """Tenta iniciar o container do SearXNG automaticamente se estiver pausado."""
        if not self._check_http_live():
            try:
                # Tenta dar start no container searxng
                subprocess.run(["docker", "start", "searxng"], capture_output=True, timeout=3)
                time.sleep(1)
            except Exception:
                pass
                
    def _check_http_live(self) -> bool:
        """Verifica rapidamente se a porta HTTP está respondendo."""
        try:
            r = requests.get(f"{self.base_url}/search?q=test&format=json", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False
            
    def is_available(self) -> bool:
        """Verifica se o SearXNG local está pronto para buscas."""
        if self._check_http_live():
            return True
        self._ensure_container_started()
        return self._check_http_live()
            
    def search(self, query: str, limit: int = 15) -> List[MediaCandidate]:
        """Consulta imagens via SearXNG local com múltiplos motores (Google, Bing, DDG, etc.)."""
        candidates = []
        if not self.is_available():
            return candidates
            
        try:
            params = {
                "q": query,
                "categories": "images",
                "format": "json"
            }
            resp = requests.get(f"{self.base_url}/search", params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[:limit]:
                    img_url = item.get("img_src") or item.get("url")
                    if img_url and img_url.startswith("http") and not img_url.lower().endswith(".svg"):
                        res_dict = item.get("resolution") if isinstance(item.get("resolution"), dict) else {}
                        candidates.append(MediaCandidate(
                            url=img_url,
                            thumbnail_url=item.get("thumbnail_src") or img_url,
                            page_url=item.get("url") or "",
                            title=item.get("title") or query,
                            alt=item.get("content") or item.get("title") or "",
                            source=f"searxng ({item.get('engine', 'web')})",
                            media_type="image",
                            width=res_dict.get("width", 0),
                            height=res_dict.get("height", 0)
                        ))
        except Exception:
            pass
        return candidates
