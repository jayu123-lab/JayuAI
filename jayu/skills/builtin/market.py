"""Skill: market intelligence — IMPLEMENTADA (Fase 5, datos MT5 reales).

ANÁLISIS puro sobre velas reales de `MT5Connector`:
  quote, rates, structure, analyze, bias.
Los cálculos (indicadores, SMC, bias) viven en `jayu/market/` y NO ejecutan
órdenes. Si MT5 no está disponible, devuelven error honesto (sin inventar).

Uso normal (orquestador): `make_market_skill(lambda: mt5_connector)`.
`register(registry)` mantiene compatibilidad registrando un connector
desconectado (nunca arranca el terminal desde los tests).
"""

from __future__ import annotations

from typing import Any, Callable

from ...market.analyzer import MarketAnalyzer
from ...mt5.connector import MT5Connector, MT5Error
from ..base import Skill

PERMISSIONS = ["market.read", "market.quote", "market.rates",
               "market.structure", "market.analyze", "market.bias"]


def make_market_skill(get_connector: Callable[[], Any]) -> Skill:
    def _analysis() -> MarketAnalyzer:
        return MarketAnalyzer(get_connector())

    def quote(symbol: str = "XAUUSD") -> dict[str, Any]:
        try:
            return {"ok": True, "quote": get_connector().quote(symbol)}
        except MT5Error as exc:
            return _err(exc)

    def rates(symbol: str = "XAUUSD", timeframe: str = "H1",
              count: int = 100) -> dict[str, Any]:
        try:
            rows = get_connector().rates(symbol, timeframe, count=count)
            return {"ok": True, "symbol": symbol, "timeframe": timeframe,
                    "count": len(rows), "candles": rows}
        except MT5Error as exc:
            return _err(exc)

    def structure(symbol: str = "XAUUSD", timeframe: str = "H1",
                  count: int = 400) -> dict[str, Any]:
        res = _analysis().analyze(symbol, timeframe, count=count)
        if not res.get("ok"):
            return res
        return {"ok": True, "symbol": res["symbol"],
                "timeframe": res["timeframe"], **res["structure"]}

    def analyze(symbol: str = "XAUUSD", timeframe: str = "H1",
                count: int = 400) -> dict[str, Any]:
        return _analysis().analyze(symbol, timeframe, count=count)

    def bias(symbol: str = "XAUUSD", timeframe: str = "H1",
             count: int = 400) -> dict[str, Any]:
        res = _analysis().analyze(symbol, timeframe, count=count)
        if not res.get("ok"):
            return res
        return {"ok": True, "symbol": res["symbol"],
                "timeframe": res["timeframe"], **res["bias"]}

    tool_actions = {
        "quote": "market.quote",
        "rates": "market.rates",
        "structure": "market.structure",
        "analyze": "market.analyze",
        "bias": "market.bias",
    }
    return Skill(
        name="market_intelligence",
        description="Análisis de mercados financieros con datos reales MT5: "
                    "indicadores, estructura (BOS/CHoCH), SMC y bias "
                    "BULLISH/BEARISH/NEUTRAL. Solo lectura.",
        category="market",
        tools={"quote": quote, "rates": rates, "structure": structure,
               "analyze": analyze, "bias": bias},
        permission_actions=PERMISSIONS,
        tool_actions=tool_actions,
        version="0.2.0",
    )


def register(registry) -> None:
    """Compatibilidad: registra la skill con un connector desconectado
    (connect_on_use=False) para no arrancar el terminal desde unittest."""
    registry.register(
        make_market_skill(lambda: MT5Connector(connect_on_use=False)))


def _err(exc: MT5Error) -> dict[str, Any]:
    return {"ok": False, "error": str(exc), "hint": getattr(exc, "hint", "")}