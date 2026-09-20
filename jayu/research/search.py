"""Búsqueda web con proveedores pluggable.

Providers:
  - ``duckduckgo`` (por defecto): usa la librería `duckduckgo_search`
    (sin API key). Puede fallar por rate-limit/red: error honesto.
  - ``searxng``: si tienes una instancia propia, define SEARXNG_URL.
"""

from __future__ import annotations

import os
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("research.search")


class SearchError(Exception):
    """Fallo de búsqueda (red, proveedor, rate-limit)."""


class WebSearch:
    def __init__(self, *, provider: str = "duckduckgo",
                 max_results: int = 8,
                 region: str = "wt-wt",
                 timeout: float = 15.0) -> None:
        self.provider = provider
        self.max_results = max_results
        self.region = region
        self.timeout = timeout

    # ------------------------------------------------------------------
    def available(self) -> dict[str, Any]:
        if self.provider == "searxng":
            url = os.environ.get("SEARXNG_URL", "")
            if not url:
                return {"provider": "searxng", "available": False,
                        "reason": "define SEARXNG_URL para usar SearXNG"}
            return {"provider": "searxng", "url": url, "available": True}
        try:
            # duckduckgo-search >= 8 usa el módulo `ddgs`
            import ddgs  # noqa: F401
            return {"provider": "duckduckgo", "available": True}
        except Exception:  # noqa: BLE001
            try:
                from duckduckgo_search import DDGS  # noqa: F401
                return {"provider": "duckduckgo", "available": True}
            except Exception as exc:  # noqa: BLE001
                return {"provider": "duckduckgo", "available": False,
                        "reason": f"ddgs/duckduckgo-search no instalado: {exc}"}

    # ------------------------------------------------------------------
    def search(self, query: str, *, max_results: int | None = None,
               ) -> dict[str, Any]:
        """Devuelve {ok, results: [{title,url,snippet}], provider}."""
        av = self.available()
        if not av["available"]:
            raise SearchError(av.get("reason", "proveedor no disponible"))
        limit = int(max_results or self.max_results)
        query = query.strip()
        if not query:
            raise SearchError("consulta vacía.")
        try:
            if self.provider == "searxng":
                results = self._search_searxng(query, limit)
            else:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                raw = DDGS(timeout=self.timeout).text(
                    query, region=self.region, max_results=limit)
                results = [{"title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", "")} for r in raw]
        except SearchError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SearchError(f"búsqueda falló: {exc}") from exc
        return {"ok": True, "query": query, "provider": self.provider,
                "results": [r for r in results if r.get("url")][:limit]}

    # ------------------------------------------------------------------
    def _search_searxng(self, query: str, limit: int) -> list[dict[str, str]]:
        import httpx
        url = os.environ.get("SEARXNG_URL", "")
        resp = httpx.get(f"{url}/search", params={"q": query, "format": "json"},
                         timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("content", "")}
                for r in data.get("results", [])][:limit]


def search_results(query: str, *, max_results: int = 8,
                   **kw) -> dict[str, Any]:
    """Helper funcional de búsqueda (usa valores por defecto de config)."""
    engine = WebSearch(**kw)
    return engine.search(query, max_results=max_results)