"""Registro central de skills.

La arquitectura de skills permite añadir capacidades sin tocar el CORE:
una skill se registra y sus herramientas quedan disponibles al orquestador
con sus permisos declarados.
"""

from __future__ import annotations

from typing import Any

from ..security.policy import Policy
from .base import Skill, SkillError


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise SkillError(f"La skill '{skill.name}' ya está registrada.")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise SkillError(f"Skill desconocida: '{name}'. "
                             f"Registradas: {', '.join(sorted(self._skills))}.")
        return self._skills[name]

    def list(self) -> list[dict[str, Any]]:
        return [skill.describe() for skill in self._skills.values()]

    def categories(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for skill in self._skills.values():
            out.setdefault(skill.category, []).append(skill.name)
        return out

    def allowed_tools_for(self, policy: Policy) -> dict[str, list[str]]:
        """Skills/herramientas permitidas según la política actual."""
        out: dict[str, list[str]] = {}
        for skill in self._skills.values():
            allowed = []
            for action in skill.permission_actions:
                if policy.is_allowed(action):
                    allowed.append(action)
            out[skill.name] = allowed
        return out