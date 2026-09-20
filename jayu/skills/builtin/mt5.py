"""Skill: MetaTrader 5 (FASE 6).

ANÁLISIS  (lectura, SAFE):  status, account, positions, orders, symbols,
                            quote, rates, ticks, history, sizer (sugerencia
                            de lote SIN ejecutar nada).
EJECUCIÓN (REVIEW/DANGEROUS, siempre gateada):
                            market_order, pending_order, modify_position,
                            modify_pending, close_position, close_all,
                            breakeven, trailing.

La ejecución DE VUELVE `blocked` si el modo de trading es READ_ONLY
(por defecto) o si no hay confirmación humana. Nada se ejecuta sin pasar
por MT5Executor + política + auditoría.
"""

from __future__ import annotations

from typing import Any

from ...mt5.connector import MT5Error
from ...mt5.execution import MT5Executor, TradingMode
from ..base import Skill

READ_ACTIONS = ["mt5.status", "mt5.account", "mt5.positions_read",
                "mt5.orders_read", "mt5.symbols", "mt5.quote",
                "mt5.rates", "mt5.ticks", "mt5.history", "mt5.sizer"]
EXEC_ACTIONS = ["mt5.market_order", "mt5.pending_order",
                "mt5.modify_position", "mt5.modify_order",
                "mt5.close_position", "mt5.close_all",
                "mt5.breakeven", "mt5.trailing"]


