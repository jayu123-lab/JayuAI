"""Skill: web research — PENDIENTE (Fase 3).

No implementado todavía. Las tools devuelven un resultado explícito
ok=False con el estado real. NO se inventan resultados.
"""

from __future__ import annotations

from typing import Any

from ..base import Skill

PERMISSIONS = ["web.search", "web.read"]


def _not_implemented(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "implemented": False,
        "phase": "FASE 3 - web_research (SearXNG + Playwright)",
        "message": ("La investigación web todavía no está implementada. "
                    "No devuelvo resultados inventados."),
    }


def search(query: str = "") -> dict[str, Any]:
    return _not_implemented("search")


def fetch(url: str = "") -> dict[str, Any]:
    return _not_implemented("fetch")


def register(registry) -> None:
    registry.register(Skill(
        name="web_research",
        description="Búsquedas web, lectura de páginas e investigación "
                    "multi-fuente. PENDIENTE: Fase 3.",
        category="web",
        tools={"search": search, "fetch": fetch},
        permission_actions=PERMISSIONS,
        version="0.1.0",
    ))