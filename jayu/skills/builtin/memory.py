"""Skill: memoria (recordar / consultar / preferencias). SAFE."""

from __future__ import annotations

from typing import Any

from ..base import Skill

PERMISSIONS = ["memory.read", "memory.write"]


def make_store(getter):
    """Inyección del MemoryStore en las tools (evita estado global)."""
    store = getter()

    def recall(query: str = "", limit: int = 10) -> dict[str, Any]:
        if query:
            rows = store.search_long_term(query, limit=limit)
        else:
            rows = store.all_long_term(limit=200)
        return {"ok": True, "query": query, "results": rows,
                "count": len(rows)}

    def remember(key: str, value: str, category: str = "fact") -> dict[str, Any]:
        store.remember(key, value, category=category, source="assistant")
        store.log_episode("memory_write", "jayu",
                          f"Recordado {category}: {key}")
        return {"ok": True, "key": key, "category": category}

    def prefer(key: str, value: str) -> dict[str, Any]:
        store.set_pref(key, value)
        return {"ok": True, "key": key, "value": value}

    def prefs() -> dict[str, Any]:
        return {"ok": True, "prefs": store.prefs()}

    skill = Skill(
        name="memory",
        description="Memoria persistente: recall, remember, preferencias.",
        category="memory",
        tools={"recall": recall, "remember": remember,
               "prefer": prefer, "prefs": prefs},
        permission_actions=PERMISSIONS,
        version="0.1.0",
    )
    return skill


def register(registry) -> None:
    # La skill de memoria necesita el store -> se registra con un factory
    # diferido en el orquestador. Esta función se sustituye en la construcción
    # real (ver core/orchestrator.py).
    raise RuntimeError(
        "memory skill must be registered via register_with_store (orchestrator)",
    )