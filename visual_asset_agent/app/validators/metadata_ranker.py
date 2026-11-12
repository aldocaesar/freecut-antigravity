import re
from typing import List, Tuple
from ..models import MediaCandidate

class MetadataRanker:
    """Classificador cirúrgico de candidatos baseado em metadados textuais e contexto."""
    
    # Palavras funcionais que NÃO devem ser consideradas entidades isoladas
    STOPWORDS = {
        "can", "in", "on", "at", "for", "with", "the", "a", "an", "by", "from", "to", "and", "or", "of", "is", "it", "this", "that",
        "tornaram", "eram", "foram", "havia", "ficou", "quando", "sendo", "sao", "como", "mais", "muito", "sobre", "entre", "seus", "suas", "pelo", "pela"
    }
    
    # Palavras que geram penalidade pesada se a busca for estrita por modelo/entidade
    CONFLICT_MAP = {
        "f40": ["f50", "enzo", "laferrari", "testarossa", "488", "458", "f355", "360", "f8", "sf90"],
        "f50": ["f40", "enzo", "laferrari", "testarossa", "488", "458"],
        "737": ["747", "777", "787", "a320", "a380", "a350", "a330"],
        "a320": ["a380", "a350", "737", "777", "787", "747"],
        "iphone 15": ["iphone 14", "iphone 13", "iphone 12", "iphone 11", "iphone x"],
        "1990s": ["2020", "2021", "2022", "2023", "2024", "2025", "2026", "2019", "2018"],
        "anos 90": ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    }
    
    # Termos de sucatas, fragmentos ou adereços têxteis que não devem ser confundidos com o veículo/máquina real
    VEHICLE_KEYWORDS = {"tank", "aircraft", "plane", "fighter", "bomber", "car", "supercar", "ship", "vessel", "cannon", "gun", "engine", "locomotive"}
    ARTIFACT_NOISE_TERMS = {"patch", "badge", "insignia", "stamp", "coin", "scrap", "fragment", "debris", "ruins", "scale model", "toy model"}
    
    def __init__(self):
        pass
        
    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r'[^a-z0-9\s]', ' ', text.lower()).strip()
        
    def rank_candidate(self, candidate: MediaCandidate, query: str, context: str = "", strict: bool = True) -> Tuple[float, List[str]]:
        score = 40.0  # Base score
        reasons = []
        
        norm_query = self._normalize(query)
        # Extrai palavras significativas da query (exclui stopwords)
        query_words = [w for w in norm_query.split() if len(w) > 1 and w not in self.STOPWORDS]
        
        norm_title = self._normalize(candidate.title)
        norm_url = self._normalize(candidate.url)
        combined_text = f"{candidate.title} {candidate.alt} {candidate.caption} {candidate.page_url} {candidate.url}"
        norm_combined = self._normalize(combined_text)
        
        # 1. REGRA DE OURO: O Título/Nome do Arquivo DEVE conter as palavras-chave principais
        # Se for entidade estrita (ex: "coca-cola", "ferrari"), deve constar no título ou URL slug
        primary_entity_words = [w for w in query_words if len(w) > 2][:2]
        title_url_combined = f"{norm_title} {norm_url}"
        
        has_primary_in_title = any(w in title_url_combined for w in primary_entity_words)
        
        if not has_primary_in_title and strict and primary_entity_words:
            score -= 60.0
            reasons.append(f"REJEIÇÃO: Assunto principal '{' '.join(primary_entity_words)}' NÃO consta no título nem no arquivo ({candidate.title[:40]}) (-60)")
        elif has_primary_in_title:
            score += 25.0
            reasons.append(f"Assunto principal presente no título/arquivo (+25)")
            
        # 2. Correspondência exata da query inteira
        if norm_query in norm_combined:
            score += 30.0
            reasons.append(f"Correspondência exata da query '{query}' nos metadados (+30)")
        else:
            # 3. Contagem de palavras da query presentes
            matched_words = [w for w in query_words if w in norm_combined]
            match_ratio = len(matched_words) / max(len(query_words), 1)
            score_bonus = match_ratio * 20.0
            score += score_bonus
            if matched_words:
                reasons.append(f"Palavras da query encontradas: {', '.join(matched_words)} (+{score_bonus:.1f})")
                
        # 4. Análise de Conflitos Específicos (ex: F40 vs F50)
        if strict:
            for key, conflicts in self.CONFLICT_MAP.items():
                if key in norm_query:
                    for conflict in conflicts:
                        if conflict in norm_combined and conflict not in norm_query:
                            score -= 50.0
                            reasons.append(f"Penalidade por conflito de entidade: '{conflict}' encontrado quando buscava '{key}' (-50)")
                            break
                            
        # 5. Bônus por Resolução
        cand_w = candidate.width or 0
        cand_h = candidate.height or 0
        if cand_w >= 1920 or cand_h >= 1080:
            score += 15.0
            reasons.append(f"Resolução Full HD/4K ({cand_w}x{cand_h}) (+15)")
        elif cand_w >= 1000 or cand_h >= 700:
            score += 8.0
            reasons.append(f"Resolução Alta ({cand_w}x{cand_h}) (+8)")
        elif cand_w > 0 and cand_w < 500:
            score -= 25.0
            reasons.append(f"Resolução muito baixa ({cand_w}x{cand_h}) (-25)")
            
        # 6. Penalidades por formatos indesejados (SVG, ícones, vetores)
        if candidate.url.lower().endswith(".svg") or "icon" in norm_combined or "logo" in norm_combined and "logo" not in norm_query:
            score -= 30.0
            reasons.append("Elemento aparenta ser ícone ou vetor (-30)")
            
        # 6.1 Proteção contra ruídos de artefatos (patches, selos, fragmentos/sucatas de veículos)
        is_searching_vehicle = any(v in norm_query for v in self.VEHICLE_KEYWORDS)
        if is_searching_vehicle:
            for noise in self.ARTIFACT_NOISE_TERMS:
                if noise in norm_combined and noise not in norm_query:
                    score -= 45.0
                    reasons.append(f"Penalidade: Objeto secundário ou sucata '{noise}' detectado ao buscar veículo (-45)")
                    break
                    
        # 6.2 Proteção contra desvio de conteúdo adulto/lingerie fora de contexto
        unrelated_adult_terms = {"lingerie", "swimwear", "bikini", "underwear"}
        if not any(t in norm_query for t in unrelated_adult_terms):
            if any(t in norm_combined for t in unrelated_adult_terms):
                score -= 70.0
                reasons.append("Rejeição: Conteúdo de moda íntima/lingerie fora de contexto (-70)")
            
        # 7. Bônus de autoridade da fonte (apenas se tiver passado no teste de título)
        if candidate.source == "wikimedia" and has_primary_in_title:
            score += 10.0
            reasons.append("Fonte Wikimedia com assunto validado (+10)")
            
        score = max(0.0, min(100.0, score))
        candidate.score = score
        candidate.reasons = reasons
        return score, reasons
        
    def rank_all(self, candidates: List[MediaCandidate], query: str, context: str = "", strict: bool = True) -> List[MediaCandidate]:
        for cand in candidates:
            self.rank_candidate(cand, query, context, strict)
        # Ordena do maior score para o menor
        return sorted(candidates, key=lambda c: c.score, reverse=True)
