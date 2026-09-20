"""Skill: market intelligence — PENDIENTE (Fases 5-6).

El análisis de mercados (estructura, SMC, order flow, footprint, bias) se
construirá sobre datos reales (MT5 local / fuentes públicas). Mientras no
exista el módulo, las tools devuelven ok=False sin datos inventados.
"""

from __future__ import annotations

from typing import Any

from ..base import Skill

PERMISSIONS = ["market.read"]


def _not_implemented(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "implemented": False,
        "phase": "FASE 5-6 - market_intelligence",
        "message": ("El análisis de mercados todavía no está implementado. "
                    "No simulo precios ni análisis."),
    }


def quote(symbol: str = "") -> dict[str, Any]:
    return _not_implemented("quote")


def structure(symbol: str = "", timeframe: str = "H1") -> dict[str, Any]:
    return _not_implemented("structure")


def bias(symbol: str = "") -> dict[str, Any]:
    return _not_implemented("bias")


def register(registry) -> None:
    registry.register(Skill(
        name="market_intelligence",
        description="Análisis de mercados financieros (XAUUSD, índices, FX, "
                    "cripto) y construcción de bias. PENDIENTE: Fases 5-6.",
        category="market",
        tools={"quote": quote, "structure": structure, "bias": bias},
        permission_actions=PERMISSIONS,
        version="0.1.0",
    ))