def make_mt5_skill(get_connector, get_executor, get_sizer) -> Skill:
    def cn():
        return get_connector()

    def ex() -> MT5Executor:
        return get_executor()

    # ---------------- LECTURA (SAFE) ----------------
    def status() -> dict[str, Any]:
        s = cn().status()
        s["trading_mode"] = ex().mode.value
        return s

    def account() -> dict[str, Any]:
        try:
            return {"ok": True, "account": cn().account_info()}
        except MT5Error as e:
            return _err(e)

    def positions(symbol: str | None = None) -> dict[str, Any]:
        try:
            rows = cn().positions(symbol=symbol)
            return {"ok": True, "count": len(rows), "positions": rows}
        except MT5Error as e:
            return _err(e)

    def orders(symbol: str | None = None) -> dict[str, Any]:
        try:
            rows = cn().orders(symbol=symbol)
            return {"ok": True, "count": len(rows), "orders": rows}
        except MT5Error as e:
            return _err(e)

    def symbols() -> dict[str, Any]:
        try:
            return {"ok": True, "count": len(cn().symbols()),
                    "symbols": cn().symbols()}
        except MT5Error as e:
            return _err(e)

    def quote(symbol: str) -> dict[str, Any]:
        try:
            return {"ok": True, "quote": cn().quote(symbol)}
        except MT5Error as e:
            return _err(e)

    def rates(symbol: str, timeframe: str = "H1", count: int = 100,
              ) -> dict[str, Any]:
        try:
            rows = cn().rates(symbol, timeframe, count=count)
            return {"ok": True, "symbol": symbol, "timeframe": timeframe,
                    "count": len(rows), "candles": rows}
        except MT5Error as e:
            return _err(e)

    def ticks(symbol: str, count: int = 100) -> dict[str, Any]:
        try:
            rows = cn().ticks(symbol, count=count)
            return {"ok": True, "symbol": symbol, "count": len(rows),
                    "ticks": rows}
        except MT5Error as e:
            return _err(e)

    def history(days: int = 7, symbol: str | None = None) -> dict[str, Any]:
        try:
            return {"ok": True, **cn().history(days=days, symbol=symbol)}
        except MT5Error as e:
            return _err(e)

    def sizer(symbol: str, entry: float, sl: float,
              risk_pct: float | None = None) -> dict[str, Any]:
        try:
            return {"ok": True,
                    **get_sizer().lot_size(symbol, entry, sl,
                                           risk_pct=risk_pct)}
        except MT5Error as e:
            return _err(e)

    # ---------------- EJECUCIÓN (gateada) ----------------
    def _exec(method, params: dict[str, Any], kw: dict[str, Any]) -> dict[str, Any]:
        authorized = kw.pop("_jayu_authorized", False)
        interactive = kw.pop("_jayu_interactive", False)
        try:
            res = method(interactive=interactive, user_ok=authorized, **params)
        except MT5Error as e:
            return _err(e)
        out = res.as_dict()
        out["trading_mode"] = ex().mode.value
        if getattr(res, "blocked", None):
            out["blocked_reason"] = res.blocked
        return out

    def market_order(symbol: str = "", volume: float = 0.0, side: str = "",
                     sl: float | None = None, tp: float | None = None,
                     deviation: int | None = None, magic: int | None = None,
                     comment: str | None = None, **kw) -> dict[str, Any]:
        if not symbol or volume <= 0 or not side:
            return {"ok": False, "error": "Parámetros: symbol, volume>0, side"}
        return _exec(ex().market_order,
                     {"symbol": symbol, "volume": volume, "side": side,
                      "sl": sl, "tp": tp, "deviation": deviation,
                      "magic": magic, "comment": comment}, kw)

    def pending_order(symbol: str = "", volume: float = 0.0, kind: str = "",
                      price: float | None = None, sl: float | None = None,
                      tp: float | None = None, magic: int | None = None,
                      comment: str | None = None, **kw) -> dict[str, Any]:
        if not symbol or volume <= 0 or not kind or price is None:
            return {"ok": False,
                    "error": "Parámetros: symbol, volume, kind, price"}
        return _exec(ex().pending_order,
                     {"symbol": symbol, "volume": volume, "kind": kind,
                      "price": price, "sl": sl, "tp": tp, "magic": magic,
                      "comment": comment}, kw)

    def modify_position(ticket: int = 0, sl: float | None = None,
                        tp: float | None = None, **kw) -> dict[str, Any]:
        if not ticket:
            return {"ok": False, "error": "Parámetros: ticket"}
        return _exec(ex().modify_position,
                     {"ticket": ticket, "sl": sl, "tp": tp}, kw)

    def modify_pending(ticket: int = 0, sl: float | None = None,
                       tp: float | None = None, price: float | None = None,
                       **kw) -> dict[str, Any]:
        if not ticket:
            return {"ok": False, "error": "Parámetros: ticket"}
        return _exec(ex().modify_pending,
                     {"ticket": ticket, "sl": sl, "tp": tp, "price": price},
                     kw)

    def close_position(ticket: int = 0,
                       deviation: int | None = None, **kw) -> dict[str, Any]:
        if not ticket:
            return {"ok": False, "error": "Parámetros: ticket"}
        return _exec(ex().close_position,
                     {"ticket": ticket, "deviation": deviation}, kw)

    def close_all(**kw) -> dict[str, Any]:
        return _exec(ex().close_all, {}, kw)

    def breakeven(ticket: int = 0, offset_points: float = 5.0,
                  **kw) -> dict[str, Any]:
        if not ticket:
            return {"ok": False, "error": "Parámetros: ticket"}
        return _exec(ex().breakeven,
                     {"ticket": ticket, "offset_points": offset_points}, kw)

    def trailing(symbol: str = "", trail_points: float = 0.0,
                 step_points: float = 0.0, **kw) -> dict[str, Any]:
        if not symbol or trail_points <= 0:
            return {"ok": False, "error": "Parámetros: symbol, trail_points"}
        return _exec(ex().trailing,
                     {"symbol": symbol, "trail_points": trail_points,
                      "step_points": step_points}, kw)

    tool_actions = {
        "status": "mt5.status", "account": "mt5.account",
        "positions": "mt5.positions_read", "orders": "mt5.orders_read",
        "symbols": "mt5.symbols", "quote": "mt5.quote",
        "rates": "mt5.rates", "ticks": "mt5.ticks",
        "history": "mt5.history", "sizer": "mt5.sizer",
        "market_order": "mt5.market_order",
        "pending_order": "mt5.pending_order",
        "modify_position": "mt5.modify_position",
        "modify_pending": "mt5.modify_order",
        "close_position": "mt5.close_position",
        "close_all": "mt5.close_all",
        "breakeven": "mt5.breakeven",
        "trailing": "mt5.trailing",
    }
    return Skill(
        name="mt5",
        description="MetaTrader 5: lectura de cuenta/posiciones/mercado y "
                    "ejecución protegida (READ_ONLY por defecto).",
        category="mt5",
        tools={"status": status, "account": account, "positions": positions,
               "orders": orders, "symbols": symbols, "quote": quote,
               "rates": rates, "ticks": ticks, "history": history,
               "sizer": sizer, "market_order": market_order,
               "pending_order": pending_order, "modify_position": modify_position,
               "modify_pending": modify_pending, "close_position": close_position,
               "close_all": close_all, "breakeven": breakeven,
               "trailing": trailing},
        permission_actions=READ_ACTIONS + EXEC_ACTIONS,
        tool_actions=tool_actions,
        version="0.1.0",
    )


def _err(e: MT5Error) -> dict[str, Any]:
    return {"ok": False, "error": str(e), "hint": getattr(e, "hint", "")}