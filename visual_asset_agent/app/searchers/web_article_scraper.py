import re
import urllib.parse
from typing import List, Set
from bs4 import BeautifulSoup
import requests
from ..models import MediaCandidate

class WebArticleImageScraper:
    """
    Buscador profundo que localiza artigos e notícias reais (via Google News RSS, Wikipedia e portais),
    acessa as páginas e extrai as fotos do corpo da matéria com atributos alt, figcaption e og:image.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    IGNORED_SUBSTRINGS = [
        "logo", "icon", "avatar", "badge", "tracker", "pixel", "banner_ad", 
        "facebook", "twitter", "instagram", "share", "button", "spinner", "placeholder", "loading",
        "author", "user", "comment", "sidebar", "ad-", "ads/", "thumb_default"
    ]
    
    def __init__(self, timeout: int = 7):
        self.timeout = timeout
        
    def _search_news_articles(self, query: str, limit: int = 4) -> List[dict]:
        """Consulta o Google News RSS (100% público, sem bloqueios de CAPTCHA)."""
        articles = []
        try:
            # Busca em português do Brasil e fallback internacional
            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            resp = requests.get(rss_url, headers=self.HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "xml")
                for item in soup.find_all("item")[:limit]:
                    articles.append({
                        "title": item.title.text if item.title else "",
                        "link": item.link.text if item.link else "",
                        "source": item.source.text if item.source else "News"
                    })
        except Exception:
            pass
            
        # Se não encontrou em PT, tenta em inglês
        if not articles:
            try:
                rss_url_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
                resp_en = requests.get(rss_url_en, headers=self.HEADERS, timeout=self.timeout)
                if resp_en.status_code == 200:
                    soup = BeautifulSoup(resp_en.text, "xml")
                    for item in soup.find_all("item")[:limit]:
                        articles.append({
                            "title": item.title.text if item.title else "",
                            "link": item.link.text if item.link else "",
                            "source": item.source.text if item.source else "News"
                        })
            except Exception:
                pass
                
        return articles
        
    def extract_images_from_url(self, page_url: str, article_title: str = "") -> List[MediaCandidate]:
        """Acessa a matéria jornalística e extrai fotos com alt e legendas."""
        candidates = []
        try:
            resp = requests.get(page_url, headers=self.HEADERS, timeout=self.timeout, allow_redirects=True)
            if resp.status_code != 200:
                return candidates
                
            real_url = resp.url
            soup = BeautifulSoup(resp.text, "html.parser")
            doc_title = article_title or (soup.title.string.strip() if soup.title and soup.title.string else "")
            
            # 1. Foto de Capa Editorial (og:image / twitter:image)
            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_img and og_img.get("content"):
                og_url = og_img["content"]
                if og_url.startswith("//"):
                    og_url = "https:" + og_url
                elif og_url.startswith("/"):
                    og_url = urllib.parse.urljoin(real_url, og_url)
                    
                if og_url.startswith("http") and not any(ign in og_url.lower() for ign in self.IGNORED_SUBSTRINGS):
                    candidates.append(MediaCandidate(
                        url=og_url,
                        thumbnail_url=og_url,
                        page_url=real_url,
                        title=f"{doc_title} (Foto Principal da Notícia)",
                        alt=doc_title,
                        caption=f"Foto oficial de capa: {doc_title}",
                        source="jornal_artigo (og:image)",
                        media_type="image"
                    ))
                    
            # 2. Varrer fotos no corpo do texto com alt ou legenda
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy-src")
                if not src:
                    srcset = img.get("srcset") or img.get("data-srcset")
                    if srcset:
                        parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
                        if parts:
                            src = parts[-1]
                            
                if not src:
                    continue
                    
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urllib.parse.urljoin(real_url, src)
                    
                if not src.startswith("http"):
                    continue
                    
                src_lower = src.lower()
                if any(ignored in src_lower for ignored in self.IGNORED_SUBSTRINGS):
                    continue
                    
                alt_text = (img.get("alt") or "").strip()
                
                # Procura legenda de <figcaption>
                caption_text = ""
                parent = img.find_parent("figure")
                if parent:
                    figcaption = parent.find("figcaption")
                    if figcaption:
                        caption_text = figcaption.get_text(strip=True)
                        
                if len(alt_text) > 4 or len(caption_text) > 4:
                    combined_title = alt_text or caption_text or doc_title
                    candidates.append(MediaCandidate(
                        url=src,
                        thumbnail_url=src,
                        page_url=real_url,
                        title=combined_title,
                        alt=alt_text,
                        caption=caption_text or f"Notícia: {doc_title}",
                        source="jornal_artigo",
                        media_type="image"
                    ))
        except Exception:
            pass
        return candidates
        
    def search(self, query: str, limit_articles: int = 3, max_candidates: int = 15) -> List[MediaCandidate]:
        """Localiza notícias sobre a query e extrai todas as fotos jornalísticas com alt e metadados."""
        articles = self._search_news_articles(query, limit=limit_articles)
        all_candidates = []
        seen_urls: Set[str] = set()
        
        for art in articles:
            link = art["link"]
            title = art["title"]
            cands = self.extract_images_from_url(link, article_title=title)
            for c in cands:
                if c.url not in seen_urls:
                    seen_urls.add(c.url)
                    all_candidates.append(c)
                    if len(all_candidates) >= max_candidates:
                        return all_candidates
                        
        return all_candidates
