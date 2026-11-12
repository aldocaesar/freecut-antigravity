import os
import sqlite3
import time
from typing import Optional, Dict, Any
from .models import MediaCandidate

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class CacheManager:
    """Gerenciador de cache local em SQLite para evitar buscas e downloads repetidos."""
    
    def __init__(self, db_path: str = None):
        if not db_path:
            cache_dir = os.path.join(BASE_DIR, "data", "cache")
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, "media_cache.db")
            
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_cache (
                    query TEXT PRIMARY KEY,
                    url TEXT,
                    title TEXT,
                    source TEXT,
                    media_type TEXT,
                    width INTEGER,
                    height INTEGER,
                    score REAL,
                    ocr_text TEXT,
                    local_path TEXT,
                    created_at REAL
                )
            """)
            conn.commit()
            
    def get(self, query: str) -> Optional[MediaCandidate]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url, title, source, media_type, width, height, score, ocr_text, local_path FROM media_cache WHERE query = ?", (query.lower().strip(),))
            row = cursor.fetchone()
            if row:
                url, title, source, media_type, width, height, score, ocr_text, local_path = row
                if local_path and os.path.exists(local_path):
                    return MediaCandidate(
                        url=url,
                        title=title,
                        source=source,
                        media_type=media_type,
                        width=width,
                        height=height,
                        score=score,
                        ocr_text=ocr_text,
                        local_path=local_path
                    )
        return None
        
    def set(self, query: str, candidate: MediaCandidate):
        if not candidate.local_path or not os.path.exists(candidate.local_path):
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO media_cache 
                (query, url, title, source, media_type, width, height, score, ocr_text, local_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                query.lower().strip(),
                candidate.url,
                candidate.title,
                candidate.source,
                candidate.media_type,
                candidate.width,
                candidate.height,
                candidate.score,
                candidate.ocr_text,
                candidate.local_path,
                time.time()
            ))
            conn.commit()
