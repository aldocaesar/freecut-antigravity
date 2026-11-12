import json
import random
import re
import ssl
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Union

from ..models import MediaCandidate


class DuckDuckGoSearcher:
    """Buscador de imagens no DuckDuckGo com extração de metadados, URLs originais,

    jitter inter-requisição seguro (>= 2.0s), cookies persistentes e enriquecimento de enquadramento.
    """

    _last_request_time: float = 0.0

    def __init__(
        self,
        timeout: int = 10,
        min_jitter: float = 2.0,
        max_jitter: float = 3.5,
    ):
        self.timeout = timeout
        self.min_jitter = min_jitter
        self.max_jitter = max_jitter
        self.cookie_jar = urllib.request.HTTPCookieProcessor()
        self.opener = urllib.request.build_opener(self.cookie_jar)
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    @classmethod
    def _apply_jitter(cls, min_jitter: float = 2.0, max_jitter: float = 3.5):
        """Enforces random spacing >= min_jitter (default 2.0s) between consecutive requests across all instances."""
        now = time.time()
        elapsed = now - cls._last_request_time
        target_delay = random.uniform(min_jitter, max_jitter)
        if elapsed < target_delay:
            sleep_time = target_delay - elapsed
            time.sleep(sleep_time)
        cls._last_request_time = time.time()

    def enrich_query(self, query: str, framing: Union[bool, str] = True) -> str:
        """Enriches the query with framing terms (e.g. 'screenshot hd', 'still hd') if appropriate."""
        if not framing:
            return query.strip()

        q_clean = query.strip()
        q_lower = q_clean.lower()

        if isinstance(framing, str) and framing.strip():
            framing_term = framing.strip()
            if framing_term.lower() not in q_lower:
                return f"{q_clean} {framing_term}"
            return q_clean

        # Default boolean framing enrichment
        framing_keywords = [
            "screenshot",
            "still",
            "wallpaper",
            "4k",
            "hd",
            "frame",
            "screencap",
        ]
        if not any(kw in q_lower for kw in framing_keywords):
            return f"{q_clean} screenshot hd"

        return q_clean

    def _get_vqd(self, query: str) -> str:
        """Fetches the VQD token from DuckDuckGo search page with session cookie initialization."""
        self._apply_jitter(self.min_jitter, self.max_jitter)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        encoded_q = urllib.parse.quote(query)
        home_url = f"https://duckduckgo.com/?q={encoded_q}&iax=images&ia=images"
        req = urllib.request.Request(home_url, headers=headers)

        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

                # Try multiple regex patterns to extract vqd
                patterns = [
                    r"vqd=([\d-]+)",
                    r'vqd="([^"]+)"',
                    r'data-vqd="([^"]+)"',
                    r"vqd=([a-zA-Z0-9_-]+)",
                    r'"vqd":\s*"([^"]+)"',
                ]
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return ""

    def search(
        self,
        query: str,
        limit: int = 15,
        framing: Union[bool, str] = True,
    ) -> List[MediaCandidate]:
        """Searches DuckDuckGo for high-resolution images matching the query.

        Args:
            query: The search query string.
            limit: Maximum number of candidates to return.
            framing: Whether to append framing terms or a specific framing term string.

        Returns:
            List of MediaCandidate objects with dimensions and original URLs.
        """
        candidates: List[MediaCandidate] = []
        if not query or not query.strip():
            return candidates

        effective_query = self.enrich_query(query, framing=framing)

        try:
            vqd = self._get_vqd(effective_query)
            if not vqd:
                # Retry once if vqd was empty
                self._apply_jitter(self.min_jitter, self.max_jitter)
                vqd = self._get_vqd(effective_query)
                if not vqd:
                    return candidates

            self._apply_jitter(self.min_jitter, self.max_jitter)
            params = {
                "l": "us-en",
                "o": "json",
                "q": effective_query,
                "vqd": vqd,
                "f": ",,,",
                "p": "1",
            }
            ijs_url = f"https://duckduckgo.com/i.js?{urllib.parse.urlencode(params)}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://duckduckgo.com/",
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            req = urllib.request.Request(ijs_url, headers=headers)

            with self.opener.open(req, timeout=self.timeout) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(content)
                results = data.get("results", [])

                for item in results[:limit]:
                    img_url = item.get("image")
                    if not img_url:
                        continue

                    thumb_url = item.get("thumbnail") or img_url
                    title = item.get("title") or ""
                    page_url = item.get("url") or ""
                    try:
                        width = int(item.get("width") or 0)
                    except (ValueError, TypeError):
                        width = 0
                    try:
                        height = int(item.get("height") or 0)
                    except (ValueError, TypeError):
                        height = 0
                    source_domain = item.get("source") or ""

                    source_str = (
                        f"duckduckgo ({source_domain})"
                        if source_domain
                        else "duckduckgo"
                    )

                    candidate = MediaCandidate(
                        url=img_url,
                        thumbnail_url=thumb_url,
                        page_url=page_url,
                        title=title,
                        alt=title,
                        caption=title,
                        source=source_str,
                        media_type="image",
                        width=width,
                        height=height,
                        is_valid=True,
                    )
                    candidates.append(candidate)

        except Exception:
            pass

        return candidates

