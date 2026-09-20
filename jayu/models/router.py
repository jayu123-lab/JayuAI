"""Router de modelos: decide proveedor + modelo según la tarea.

Criterios: velocidad, coste, complejidad, privacidad y necesidad de
razonamiento. Nunca se usa un modelo enorme para tareas triviales.

Roles por tarea (config/models.yaml -> routing):
    classify : tareas simples -> small
    chat     : conversación   -> fast
    code     : programación   -> default
    reason   : análisis       -> deep
    market   : mercados       -> deep
    research : web            -> default
    embedding: nomic-embed-text
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Settings
from .providers import OpenAICompatibleProvider, build_providers

ROLE_SPEED = ["small", "fast", "default", "deep"]


@dataclass(frozen=True)
class RouteResult:
    provider: str
    model: str
    role: str
    reason: str


class ModelRouter:
    """Selecciona proveedor/modelo. `providers_override` permite tests."""

    def __init__(self, settings: Settings,
                 providers_override: dict[str, OpenAICompatibleProvider] | None = None) -> None:
        self.settings = settings
        self.models_conf = settings.models_conf
        if providers_override is not None:
            self.providers = providers_override
        else:
            self.providers = build_providers(self.models_conf)
        # name -> {roles, provider}
        self._models = dict(self.models_conf.get("models", {}))
        self._routing = dict(self.models_conf.get("routing", {}))

    # -- utilidades ---------------------------------------------------------
    def provider_names(self) -> list[str]:
        return list(self.providers)

    def resolve(self, role: str, *, complexity: int = 1,
                prefer_provider: str | None = None) -> RouteResult:
        """Elige el modelo más rápido que cumpla el rol y la complejidad."""
        wanted = role
        if complexity >= 3 and role in ("chat", "code"):
            wanted = "deep"
        candidates: list[tuple[int, str, str]] = []  # (speed_idx, provider, model)
        for name, meta in self._models.items():
            roles = meta.get("roles", []) or []
            if wanted not in roles:
                continue
            provider = meta.get("provider")
            if provider not in self.providers:
                continue
            if prefer_provider and provider != prefer_provider:
                continue
            speed = meta.get("speed", "medium")
            speed_idx = ROLE_SPEED.index(speed) if speed in ROLE_SPEED else 3
            candidates.append((speed_idx, provider, name))
        if prefer_provider and not candidates:
            # Permitir otro proveedor si el preferido no tiene modelo apto
            return self.resolve(role, complexity=complexity, prefer_provider=None)
        if not candidates:
            roles_known = ", ".join(sorted({r for m in self._models.values()
                                            for r in (m.get("roles") or [])}))
            return RouteResult("", "", wanted,
                               f"Sin modelo con rol '{wanted}' (roles conocidos: {roles_known})")
        candidates.sort(key=lambda c: c[0])
        _, provider, model = candidates[0]
        reason = (f"Rol '{wanted}' resuelto al modelo más rápido disponible "
                  f"(complejidad {complexity}) en proveedor '{provider}'")
        return RouteResult(provider, model, wanted, reason)

    def route(self, task: str, *, intent: str = "chat",
              complexity: int = 1) -> RouteResult:
        role_key = "classify" if intent == "classify" else intent
        target_role = self._routing.get(role_key, self._routing.get("chat", "chat"))
        if target_role in ("small", "fast", "default", "deep"):
            return self.resolve(target_role, complexity=complexity)
        # role explícito (p.ej. embedding)
        order = {r: i for i, r in enumerate(["small", "fast", "default", "deep"])}
        best = None
        for name, meta in self._models.items():
            if target_role not in meta.get("roles", []):
                continue
            provider = meta.get("provider")
            if provider not in self.providers:
                continue
            speed = meta.get("speed", "medium")
            if best is None or order.get(speed, 9) < order.get(best[0], 9):
                best = (speed, provider, name)
        if best is None:
            return RouteResult("", "", target_role,
                               f"Sin modelo con rol '{target_role}'")
        return RouteResult(best[1], best[2], target_role,
                           f"Rol '{target_role}' -> modelo más rápido disponible")

    def available_models(self) -> dict[str, list[str]]:
        """Modelos realmente disponibles en cada proveedor (ping)."""
        out: dict[str, list[str]] = {}
        for name, provider in self.providers.items():
            if hasattr(provider, "installed_models"):
                out[name] = provider.installed_models()
            else:
                out[name] = provider.list_models()
        return out

    def close(self) -> None:
        for provider in self.providers.values():
            try:
                provider.close()
            except Exception:  # noqa: BLE001
                pass