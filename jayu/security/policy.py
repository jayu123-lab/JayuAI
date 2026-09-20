"""Política de permisos de JAYU_JAR.

Clasificación de acciones:
    SAFE      -> se permite en todos los modos
    REVIEW    -> requiere confirmación en "confirm_before_execution"
    DANGEROUS -> requiere confirmación SIEMPRE (y se niega en read_only)

Modos globales (settings.yaml -> autonomy_level):
    read_only
    confirm_before_execution  (por defecto)
    autonomous

Reglas cargadas de config/permissions.yaml (globulamas; la más específica gana).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Classification(str, Enum):
    SAFE = "SAFE"
    REVIEW = "REVIEW"
    DANGEROUS = "DANGEROUS"


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Verdict:
    action: str
    classification: Classification
    decision: Decision
    reason: str


_MODE_DEFAULT = {
    "read_only": {"SAFE": "allow", "REVIEW": "deny", "DANGEROUS": "deny"},
    "confirm_before_execution": {"SAFE": "allow", "REVIEW": "ask", "DANGEROUS": "ask"},
    "autonomous": {"SAFE": "allow", "REVIEW": "allow", "DANGEROUS": "ask"},
}


class Policy:
    def __init__(self, permissions_conf: dict[str, Any],
                 autonomy_level: str = "confirm_before_execution") -> None:
        self.actions_conf = dict(permissions_conf.get("actions", {}))
        merged: dict[str, dict[str, str]] = {}
        for level, table in _MODE_DEFAULT.items():
            merged[level] = dict(table)
        for level, table in dict(permissions_conf.get("modes", {})).items():
            base = merged.setdefault(level, {})
            for key, value in (table or {}).items():
                base[str(key).upper()] = str(value).lower()
        self.modes_conf = merged
        self.autonomy_level = autonomy_level
        if self.autonomy_level not in _MODE_DEFAULT:
            self.autonomy_level = "confirm_before_execution"

    def set_autonomy_level(self, level: str) -> None:
        if level in _MODE_DEFAULT:
            self.autonomy_level = level

    # -- clasificación ------------------------------------------------------
    def classify(self, action: str) -> Classification:
        if action in self.actions_conf:
            return self._to_class(action, self.actions_conf[action])
        # globulama más específica (la que coincide con más caracteres fijos)
        best: str | None = None
        for pattern, value in self.actions_conf.items():
            if not any(ch in pattern for ch in "*?"):
                continue
            if fnmatch.fnmatch(action, pattern):
                if best is None or len(pattern) > len(best):
                    best = pattern
        if best is not None:
            return self._to_class(action, self.actions_conf[best])
        return self._to_class(action, self.actions_conf.get("*", "REVIEW"))

    @staticmethod
    def _to_class(action: str, value: Any) -> Classification:
        try:
            return Classification(str(value).upper())
        except ValueError:
            return Classification.REVIEW

    # -- evaluación ---------------------------------------------------------
    def evaluate(self, action: str) -> Verdict:
        cls = self.classify(action)
        mode_table = self.modes_conf.get(self.autonomy_level, _MODE_DEFAULT["confirm_before_execution"])
        decision = mode_table.get(cls.value, "ask")
        reason = f"Clasificación '{cls.value}' en modo '{self.autonomy_level}' -> {decision}"
        return Verdict(action, cls, Decision(decision), reason)

    def is_allowed(self, action: str) -> bool:
        return self.evaluate(action).decision == Decision.ALLOW

    def resolve_confirmation(self, action: str, user_ok: bool = False) -> Verdict:
        """Aplica la respuesta humana a un veredicto ASK."""
        verdict = self.evaluate(action)
        if verdict.decision == Decision.ASK:
            resolved = Decision.ALLOW if user_ok else Decision.DENY
            return Verdict(action, verdict.classification, resolved,
                           f"Confirmación humana {'SÍ' if user_ok else 'NO'} para {action}")
        return verdict