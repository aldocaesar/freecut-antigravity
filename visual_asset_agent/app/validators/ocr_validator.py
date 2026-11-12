import os
import io
import re
from typing import Tuple, List
from PIL import Image

class OCRValidator:
    """Validador visual via OCR local com RapidOCR (onnxruntime)."""
    
    WATERMARKS = ["shutterstock", "gettyimages", "alamy", "istockphoto", "dreamstime", "123rf", "depositphotos", "watermark", "stock photo"]
    
    def __init__(self):
        self.ocr = None
        self._init_ocr()
        
    def _init_ocr(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
        except Exception:
            self.ocr = None
            
    def is_available(self) -> bool:
        return self.ocr is not None
        
    def extract_text(self, image_input) -> str:
        """Extrai todo o texto da imagem (caminho str, bytes ou PIL Image)."""
        if not self.ocr:
            return ""
            
        try:
            if isinstance(image_input, str):
                if not os.path.exists(image_input):
                    return ""
                result, _ = self.ocr(image_input)
            elif isinstance(image_input, bytes):
                import numpy as np
                import cv2
                nparr = np.frombuffer(image_input, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                result, _ = self.ocr(img)
            elif isinstance(image_input, Image.Image):
                import numpy as np
                img_np = np.array(image_input)
                result, _ = self.ocr(img_np)
            else:
                return ""
                
            if not result:
                return ""
                
            # Coleta todos os blocos de texto
            lines = [item[1] for item in result if len(item) > 1 and item[1]]
            return " ".join(lines).strip()
        except Exception:
            return ""
            
    def validate_image_ocr(self, image_input, target_query: str) -> Tuple[float, List[str], str]:
        """
        Retorna:
        - score_adjustment: bônus ou penalidade
        - reasons: justificativas
        - detected_text: texto lido pelo OCR
        """
        detected_text = self.extract_text(image_input)
        if not detected_text:
            return 0.0, ["Nenhum texto detectado na imagem"], ""
            
        norm_text = detected_text.lower()
        norm_query = target_query.lower()
        reasons = []
        score_adj = 0.0
        
        # 1. Detecção de marcas d'água de bancos pagos
        for wm in self.WATERMARKS:
            if wm in norm_text:
                score_adj -= 50.0
                reasons.append(f"Marca d'água detectada por OCR: '{wm}' (-50)")
                break
                
        # 2. Busca de palavras-chave da query estampadas na foto (ex: emblema F40, marca Coca-Cola, tarja STF)
        query_words = [w for w in re.sub(r'[^a-z0-9]', ' ', norm_query).split() if len(w) > 2]
        matched_ocr = [w for w in query_words if w in norm_text]
        
        if matched_ocr:
            bonus = len(matched_ocr) * 15.0
            score_adj += bonus
            reasons.append(f"Texto OCR confirmou entidade: {', '.join(matched_ocr)} (+{bonus:.1f})")
            
        return score_adj, reasons, detected_text
