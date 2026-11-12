import os
import re
import requests
from typing import List, Optional, Dict, Any, Tuple
from ..models import MediaCandidate

class TMDBSearcher:
    """
    Buscador oficial do The Movie Database (TMDB) para filmes, séries e animes.
    Suporta autenticação dupla (v3 API key via query param ou v4 Bearer Token),
    descoberta de backdrops originais e stills de episódios de TV em Full HD/4K.
    """
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_ORIGINAL = "https://image.tmdb.org/t/p/original"
    IMAGE_BASE_THUMB = "https://image.tmdb.org/t/p/w780"
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 8):
        self._explicit_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
    @property
    def api_key(self) -> str:
        if self._explicit_key is not None:
            return self._explicit_key.strip()
        return os.environ.get("TMDB_API_KEY", "").strip()
        
    def _get_auth(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        headers = {
            "User-Agent": "VisualAssetAgent/1.0 (freecut video automation pipeline)",
            "Accept": "application/json"
        }
        params: Dict[str, str] = {}
        key = self.api_key
        if not key:
            return params, headers
            
        # Suporte duplo: Bearer Token (v4 Read Access Token) ou API Key (v3)
        if key.startswith("ey") or len(key) > 40:
            headers["Authorization"] = f"Bearer {key}"
        else:
            params["api_key"] = key
        return params, headers
        
    def _request(self, endpoint: str, extra_params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
            
        params, headers = self._get_auth()
        if extra_params:
            params.update(extra_params)
            
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None
            
    def _extract_season_number(self, text: str) -> int:
        """Extrai número de temporada da query (ex: 'House of the Dragon Season 2', 's02', 'temporada 3'). Default: 1."""
        if not text:
            return 1
        m = re.search(r'(?:season|temporada|s)\s*(\d+)', text, re.IGNORECASE)
        if m:
            try:
                s_num = int(m.group(1))
                return s_num if s_num > 0 else 1
            except ValueError:
                pass
        return 1

    def search(self, query: str, universe: Optional[str] = None, limit: int = 15) -> List[MediaCandidate]:
        """
        Busca backdrops e stills de séries/filmes no TMDB.
        Retorna lista de MediaCandidate em resolução Full HD/4K (original).
        Fallback gracioso retornando lista vazia se API key ausente ou 0 resultados.
        """
        candidates: List[MediaCandidate] = []
        if not self.api_key:
            return candidates
            
        search_query = (query or "").strip()
        if not search_query and universe:
            search_query = universe.strip()
            
        if not search_query:
            return candidates
            
        seen_urls = set()
        
        try:
            # 1. Multi-Search inicial
            data = self._request("/search/multi", {
                "query": search_query,
                "include_adult": "false",
                "language": "en-US"
            })
            
            results = data.get("results", []) if data else []
            
            # Fallback para universe se query específica não retornou nada
            if not results and universe and universe.strip().lower() != search_query.lower():
                data = self._request("/search/multi", {
                    "query": universe.strip(),
                    "include_adult": "false",
                    "language": "en-US"
                })
                results = data.get("results", []) if data else []
                
            # Fallback direto para /search/tv ou /search/movie se multi-search falhar
            if not results:
                tv_data = self._request("/search/tv", {"query": search_query, "include_adult": "false", "language": "en-US"})
                if tv_data and tv_data.get("results"):
                    results = [{"media_type": "tv", **r} for r in tv_data.get("results", [])]
                else:
                    movie_data = self._request("/search/movie", {"query": search_query, "include_adult": "false", "language": "en-US"})
                    if movie_data and movie_data.get("results"):
                        results = [{"media_type": "movie", **r} for r in movie_data.get("results", [])]
                        
            if not results:
                return candidates
                
            season_num = self._extract_season_number(f"{search_query} {universe or ''}")
            
            # Processa as melhores entidades encontradas (top 3)
            for entity in results[:3]:
                media_type = entity.get("media_type", "")
                if media_type not in ("movie", "tv"):
                    if "first_air_date" in entity or "name" in entity:
                        media_type = "tv"
                    elif "release_date" in entity or "title" in entity:
                        media_type = "movie"
                    else:
                        continue
                        
                entity_id = entity.get("id")
                if not entity_id:
                    continue
                    
                entity_title = (
                    entity.get("title") or 
                    entity.get("name") or 
                    entity.get("original_title") or 
                    entity.get("original_name") or 
                    search_query
                )
                overview = entity.get("overview", "")
                
                # A. Backdrop direto da entidade
                direct_backdrop = entity.get("backdrop_path")
                if direct_backdrop:
                    file_clean = direct_backdrop.lstrip('/')
                    orig_url = f"{self.IMAGE_BASE_ORIGINAL}/{file_clean}"
                    if orig_url not in seen_urls:
                        seen_urls.add(orig_url)
                        candidates.append(MediaCandidate(
                            url=orig_url,
                            thumbnail_url=f"{self.IMAGE_BASE_THUMB}/{file_clean}",
                            page_url=f"https://www.themoviedb.org/{media_type}/{entity_id}",
                            title=f"{entity_title} (Backdrop)",
                            alt=f"{entity_title} official TMDB backdrop",
                            caption=overview[:150] if overview else f"{entity_title} official backdrop",
                            source=f"tmdb ({media_type})",
                            media_type="image",
                            width=1920,
                            height=1080,
                            metadata={
                                "tmdb_id": entity_id,
                                "media_type": media_type,
                                "vote_average": entity.get("vote_average", 0.0),
                                "type": "backdrop"
                            }
                        ))
                        
                # B. Galeria de Backdrops em alta resolução (/images)
                img_data = self._request(f"/{media_type}/{entity_id}/images", {
                    "include_image_language": "en,null,pt"
                })
                if img_data:
                    backdrops = img_data.get("backdrops", [])
                    for b in backdrops:
                        file_path = b.get("file_path")
                        if not file_path:
                            continue
                        file_clean = file_path.lstrip('/')
                        orig_url = f"{self.IMAGE_BASE_ORIGINAL}/{file_clean}"
                        if orig_url in seen_urls:
                            continue
                        seen_urls.add(orig_url)
                        
                        w = b.get("width", 1920) or 1920
                        h = b.get("height", 1080) or 1080
                        
                        candidates.append(MediaCandidate(
                            url=orig_url,
                            thumbnail_url=f"{self.IMAGE_BASE_THUMB}/{file_clean}",
                            page_url=f"https://www.themoviedb.org/{media_type}/{entity_id}",
                            title=f"{entity_title} Backdrop",
                            alt=f"{entity_title} official TMDB backdrop",
                            caption=overview[:150] if overview else f"{entity_title} backdrop",
                            source=f"tmdb ({media_type})",
                            media_type="image",
                            width=w,
                            height=h,
                            metadata={
                                "tmdb_id": entity_id,
                                "media_type": media_type,
                                "vote_average": b.get("vote_average", 0.0),
                                "aspect_ratio": b.get("aspect_ratio", 1.778),
                                "type": "backdrop"
                            }
                        ))
                        if len(candidates) >= limit:
                            break
                            
                # C. Stills de Episódios para Séries de TV (/tv/{id}/season/{season_number})
                if media_type == "tv" and len(candidates) < limit:
                    season_data = self._request(f"/tv/{entity_id}/season/{season_num}", {"language": "en-US"})
                    if (not season_data or not season_data.get("episodes")) and season_num != 1:
                        # Fallback para Season 1
                        season_num = 1
                        season_data = self._request(f"/tv/{entity_id}/season/1", {"language": "en-US"})
                        
                    if season_data and season_data.get("episodes"):
                        for ep in season_data.get("episodes", []):
                            still_path = ep.get("still_path")
                            if not still_path:
                                continue
                            file_clean = still_path.lstrip('/')
                            orig_url = f"{self.IMAGE_BASE_ORIGINAL}/{file_clean}"
                            if orig_url in seen_urls:
                                continue
                            seen_urls.add(orig_url)
                            
                            ep_num = ep.get("episode_number", 0)
                            ep_name = ep.get("name", "")
                            ep_overview = ep.get("overview", "")
                            ep_vote = ep.get("vote_average", 0.0)
                            
                            title_str = (
                                f"{entity_title} S{season_num:02d}E{ep_num:02d} - {ep_name}"
                                if ep_name else f"{entity_title} S{season_num:02d}E{ep_num:02d}"
                            )
                            
                            candidates.append(MediaCandidate(
                                url=orig_url,
                                thumbnail_url=f"{self.IMAGE_BASE_THUMB}/{file_clean}",
                                page_url=f"https://www.themoviedb.org/tv/{entity_id}/season/{season_num}/episode/{ep_num}",
                                title=title_str,
                                alt=f"{entity_title} S{season_num:02d}E{ep_num:02d} official still",
                                caption=ep_overview[:150] if ep_overview else f"{entity_title} season {season_num} episode {ep_num}",
                                source="tmdb (tv_still)",
                                media_type="image",
                                width=1920,
                                height=1080,
                                metadata={
                                    "tmdb_id": entity_id,
                                    "season": season_num,
                                    "episode": ep_num,
                                    "episode_id": ep.get("id"),
                                    "vote_average": ep_vote,
                                    "type": "still"
                                }
                            ))
                            if len(candidates) >= limit:
                                break
                                
                if len(candidates) >= limit:
                    break
                    
        except Exception:
            # Fallback gracioso garantido sem exceções não tratadas
            pass
            
        return candidates[:limit]
