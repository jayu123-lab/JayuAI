"""FASE 3 — Investigación web de JayuAI.

  - `WebSearch`  -> búsquedas por proveedor (DuckDuckGo / SearXNG).
  - `PageFetcher`-> descarga y limpia páginas web (texto útil, sin ruido).
  - `summarize_text` -> resumen honesto (con LLM local si está, o extractivo).

Los resultados SIEMPRE tiran de fuentes reales; nunca se inventan titulares.
Si un proveedor no está disponible (sin red / bloqueado / clave), se devuelve
ok=False con el motivo exacto.
"""

from .fetcher import FetchError, PageFetcher
from .search import SearchError, WebSearch, search_results

__all__ = ["WebSearch", "search_results", "PageFetcher", "FetchError",
           "SearchError"]