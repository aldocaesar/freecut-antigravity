from typing import List, Optional
from ..models import MediaCandidate
from .wikimedia import WikimediaSearcher
from .duckduckgo import DuckDuckGoSearcher
from .searxng import SearXNGSearcher
from .openverse import OpenverseSearcher
from .pexels_pixabay import StockSearcher
from .yandex import YandexSearcher
from .web_article_scraper import WebArticleImageScraper
from .tmdb import TMDBSearcher

class MediaAggregator:
    """Agrega candidatos de múltiplas fontes (TMDB, DuckDuckGo, Yandex, Wikimedia, SearXNG, Openverse, Stock, Notícias)."""
    
    ANIME_INDICATORS = (
        "anime", "manga", "one piece", "naruto", "dragon ball", "dragonball",
        "bleach", "attack on titan", "shingeki", "jujutsu", "demon slayer",
        "kimetsu", "hunter x hunter", "death note", "fullmetal", "my hero academia",
        "boku no hero", "chainsaw man", "solo leveling", "evangelion",
        "sword art online", "tokyo ghoul", "pokemon", "pokémon", "studio ghibli",
        "ghibli", "boruto", "vinland", "jojo", "berserk", "black clover",
        "haikyuu", "frieren", "cyberpunk edgerunners", "spy x family",
        "one punch man", "cowboy bebop", "sailor moon", "mob psycho",
        "steins gate", "code geass", "fairy tail", "yu-gi-oh", "yugioh",
        "inuyasha", "overlord", "blue lock", "kaiju no 8", "dandadan",
        "sousou no frieren", "mashle", "luffy", "zoro", "goku", "vegeta",
        "sasuke", "gojo", "sukuna", "eren", "levi", "tanjiro", "nezuko"
    )
    
    def __init__(self):
        self.news_scraper = WebArticleImageScraper()
        self.wikimedia = WikimediaSearcher()
        self.duckduckgo = DuckDuckGoSearcher()
        self.searxng = SearXNGSearcher()
        self.openverse = OpenverseSearcher()
        self.stock = StockSearcher()
        self.yandex = YandexSearcher()
        self.tmdb = TMDBSearcher()
        
    def _is_anime(self, text: str) -> bool:
        if not text:
            return False
        norm = text.lower()
        return any(kw in norm for kw in self.ANIME_INDICATORS)
        
    def aggregate(
        self,
        query: str,
        media_type: str = "image",
        mode: str = "default",
        universe: Optional[str] = None,
        limit: int = 45
    ) -> List[MediaCandidate]:
        candidates: List[MediaCandidate] = []
        seen_urls = set()
        
        q_clean = (query or "").strip()
        u_clean = (universe or "").strip()
        
        # Injeção de contexto do universo se especificado e ainda não presente na query
        effective_query = q_clean
        if u_clean:
            if not effective_query:
                effective_query = u_clean
            elif u_clean.lower() not in effective_query.lower():
                effective_query = f"{u_clean} {effective_query}".strip()
                
        if not effective_query:
            return candidates
            
        # ── MODO POP (Séries, Filmes e Animes) ──────────────────────────
        if mode.lower() == "pop":
            # 1. Força estritamente apenas imagens (zero vídeos)
            media_type = "image"
            
            # 2. 100% BLOQUEIA bancos de stock genéricos (Pexels, Pixabay) e Openverse
            is_anime_target = self._is_anime(f"{effective_query} {u_clean}")
            
            if is_anime_target:
                # Roteamento Inteligente Anime: DuckDuckGo (com framing) -> TMDB -> Yandex -> Wikimedia
                # A. DuckDuckGo com termos de enquadramento (HD stills / screenshots)
                for cand in self.duckduckgo.search(effective_query, limit=15, framing=True):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # B. TMDB (para animes catalogados oficialmente com stills de episódios/backdrops)
                for cand in self.tmdb.search(effective_query, universe=universe, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # C. Yandex (cobertura web ampla)
                for cand in self.yandex.search(effective_query, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # D. Wikimedia Commons
                for cand in self.wikimedia.search(effective_query, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
            else:
                # Roteamento Inteligente Filmes / Séries: TMDB -> DuckDuckGo -> Yandex -> Wikimedia
                # A. TMDB (stills oficiais de episódios e backdrops originais 4K/Full HD)
                for cand in self.tmdb.search(effective_query, universe=universe, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # B. DuckDuckGo com framing
                for cand in self.duckduckgo.search(effective_query, limit=15, framing=True):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # C. Yandex
                for cand in self.yandex.search(effective_query, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
                # D. Wikimedia Commons
                for cand in self.wikimedia.search(effective_query, limit=15):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                        
            return candidates[:limit]
            
        # ── MODO DEFAULT (Geral / Notícias / Stock) ─────────────────────
        # 1. Se for vídeo genérico, busca em bancos de stock primeiro (Pexels + Pixabay)
        if media_type == "video":
            for cand in self.stock.search_pexels_videos(effective_query, limit=10):
                if cand.url not in seen_urls:
                    seen_urls.add(cand.url)
                    candidates.append(cand)
            for cand in self.stock.search_pixabay_videos(effective_query, limit=12):
                if cand.url not in seen_urls:
                    seen_urls.add(cand.url)
                    candidates.append(cand)
            return candidates
            
        # 2. Imagens: Pixabay API oficial entra cedo (evita ser cortado pelo limit=45) + fontes específicas
        for cand in self.stock.search_pixabay_images(effective_query, limit=10):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)

        # Fonte A: Yandex (ótimo alcance web para produtos, objetos comerciais e contexto amplo)
        for cand in self.yandex.search(effective_query, limit=15):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)
                
        # Fonte B: SearXNG (se ativo localmente no Docker)
        if self.searxng.is_available():
            for cand in self.searxng.search(effective_query, limit=15):
                if cand.url not in seen_urls:
                    seen_urls.add(cand.url)
                    candidates.append(cand)
                    
        # Fonte C: Matérias e Notícias da Web (extração de og:image, alt e figcaption)
        for cand in self.news_scraper.search(effective_query, limit_articles=3, max_candidates=10):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)
                
        # Fonte D: Wikimedia Commons (alta precisão para entidades e personalidades)
        for cand in self.wikimedia.search(effective_query, limit=15):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)
                
        # Fonte E: TMDB (se API key configurada)
        if self.tmdb.api_key:
            for cand in self.tmdb.search(effective_query, universe=universe, limit=10):
                if cand.url not in seen_urls:
                    seen_urls.add(cand.url)
                    candidates.append(cand)
                    
        # Fonte F: Openverse (banco aberto com mais de 700 milhões de fotos com tags)
        for cand in self.openverse.search(effective_query, limit=12):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)
                
        # Fonte G: DuckDuckGo (amplo alcance web com metadados)
        for cand in self.duckduckgo.search(effective_query, limit=12):
            if cand.url not in seen_urls:
                seen_urls.add(cand.url)
                candidates.append(cand)
                    
        return candidates[:limit]
