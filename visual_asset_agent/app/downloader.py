import os
import re
import hashlib
import requests
from io import BytesIO
from PIL import Image
from typing import Optional, Tuple
from .models import MediaCandidate

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class MediaDownloader:
    """Downloader seguro com validação de formato, integridade PIL e dimensões."""
    
    def __init__(self, download_dir: str = None, timeout: int = 15):
        self.download_dir = download_dir or os.path.join(BASE_DIR, "data", "downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        self.timeout = timeout
        self.headers = {
            "User-Agent": "FreeCutVideoBot/2.0 (video-asset-downloader; contact@freecut.local) Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        
    def _clean_filename(self, text: str) -> str:
        clean = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
        return clean[:40].strip('_')
        
    def download(self, candidate: MediaCandidate, prefix: str = "media") -> Tuple[bool, Optional[str], str]:
        """
        Baixa o candidato e retorna: (sucesso: bool, caminho_local: str, erro/mensagem: str)
        """
        if not candidate.url:
            return False, None, "URL inválida ou vazia"
            
        try:
            resp = requests.get(candidate.url, headers=self.headers, timeout=self.timeout, stream=True)
            if resp.status_code != 200:
                return False, None, f"HTTP Error {resp.status_code}"
                
            content = resp.content
            if len(content) < 5000:  # Menor que 5KB (provável thumbnail corrompido ou erro HTML)
                return False, None, "Arquivo muito pequeno (<5KB)"
                
            if candidate.media_type == "video":
                clean_pfx = self._clean_filename(prefix)
                clean_ttl = self._clean_filename(candidate.title)
                hash_id = hashlib.md5(candidate.url.encode()).hexdigest()[:8]
                filename = f"{clean_pfx}_{clean_ttl}_{hash_id}.mp4"
                output_path = os.path.join(self.download_dir, filename)
                with open(output_path, "wb") as f:
                    f.write(content)
                candidate.local_path = output_path
                return True, output_path, "Vídeo baixado com sucesso"
            else:
                # Valida e converte imagem
                try:
                    img = Image.open(BytesIO(content))
                    img.verify()  # Verifica integridade
                    
                    # Reabre para pegar dimensões reais e salvar
                    img = Image.open(BytesIO(content))
                    candidate.width, candidate.height = img.size
                    
                    if candidate.width < 400 or candidate.height < 300:
                        return False, None, f"Dimensões insuficientes ({candidate.width}x{candidate.height})"
                        
                    # Converte para RGB se necessário
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                        
                    clean_pfx = self._clean_filename(prefix)
                    clean_ttl = self._clean_filename(candidate.title)
                    hash_id = hashlib.md5(candidate.url.encode()).hexdigest()[:8]
                    filename = f"{clean_pfx}_{clean_ttl}_{hash_id}.jpg"
                    output_path = os.path.join(self.download_dir, filename)
                    
                    img.save(output_path, "JPEG", quality=95)
                    candidate.local_path = output_path
                    return True, output_path, "Imagem validada e salva com sucesso"
                except Exception as e:
                    return False, None, f"Erro ao processar imagem PIL: {str(e)}"
                    
        except Exception as e:
            return False, None, f"Exceção no download: {str(e)}"
