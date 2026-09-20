"""MT5Executor — capa de EJECUCIÓN de órdenes (FASE 6).

CRÍTICO:
  - NUNCA ejecuta sin antes pasar por el `Policy` y registrar auditaría.
  - Modos de trading (config/trading.yaml -> mode):
      READ_ONLY                 -> ninguna ejecución (por defecto)
      CONFIRM_BEFORE_EXECUTION  -> cada orden exige confirmación humana
      AUTONOMOUS_TRADING        -> SOLO si `autonomous_trading_enabled: true`
                                   (por defecto false). Ejecuta REVIEW sin
                                   preguntar; DANGEROUS siempre pregunta.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from ..logging_setup import get_logger
from ..security.audit import Auditor
from ..security.policy import Classification, Decision, Policy, Verdict
from .connector import MT5Connector, MT5Error

logger = get_logger("mt5.execution")


class TradingMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    CONFIRM_BEFORE_EXECUTION = "CONFIRM_BEFORE_EXECUTION"
    AUTONOMOUS_TRADING = "AUTONOMOUS_TRADING"


def resolve_trading_mode(trading_conf: dict[str, Any]) -> TradingMode:
    raw = str(trading_conf.get("mode", "READ_ONLY")).upper()
    # AUTONOMOUS_TRADING solo se honra con lo que indica el propio Config
    enabled = bool(trading_conf.get("autonomous_trading_enabled", False))
    try:
        mode = TradingMode(raw)
    except ValueError:
        mode = TradingMode.READ_ONLY
    if mode == TradingMode.AUTONOMOUS_TRADING and not enabled:
        logger.warning("AUTONOMOUS_TRADING en config per se -> degradado a "
                       "CONFIRM_BEFORE_EXECUTION (autonomous_trading_enabled "
                       "no está en true)")
        return TradingMode.CONFIRM_BEFORE_EXECUTION
    return mode


class ExecuteResult:
    """Resultado estructurado de una operación de ejecución."""

    def __init__(self, *, ok: bool, action: str, verdict: Verdict | None,
                 blocked: str | None = None, data: dict[str, Any] | None = None,
                 reason: str = "") -> None:
        self.ok = ok
        self.action = action
        self.verdict = verdict
        self.blocked = blocked
        self.data = data or {}
        self.reason = reason

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "verdict": self.verdict.decision.value if self.verdict else None,
            "classification": self.verdict.classification.value if self.verdict else None,
            "blocked": self.blocked,
            "reason": self.reason,
            "data": self.data,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExecuteResult ok={self.ok} action={self.action} ok={self.ok}>"


class MT5Executor:
    def __init__(
        self,
        connector: MT5Connector,
        policy: Policy,
        auditor: Auditor,
        trading_conf: dict[str, Any],
        *,
        confirmer: Callable[[str], bool] | None = None,
    ) -> None:
        self.connector = connector
        self.policy = policy
        self.auditor = auditor
        self.trading_conf = trading_conf or {}
        self.confirmer = confirmer or (lambda _p: False)
        self.mode = resolve_trading_mode(self.trading_conf)

    # ------------------------------------------------------------------
    # Autorización
    # ------------------------------------------------------------------
    def _authorize(self, action: str, tool: str, *, interactive: bool,
                   user_ok: bool) -> tuple[ExecuteResult | None, Verdict | bool]:
        """Comprueba modo trading + política. Devuelve (bloqueo, autorizado)."""
        effective = self.mode
        if effective == TradingMode.READ_ONLY:
            verdict = self.policy.evaluate(action)
            self.auditor.record(actor="jayu", action=action,
                                classification=verdict.classification,
                                decision=Decision.DENY,
                                reason="modo de trading READ_ONLY",
                                tool=tool)
            return (ExecuteResult(ok=False, action=action, verdict=verdict,
                                  blocked="trading_mode=READ_ONLY"), False)

        verdict = self.policy.evaluate(action)
        self.auditor.record_verdict(actor="jayu", verdict=verdict, tool=tool)
        if verdict.decision == Decision.DENY:
            return (ExecuteResult(ok=False, action=action, verdict=verdict,
                                  blocked="política deniega la acción"), False)

        if verdict.decision == Decision.ASK:
            autonomous_review = (
                effective == TradingMode.AUTONOMOUS_TRADING
                and verdict.classification == Classification.REVIEW
            )
            if autonomous_review:
                # ejecución autónoma permitida para REVIEW (config lo autorizó)
                final = Verdict(action, verdict.classification,
                                Decision.ALLOW,
                                "AUTONOMOUS_TRADING autoriza REVIEW sin confirmar")
                self.auditor.record_verdict(actor="jayu", verdict=final,
                                            tool=tool)
                return (None, True)
            if interactive and (user_ok or self.confirmer(
                    f"Confirmación de ejecución requerida para '{action}' "
                    f"({tool}). ¿Proceder? (S/n)")):
                final = Verdict(action, verdict.classification,
                                Decision.ALLOW, "confirmado por el usuario")
                self.auditor.record_verdict(actor="jayu", verdict=final,
                                            tool=tool)
                return (None, True)
            return (ExecuteResult(ok=False, action=action, verdict=verdict,
                                  blocked="falta confirmación humana"), False)

        return (None, True)

    def _send(self, request: dict[str, Any], tool: str) -> dict[str, Any]:
        """Ejecuta order_send y estructura la respuesta (auditable)."""
        self.connector._ensure()
        mt5 = self.connector._mt5
        result = mt5.order_send(request)
        if result is None:
            raise MT5Error("order_send devolvió None.",
                           hint=str(self.connector.last_error()))
        done = getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        d = _result_dict(result)
        if d.get("retcode") not in (done, None):
            self.auditor.record(
                actor="jayu", action=f"mt5.{tool}",
                classification=Classification.REVIEW,
                decision=Decision.DENY,
                reason=f"broker rechazó (retcode={d.get('retcode')} "
                       f"{d.get('comment')})",
                tool=f"mt5.{tool}", result=d)
        return d

    # ------------------------------------------------------------------
    # Órdenes de mercado
    # ------------------------------------------------------------------
    def market_order(
        self, symbol: str, volume: float, side: str, *,
        sl: float | None = None, tp: float | None = None,
        deviation: int | None = None, magic: int | None = None,
        comment: str | None = None,
        interactive: bool = True, user_ok: bool = False,
    ) -> ExecuteResult:
        blocked, ok = self._authorize(
            "mt5.market_order", "market_order", interactive=interactive,
            user_ok=user_ok)
        if blocked:
            return blocked
        mt5 = self.connector._mt5
        side = str(side).upper()
        otype = (mt5.ORDER_TYPE_BUY if side in ("BUY", "LONG", "COMPRA")
                 else mt5.ORDER_TYPE_SELL if side in ("SELL", "SHORT", "VENTA")
                 else None)
        if otype is None:
            return ExecuteResult(ok=False, action="mt5.market_order",
                                 verdict=None,
                                 reason=f"side inválido: {side} (BUY|SELL)",
                                 blocked="parámetros")
        quote = self.connector.quote(symbol)
        price = quote.get("ask") if otype == mt5.ORDER_TYPE_BUY else quote.get("bid")
        request = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
            "symbol": symbol, "volume": float(volume), "type": otype,
            "price": float(price), "sl": sl, "tp": tp,
            "deviation": int(deviation or self._exec_cfg("deviation_points", 20)),
            "magic": int(magic or self._exec_cfg("default_magic", 7654321)),
            "comment": comment or self._exec_cfg("default_comment", "JAYU"),
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
            "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1),
        }
        data = self._send(request, "market_order")
        ok_res = data.get("retcode") == getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        self.auditor.record(actor="jayu", action="mt5.market_order",
                            classification=Classification.REVIEW,
                            decision=Decision.ALLOW if ok_res else Decision.DENY,
                            reason="order_send ejecutada" if ok_res
                            else "order_send rechazada",
                            tool="mt5.market_order", result=data)
        return ExecuteResult(ok=ok_res, action="mt5.market_order",
                             verdict=None, data=data,
                             reason=data.get("comment", ""))

    # ------------------------------------------------------------------
    # Órdenes pendientes
    # ------------------------------------------------------------------
    def pending_order(
        self, symbol: str, volume: float, kind: str, price: float, *,
        sl: float | None = None, tp: float | None = None,
        magic: int | None = None, comment: str | None = None,
        interactive: bool = True, user_ok: bool = False,
    ) -> ExecuteResult:
        blocked, ok = self._authorize(
            "mt5.pending_order", "pending_order", interactive=interactive,
            user_ok=user_ok)
        if blocked:
            return blocked
        mt5 = self.connector._mt5
        kind_map = {
            "BUY_LIMIT": "ORDER_TYPE_BUY_LIMIT",
            "SELL_LIMIT": "ORDER_TYPE_SELL_LIMIT",
            "BUY_STOP": "ORDER_TYPE_BUY_STOP",
            "SELL_STOP": "ORDER_TYPE_SELL_STOP",
            "BUY_STOP_LIMIT": "ORDER_TYPE_BUY_STOP_LIMIT",
            "SELL_STOP_LIMIT": "ORDER_TYPE_SELL_STOP_LIMIT",
        }
        attr = kind_map.get(str(kind).upper())
        if not attr or not hasattr(mt5, attr):
            return ExecuteResult(ok=False, action="mt5.pending_order",
                                 verdict=None, blocked="parámetros",
                                 reason=f"kind inválido: {kind}")
        request = {
            "action": getattr(mt5, "TRADE_ACTION_PENDING", 5),
            "symbol": symbol, "volume": float(volume),
            "type": getattr(mt5, attr), "price": float(price),
            "sl": sl, "tp": tp,
            "magic": int(magic or self._exec_cfg("default_magic", 7654321)),
            "comment": comment or self._exec_cfg("default_comment", "JAYU"),
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
            "type_filling": getattr(mt5, "ORDER_FILLING_RETURN", 3),
        }
        data = self._send(request, "pending_order")
        ok_res = data.get("retcode") == getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        self.auditor.record(actor="jayu", action="mt5.pending_order",
                            classification=Classification.REVIEW,
                            decision=Decision.ALLOW if ok_res else Decision.DENY,
                            reason="order_send ejecutada" if ok_res
                            else "order_send rechazada",
                            tool="mt5.pending_order", result=data)
        return ExecuteResult(ok=ok_res, action="mt5.pending_order",
                             verdict=None, data=data,
                             reason=data.get("comment", ""))

    # ------------------------------------------------------------------
    # Modificación y cierre
    # ------------------------------------------------------------------
    def modify_position(self, ticket: int, *, sl: float | None = None,
                        tp: float | None = None,
                        interactive: bool = True, user_ok: bool = False,
                        ) -> ExecuteResult:
        return self._modify("mt5.modify_position", "modify_position", ticket,
                            sl=sl, tp=tp, interactive=interactive,
                            user_ok=user_ok)

    def modify_pending(self, ticket: int, *, sl: float | None = None,
                       tp: float | None = None, price: float | None = None,
                       interactive: bool = True, user_ok: bool = False,
                       ) -> ExecuteResult:
        return self._modify("mt5.modify_order", "modify_pending", ticket,
                            sl=sl, tp=tp, price=price, interactive=interactive,
                            user_ok=user_ok, pending=True)

    def _modify(self, action: str, tool: str, ticket: int, *,
                sl: float | None = None, tp: float | None = None,
                price: float | None = None, pending: bool = False,
                interactive: bool, user_ok: bool) -> ExecuteResult:
        blocked, ok = self._authorize(action, tool, interactive=interactive,
                                      user_ok=user_ok)
        if blocked:
            return blocked
        mt5 = self.connector._mt5
        request = {"action": getattr(mt5, "TRADE_ACTION_SLTP", 6)
                   if not pending else getattr(mt5, "TRADE_ACTION_MODIFY", 2),
                   "ticket": int(ticket)}
        if not pending:
            pos = self._find_position(ticket)
            if pos is None:
                return ExecuteResult(ok=False, action=action, verdict=None,
                                     blocked="posición no encontrada",
                                     reason=f"ticket {ticket} no existe")
            request["symbol"] = pos.get("symbol")
        else:
            ord_pending = self._find_pending(ticket)
            if ord_pending is None:
                return ExecuteResult(ok=False, action=action, verdict=None,
                                     blocked="orden pendiente no encontrada",
                                     reason=f"ticket {ticket} no existe")
            request["symbol"] = ord_pending.get("symbol")
            if price is not None:
                request["price"] = float(price)
        if sl is not None:
            request["sl"] = float(sl)
        if tp is not None:
            request["tp"] = float(tp)
        if sl is None and tp is None and price is None:
            return ExecuteResult(ok=False, action=action, verdict=None,
                                 blocked="parámetros",
                                 reason="SL, TP o precio requeridos")
        data = self._send(request, tool)
        ok_res = data.get("retcode") == getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        self.auditor.record(actor="jayu", action=action,
                            classification=Classification.REVIEW,
                            decision=Decision.ALLOW if ok_res else Decision.DENY,
                            reason="modificado" if ok_res else "rechazado",
                            tool=f"mt5.{tool}", result=data)
        return ExecuteResult(ok=ok_res, action=action, verdict=None, data=data,
                             reason=data.get("comment", ""))

    def close_position(self, ticket: int, *, deviation: int | None = None,
                       interactive: bool = True, user_ok: bool = False,
                       ) -> ExecuteResult:
        blocked, ok = self._authorize(
            "mt5.close_position", "close_position", interactive=interactive,
            user_ok=user_ok)
        if blocked:
            return blocked
        mt5 = self.connector._mt5
        pos = self._find_position(ticket)
        if pos is None:
            return ExecuteResult(ok=False, action="mt5.close_position",
                                 verdict=None, blocked="posición no encontrada")
        volume = float(pos.get("volume", 0.0))
        # cerrar: vender si está comprada, comprar si está vendida
        otype = (mt5.ORDER_TYPE_SELL
                 if int(pos.get("type", 0)) == 0 else mt5.ORDER_TYPE_BUY)
        quote = self.connector.quote(pos.get("symbol"))
        price = quote.get("bid") if otype == mt5.ORDER_TYPE_SELL else quote.get("ask")
        request = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
            "symbol": pos.get("symbol"), "volume": volume, "type": otype,
            "position": int(ticket), "price": float(price),
            "deviation": int(deviation or self._exec_cfg("deviation_points", 20)),
            "magic": int(pos.get("magic", 0)),
            "comment": self._exec_cfg("default_comment", "JAYU") + " CLOSE",
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
            "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1),
        }
        data = self._send(request, "close_position")
        ok_res = data.get("retcode") == getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        self.auditor.record(actor="jayu", action="mt5.close_position",
                            classification=Classification.REVIEW,
                            decision=Decision.ALLOW if ok_res else Decision.DENY,
                            reason="cerrada" if ok_res else "rechazada",
                            tool="mt5.close_position", result=data)
        return ExecuteResult(ok=ok_res, action="mt5.close_position",
                             verdict=None, data=data,
                             reason=data.get("comment", ""))

    def close_all(self, *, interactive: bool = True,
                  user_ok: bool = False) -> ExecuteResult:
        """Cierra TODAS las posiciones abiertas. DANGEROUS."""
        blocked, ok = self._authorize("mt5.close_all", "close_all",
                                      interactive=interactive, user_ok=user_ok)
        if blocked:
            return blocked
        positions = self.connector.positions()
        results = []
        all_ok = True
        for pos in positions:
            # La confirmación humana ya cubrió close_all (DANGEROUS):
            # la sub-acción de cierre individual queda cubierta por ella.
            res = self.close_position(int(pos["ticket"]),
                                      interactive=True, user_ok=True)
            results.append({"ticket": pos["ticket"], "ok": res.ok,
                            "comment": pos.get("comment")})
            all_ok = all_ok and res.ok
        data = {"closed": results, "count": len(positions)}
        self.auditor.record(actor="jayu", action="mt5.close_all",
                            classification=Classification.DANGEROUS,
                            decision=Decision.ALLOW if all_ok else Decision.DENY,
                            reason="cierre total ejecutado",
                            tool="mt5.close_all", result=data)
        return ExecuteResult(ok=all_ok, action="mt5.close_all", verdict=None,
                             data=data)

    # ------------------------------------------------------------------
    # Gestión de riesgo de posiciones (break-even / trailing)
    # ------------------------------------------------------------------
    def breakeven(self, ticket: int, *, offset_points: float = 5.0,
                  interactive: bool = True, user_ok: bool = False,
                  ) -> ExecuteResult:
        blocked, ok = self._authorize("mt5.breakeven", "breakeven",
                                      interactive=interactive, user_ok=user_ok)
        if blocked:
            return blocked
        pos = self._find_position(ticket)
        if pos is None:
            return ExecuteResult(ok=False, action="mt5.breakeven",
                                 verdict=None, blocked="posición no encontrada")
        info = self.connector.symbol_info(pos.get("symbol"))
        point = float(info.get("point", 0.0) or 0.0)
        offset = float(offset_points) * point
        entry = float(pos.get("price_open"))
        side_buy = int(pos.get("type", 0)) == 0
        be = entry + offset if side_buy else entry - offset
        return self.modify_position(ticket, sl=be, tp=float(pos.get("tp"))
                                    if pos.get("tp") else None,
                                    interactive=interactive, user_ok=user_ok)

    def trailing(self, symbol: str, *, trail_points: float, step_points: float = 0.0,
                 interactive: bool = True, user_ok: bool = False,
                 ) -> ExecuteResult:
        blocked, ok = self._authorize("mt5.trailing", "trailing",
                                      interactive=interactive, user_ok=user_ok)
        if blocked:
            return blocked
        positions = self.connector.positions(symbol=symbol)
        if not positions:
            return ExecuteResult(ok=False, action="mt5.trailing", verdict=None,
                                 blocked=f"sin posiciones en {symbol}")
        info = self.connector.symbol_info(symbol)
        point = float(info.get("point", 0.0) or 0.0)
        quote = self.connector.quote(symbol)
        results = []
        for pos in positions:
            side_buy = int(pos.get("type", 0)) == 0
            current_sl = float(pos.get("sl") or 0.0)
            if side_buy:
                new_sl = float(quote.get("bid")) - trail_points * point
                step = step_points * point
                improved = (new_sl - current_sl) >= step and new_sl > current_sl
            else:
                new_sl = float(quote.get("ask")) + trail_points * point
                step = step_points * point
                improved = (current_sl - new_sl) >= step and new_sl < current_sl
            if improved:
                # autorización ya concedida por `trailing` (acción padre)
                res = self.modify_position(int(pos["ticket"]), sl=new_sl,
                                           interactive=True, user_ok=True)
                results.append({"ticket": pos["ticket"], "moved": True,
                                "sl": round(new_sl, 6), "ok": res.ok})
            else:
                results.append({"ticket": pos["ticket"], "moved": False,
                                "sl": round(current_sl, 6)})
        data = {"results": results, "symbol": symbol}
        self.auditor.record(actor="jayu", action="mt5.trailing",
                            classification=Classification.REVIEW,
                            decision=Decision.ALLOW,
                            reason="trailing stop procesado",
                            tool="mt5.trailing", result=data)
        return ExecuteResult(ok=True, action="mt5.trailing", verdict=None,
                             data=data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _exec_cfg(self, key: str, default: Any) -> Any:
        return self.trading_conf.get("execution", {}).get(key, default)

    def _find_position(self, ticket: int) -> dict[str, Any] | None:
        for pos in self.connector.positions():
            if int(pos.get("ticket")) == int(ticket):
                return pos
        return None

    def _find_pending(self, ticket: int) -> dict[str, Any] | None:
        for order in self.connector.orders():
            if int(order.get("ticket")) == int(ticket):
                return order
        return None


def _result_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "_asdict"):
        base = {k: v for k, v in result._asdict().items()}
    elif isinstance(result, dict):
        base = dict(result)
    else:
        base = {"retcode": getattr(result, "retcode", None),
                "comment": getattr(result, "comment", None),
                "order": getattr(result, "order", None),
                "deal": getattr(result, "deal", None),
                "price": getattr(result, "price", None),
                "volume": getattr(result, "volume", None),
                "request": getattr(result, "request", None)}
    # limpiar request nested para logs legibles
    req = base.pop("request", None)
    if isinstance(req, dict):
        base["request"] = {k: v for k, v in req.items()}
    elif req is not None:
        base["request"] = repr(req)
    return base