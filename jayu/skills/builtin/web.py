"""Skill: web_research — FASE 3 implementada (búsqueda + lectura + resumen).

Tools:
  - search(query)     web.search   SAFE — resultados reales (DuckDuckGo/SearXNG).
  - read(url)         web.read      SAFE — texto limpio de una página.
  - summarize(url)    web.summarize SAFE — resumen (LLM local si está,
                                           si no extractivo honesto).

Nunca se inventan resultados ni titulares: sin proveedor o sin red la skill
devuelve ok=False con el motivo exacto.
"""

from __future__ import annotations

from typing import Any, Callable

from ...models.providers import LLMError
from ...research.fetcher import FetchError, extract_relevant
from ...research.search import SearchError
from ...research.summary import summarize_text
from ..base import Skill

GOLD_KEYWORDS = ("oro", "gold", "xau", "plata", "silver", "xag", "dxy",
                 "dólar", "bonos", "tesoro", "fomc", "fed", "inflación",
                 "cpi", "banco central", "tasas reales", "recesión")


def make_web_skill(get_search, get_fetcher,
                   chat_fn: Callable[[str], str] | None = None) -> Skill:
    # ------------------------------------------------------------------
    def search(query: str = "", max_results: int = 6, **kw) -> dict[str, Any]:
        try:
            return get_search().search(query, max_results=max_results)
        except SearchError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    def read(url: str = "", **kw) -> dict[str, Any]:
        if not url.strip():
            return {"ok": False, "error": "falta URL."}
        try:
            return get_fetcher().fetch(url)
        except FetchError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    def summarize(url: str = "", **kw) -> dict[str, Any]:
        if not url.strip():
            return {"ok": False, "error": "falta URL."}
        try:
            page = get_fetcher().fetch(url)
        except FetchError as exc:
            return {"ok": False, "error": str(exc)}
        if not page.get("ok"):
            return page
        res = summarize_text(page.get("text", ""), chat_fn=chat_fn)
        res["url"] = page.get("url")
        res["title"] = page.get("title")
        summary_low = res.get("summary", "").lower()
        if any(tag in summary_low for tag in
               ("oro", "gold", "oro/plata", "xau")):
            relevant = extract_relevant(page.get("text", ""), GOLD_KEYWORDS)
            res["pasajes_relevantes"] = relevant
        return res

    # ------------------------------------------------------------------
    return Skill(
        name="web_research",
        description="Investigación web: búsqueda multi-fuente, lectura de "
                    "páginas y resumen (LLM local si está). Ideal para "
                    "noticias de oro y macro.",
        category="web",
        tools={"search": search, "read": read, "summarize": summarize},
        permission_actions=["web.search", "web.read", "web.summarize"],
        tool_actions={"search": "web.search", "read": "web.read",
                      "summarize": "web.summarize"},
        version="0.2.0",
    )


def register(registry) -> None:
    """Compatibilidad: skill con motores DESCONECTADOS (tests honestos)."""
    registry.register(make_web_skill(lambda: None, lambda: None))