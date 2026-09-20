"""Lectura de páginas web: descarga HTTP y extracción de texto limpio.

Sin navegador (no usamos Playwright aún): sirve para notas, artículos,
blogs y páginas de texto estático. Las páginas renderizadas por JS (SPA)
pueden devolver poco contenido; se declara honestamente.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..logging_setup import get_logger

logger = get_logger("research.fetch")

_URL_RE = re.compile(r"https?://\S+")
_DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "es,en;q=0.8",
}


class FetchError(Exception):
    """No se pudo leer la página (red/estado/parseo)."""


class PageFetcher:
    def __init__(self, *, timeout: float = 20.0,
                 max_chars: int = 12000) -> None:
        self.timeout = timeout
        self.max_chars = max_chars

    # ------------------------------------------------------------------
    def fetch(self, url: str) -> dict[str, Any]:
        url = url.strip()
        if not _URL_RE.match(url):
            raise FetchError(f"URL no válida: {url!r}")
        try:
            resp = httpx.get(url, headers=_DEFAULT_HEADERS,
                             timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"HTTP falló para {url}: {exc}") from exc
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav",
                         "footer", "form", "iframe"]):
            tag.decompose()
        title = (soup.title.string.strip()
                 if soup.title and soup.title.string else "")
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        body = "\n".join(lines)
        body = body[:self.max_chars]
        return {"ok": True, "url": str(resp.url), "title": title,
                "chars": len(body),
                "text": body,
                "links": self._top_links(soup)}

    # ------------------------------------------------------------------
    def _top_links(self, soup: BeautifulSoup, limit: int = 8) -> list[str]:
        seen: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and href not in seen:
                seen.append(href)
        return seen[:limit]


def extract_relevant(text: str, keywords: tuple[str, ...],
                     limit: int = 3) -> list[str]:
    """Selecciona párrafos que mencionan palabras clave (resumen extractivo)."""
    out: list[str] = []
    for para in text.splitlines():
        low = para.lower()
        if any(k.lower() in low for k in keywords):
            out.append(para[:600])
        if len(out) >= limit:
            break
    return out