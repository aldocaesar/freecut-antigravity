import os
import time
from typing import Optional, List
from .models import MediaCandidate, SearchResult
from .searchers.aggregator import MediaAggregator
from .validators.metadata_ranker import MetadataRanker
from .validators.ocr_validator import OCRValidator
from .downloader import MediaDownloader
from .cache_manager import CacheManager

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class VisualAssetAgent:
    """Agente central de descoberta, ranking e validação inteligente de mídias."""
    
    def __init__(self, download_dir: str = None, cache_db: str = None):
        self.download_dir = download_dir or os.path.join(BASE_DIR, "data", "downloads")
        self.aggregator = MediaAggregator()
        self.ranker = MetadataRanker()
        self.ocr = OCRValidator()
        self.downloader = MediaDownloader(self.download_dir)
        self.cache = CacheManager(cache_db)
        
    def find_best_media(
        self,
        query: str,
        context: str = "",
        media_type: str = "image",
        strict: bool = True,
        use_cache: bool = True,
        use_ocr: bool = True,
        exclude_urls: Optional[set] = None,
        mode: str = "default",
        universe: Optional[str] = None,
    ) -> SearchResult:
        start_time = time.time()
        exclude_set = exclude_urls or set()
        
        # No modo POP, força estritamente apenas imagens (zero vídeos)
        if mode.lower() == "pop":
            media_type = "image"
            
        q_clean = (query or "").strip()
        u_clean = (universe or "").strip()
        
        # Effective query computation for ranking, cache and downloads
        effective_query = q_clean
        if u_clean:
            if not effective_query:
                effective_query = u_clean
            elif u_clean.lower() not in effective_query.lower():
                effective_query = f"{u_clean} {effective_query}".strip()
                
        cache_key = effective_query if mode.lower() == "pop" else query
        
        # 1. Verificar Cache (se não estiver na lista de exclusão)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached and cached.url not in exclude_set:
                return SearchResult(
                    query=query,
                    candidates=[cached],
                    winner=cached,
                    execution_time_s=time.time() - start_time,
                    status="cached",
                    message="Mídia recuperada do cache local"
                )
                
        # 2. Descoberta Multi-Fonte com suporte a Modo POP e Universo
        raw_candidates = self.aggregator.aggregate(
            query=query,
            media_type=media_type,
            mode=mode,
            universe=universe,
            limit=45
        )
        if not raw_candidates:
            return SearchResult(
                query=query,
                candidates=[],
                winner=None,
                execution_time_s=time.time() - start_time,
                status="error",
                message=f"Nenhum candidato encontrado para a busca '{query}'"
            )
            
        # 3. Classificação por Metadados (Filtro Rápido)
        ranking_query = effective_query if mode.lower() == "pop" else query
        ranked_candidates = self.ranker.rank_all(raw_candidates, ranking_query, context=context, strict=strict)
        
        # 4. Processamento dos Melhores Candidatos (Top 8 não-duplicados)
        eligible_candidates = [c for c in ranked_candidates if c.url not in exclude_set][:8]
        winner = None
        
        for cand in eligible_candidates:
            # Baixa para validação física
            prefix = ranking_query.replace(" ", "_")[:20]
            success, local_path, msg = self.downloader.download(cand, prefix=prefix)
            if not success:
                cand.reasons.append(f"Falha no download: {msg}")
                continue
                
            # 5. Validação por OCR (se aplicável para imagens)
            if use_ocr and self.ocr.is_available() and cand.media_type == "image":
                score_adj, ocr_reasons, detected_text = self.ocr.validate_image_ocr(local_path, ranking_query)
                cand.score += score_adj
                cand.ocr_text = detected_text
                cand.reasons.extend(ocr_reasons)
                
            winner = cand
            break  # Primeiro candidato baixado e validado com sucesso
            
        if winner:
            if use_cache:
                self.cache.set(cache_key, winner)
            return SearchResult(
                query=query,
                candidates=ranked_candidates,
                winner=winner,
                execution_time_s=time.time() - start_time,
                status="success",
                message="Melhor mídia encontrada e validada"
            )
        else:
            return SearchResult(
                query=query,
                candidates=ranked_candidates,
                winner=None,
                execution_time_s=time.time() - start_time,
                status="error",
                message="Falha ao baixar os principais candidatos"
            )
