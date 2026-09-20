"""Skill: unidad extensible de capacidad de JAYU_JAR.

Un skill registra:
    - nombre y descripción
    - categoría (market, coding, web, voice, pc, mt5, ...)
    - herramientas (nombre -> callable)
    - acciones de permiso que requiere (para el policy check)

Ejemplo de skill real (registrado en Fases 3-8):

    Skill(
        name="web_research",
        description="Búsqueda y lectura web multi-fuente",
        category="web",
        tools={"search": search_impl, "fetch": fetch_impl},
        permission_actions=["web.search", "web.read"],
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class SkillError(Exception):
    """Error controlado dentro de una skill."""


@dataclass
class Skill:
    name: str
    description: str
    category: str
    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    permission_actions: list[str] = field(default_factory=list)
    version: str = "0.1.0"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "tools": list(self.tools),
        }


def skill_tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorador opcional para marcar handlers como tools de skill."""
    func._is_skill_tool = True  # type: ignore[attr-defined]
    return func