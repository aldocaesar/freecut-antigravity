from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class MediaCandidate:
    url: str
    title: str = ""
    thumbnail_url: str = ""
    page_url: str = ""
    alt: str = ""
    caption: str = ""
    source: str = "web"
    media_type: str = "image"  # "image" or "video"
    width: int = 0
    height: int = 0
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    ocr_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    local_path: Optional[str] = None
    is_valid: bool = True

@dataclass
class SearchResult:
    query: str
    candidates: List[MediaCandidate] = field(default_factory=list)
    winner: Optional[MediaCandidate] = None
    execution_time_s: float = 0.0
    status: str = "success"
    message: str = ""
