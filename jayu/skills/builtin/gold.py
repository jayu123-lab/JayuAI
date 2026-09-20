"""Skill: gold_analyst — ESPECIALISTA en XAUUSD y el ecosistema del oro.

Cubre todos los ámbitos: macro (tasas reales, FED, inflación, empleo),
bancos centrales, demanda física, flujos (ETFs/COT), correlaciones (DXY,
bonos del Tesoro, plata) y niveles técnicos.

Tools:
  - drivers(symbol)  gold.context  SAFE — marco de drivers + datos en vivo.
  - levels(...)      gold.levels   SAFE — niveles desde estructura real.
  - calendar()       gold.calendar SAFE — agenda macro típica del mes.

Los datos en vivo vienen de MT5; el conocimiento estático de jayu/kb/gold.py.
Nunca se inventa un precio: sin terminal se marca `dato: pendiente`.
"""

from __future__ import annotations

from typing import Any, Callable

from ...kb.gold import GOLD_ASSETS, gold_context, gold_levels, macro_calendar
from ...market.analyzer import MarketAnalyzer
from ...mt5.connector import MT5Error
from ..base import Skill

# Símbolos a consultar en vivo si el broker los ofrece.
_LIVE_SYMBOLS = ["XAUUSD", "XAGUSD", "DXY", "US10Y"]

# Alias alternativos que algunos brokers usan para los índices/bonos.
_ALIASES = {"DXY": ["DXY", "DX"], "US10Y": ["US10Y", "TNX", "UST10Y"]}


def make_gold_skill(get_connector) -> Skill:
    # ------------------------------------------------------------------
    def _live_quotes(symbols_map: dict[str, str]) -> dict[str, Any]:
        """Consulta quotes en vivo; devuelve {SYM: precio} y marcas pensadas."""
        conn = get_connector()
        if conn is None:
            return {}
        try:
            avail = {s.upper() for s in conn.symbols()}
        except MT5Error:
            return {}
        out: dict[str, Any] = {}
        for canon, sym in symbols_map.items():
            if sym in avail:
                try:
                    q = conn.quote(sym)
                    out[canon] = q.get("bid")
                except MT5Error:
                    out[canon] = None
            else:
                out[canon] = None
        return out

    def _symbol_pick(alias: str, avail: set[str]) -> str | None:
        for candidate in _ALIASES.get(alias, [alias]):
            if candidate in avail:
                return candidate
        return None

    # ------------------------------------------------------------------
    def drivers(symbol: str = "XAUUSD", **kw) -> dict[str, Any]:
        conn = get_connector()
        symbols_map: dict[str, str] = {"XAUUSD": symbol.upper()}
        try:
            avail = {s.upper() for s in conn.symbols()} if conn else set()
        except MT5Error:
            avail = set()
        for alias, syms in _ALIASES.items():
            pick = _symbol_pick(alias, avail)
            if pick:
                symbols_map[alias] = pick
        # siempre intenta XAGUSD aunque no esté en aliases
        if "XAGUSD" in avail and "XAGUSD" not in symbols_map:
            symbols_map["XAGUSD"] = "XAGUSD"
        live = _live_quotes(symbols_map)
        ctx = gold_context(symbol=symbol.upper(), live=live)
        ctx["disponible_en_broker"] = {
            k: (v is not None) for k, v in live.items()}
        ctx["activos"] = {k: v for k, v in GOLD_ASSETS.items()
                          if k in live or k in ("XAUUSD", "XAGUSD", "DXY",
                                                "US10Y")}
        return ctx

    # ------------------------------------------------------------------
    def levels(symbol: str = "XAUUSD", timeframe: str = "H1",
               count: int = 300, **kw) -> dict[str, Any]:
        conn = get_connector()
        if conn is None:
            return {"ok": False, "error": "sin conector MT5."}
        try:
            an = MarketAnalyzer(conn)
            report = an.analyze(symbol.upper(), timeframe, count)
        except MT5Error as exc:
            return {"ok": False, "error": str(exc)}
        if not report.get("ok"):
            return report
        structure = report.get("structure", {})
        price = (report.get("last_candle") or {}).get("close")
        atr = (report.get("indicators") or {}).get("atr14")
        res = gold_levels(
            price=price,
            last_swing_high=(structure.get("last_swing_high") or {}).get(
                "price"),
            last_swing_low=(structure.get("last_swing_low") or {}).get(
                "price"),
            atr=atr)
        res["symbol"] = symbol.upper()
        res["timeframe"] = timeframe
        res["trend"] = structure.get("trend")
        return res

    # ------------------------------------------------------------------
    def calendar(**kw) -> dict[str, Any]:
        return macro_calendar()

    # ------------------------------------------------------------------
    return Skill(
        name="gold_analyst",
        description="Especialista en XAUUSD y el ecosistema del oro: drivers "
                    "macro/fundamentales (FED, tasas reales, bancos "
                    "centrales, DXY, bonos, plata) + niveles técnicos y "
                    "agenda macro.",
        category="market",
        tools={"drivers": drivers, "levels": levels, "calendar": calendar},
        permission_actions=["gold.context", "gold.levels", "gold.calendar"],
        tool_actions={"drivers": "gold.context", "levels": "gold.levels",
                      "calendar": "gold.calendar"},
        version="0.1.0",
    )