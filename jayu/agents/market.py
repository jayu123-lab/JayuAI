"""Agentes de mercado (Fase 8): researcher, risk_manager y governor.

El GOVERNOR coordina la cadena y DECIDE, pero NUNCA ejecuta: emite propuestas
(REVIEW) que el orquestador solo ejecuta por la ruta protegida existente.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from ..mt5.connector import MT5Error
from .base import Agent, AgentResult

DEFAULT_GOVERNOR_CFG = {
    "propose_trades": True,
    "conviction_min": 0.5,
    "take_profit_rr": 1.5,
    "sl_fallback_atr_mult": 1.5,
}


class MarketResearcher(Agent):
    """Agente 1: analiza el mercado y devuelve un resumen accionable."""

    role = "investigador de mercado"
    name = "researcher"
    tools = ["market_intelligence.analyze"]

    def __init__(self, analyze_fn: Callable[[str, str, int], dict[str, Any]],
                 **kw) -> None:
        super().__init__(**kw)
        self.analyze_fn = analyze_fn

    def run(self, task: dict[str, Any]) -> AgentResult:
        symbol = task.get("symbol", "XAUUSD")
        timeframe = task.get("timeframe", "H1")
        count = int(task.get("count", 400))
        try:
            report = self.analyze_fn(symbol, timeframe, count)
        except MT5Error as exc:
            return AgentResult(self.name, "Análisis de mercado", False,
                               error=str(exc))
        if not report.get("ok"):
            return AgentResult(self.name, "Análisis de mercado", False,
                               error=report.get("error",
                                                "análisis no disponible"))
        structure = report.get("structure", {})
        indicators = report.get("indicators", {})
        smc = report.get("smc", {})
        summary = {
            "bias_direction": report.get("bias", {}).get("direction"),
            "bias_score": report.get("bias", {}).get("score", 0),
            "bias_reasons": report.get("bias", {}).get("reasons", []),
            "trend": structure.get("trend"),
            "rsi14": indicators.get("rsi14"),
            "atr14": indicators.get("atr14"),
            "atr14_pct": indicators.get("atr14_pct"),
            "last_swing_high": (structure.get("last_swing_high") or {}).get(
                "price"),
            "last_swing_low": (structure.get("last_swing_low") or {}).get(
                "price"),
            "last_close": report.get("last_candle", {}).get("close"),
            "fvgs": len(smc.get("fvgs") or []),
            "order_blocks": len(smc.get("order_blocks") or []),
            "quote": report.get("quote"),
        }
        return AgentResult(self.name, "Análisis de mercado", True,
                           summary=summary)


class RiskManager(Agent):
    """Agente 2: valida el riesgo de un plan (lote, spread, posiciones,
    pérdida diaria). NUNCA dimensiona creación: solo sugiere y advierte."""

    role = "gestor de riesgo"
    name = "risk_manager"
    tools = ["mt5.quote", "mt5.history", "mt5.positions_read", "mt5.sizer"]

    def __init__(self, connector, sizer,
                 risk_conf: dict[str, Any] | None = None, **kw) -> None:
        super().__init__(**kw)
        self.connector = connector
        self.sizer = sizer
        self.risk_conf = risk_conf or {}

    def run(self, task: dict[str, Any]) -> AgentResult:
        symbol = task.get("symbol", "XAUUSD")
        research = (task.get("research") or {}).get("summary") or {}
        plan = task.get("plan") or {}
        warnings: list[str] = []
        risk_ok = True

        entry = plan.get("entry") or research.get("last_close")
        sl = plan.get("sl")
        side = plan.get("side")

        # --- spread ----------------------------------------------------
        spread_pts = None
        try:
            quote = self.connector.quote(symbol)
            spread_pts = quote.get("spread_points")
        except MT5Error as exc:
            warnings.append(f"spread no consultado: {exc}")
        thr = self.risk_conf.get("max_spread_threshold")
        if (thr is not None and spread_pts is not None
                and spread_pts > thr):
            warnings.append(f"Spread {spread_pts} pts supera el límite ({thr}).")
            risk_ok = False

        # --- dimensionado de lote ---------------------------------------
        max_volume = 0.0
        if side and entry and sl:
            try:
                sz = self.sizer.lot_size(symbol, entry_price=entry,
                                         stop_loss=sl)
            except MT5Error as exc:
                return AgentResult(self.name, "Validación de riesgo", False,
                                   error=str(exc))
            max_volume = sz.get("suggested_volume") or 0.0
            if not sz.get("ok"):
                warnings.append(sz.get("error", "no se pudo dimensionar"))
                risk_ok = False
            warnings.extend(sz.get("warnings") or [])
        else:
            warnings.append("Falta entrada/SL/SL mínimo para dimensionar lote.")

        # --- posiciones abiertas en el símbolo ---------------------------
        open_on_symbol = 0
        try:
            open_on_symbol = len(self.connector.positions(symbol=symbol))
        except MT5Error as exc:
            warnings.append(str(exc))
        max_open = self.risk_conf.get("max_open_positions")
        if max_open and open_on_symbol >= max_open:
            warnings.append(
                f"Ya hay {open_on_symbol} posición(es) abierta(s) en "
                f"{symbol} (máx {max_open}).")
            risk_ok = False

        # --- pérdida diaria ----------------------------------------------
        daily_loss = 0.0
        deals_seen = 0
        try:
            hist = self.connector.history(days=1, symbol=symbol)
            deals = hist.get("deals") or []
            deals_seen = len(deals)
            loss = sum(float(d.get("profit", 0.0) or 0.0) for d in deals)
            daily_loss = max(0.0, -loss)
        except MT5Error:
            pass
        max_loss_pct = self.risk_conf.get("max_daily_loss_pct")
        if max_loss_pct and deals_seen:
            try:
                acc = self.connector.account_info()
                balance = acc.get("balance", 0.0) or 0.0
                if balance and daily_loss >= balance * max_loss_pct / 100.0:
                    warnings.append(
                        f"Pérdida diaria {daily_loss:.2f}$ >= "
                        f"{max_loss_pct}% del balance.")
                    risk_ok = False
            except MT5Error:
                pass

        summary = {
            "risk_ok": risk_ok,
            "warnings": warnings,
            "max_volume": round(max_volume, 2),
            "open_positions_on_symbol": open_on_symbol,
            "spread_points": spread_pts,
            "daily_loss_usd": round(daily_loss, 2),
            "deals_seen_today": deals_seen,
            "plan": {"side": side, "entry": entry, "sl": sl},
        }
        return AgentResult(self.name, "Validación de riesgo", True,
                           summary=summary)


class MarketGovernor(Agent):
    """Agente 3: coordina researcher + risk_manager, agrega y DECIDE.

    Salida: dict con la cadena de agentes, la decisión (dirección, convicción,
    razones), el plan validado y las propuestas. NUNCA ejecuta.
    """

    role = "gobernador de mercado"
    name = "governor"
    tools = ["market_intelligence.analyze", "mt5.sizer", "mt5.quote"]

    def __init__(self, researcher: MarketResearcher,
                 risk_manager: RiskManager, *,
                 threshold: int = 2,
                 cfg: dict[str, Any] | None = None, **kw) -> None:
        super().__init__(**kw)
        self.researcher = researcher
        self.risk_manager = risk_manager
        self.threshold = max(1, int(threshold))
        self.cfg = {**DEFAULT_GOVERNOR_CFG, **(cfg or {})}

    # ------------------------------------------------------------------
    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        symbol = task.get("symbol", "XAUUSD")
        timeframe = task.get("timeframe", "H1")
        count = int(task.get("count", 400))

        chain: list[dict[str, Any]] = []
        res_researcher = self.researcher.run(task)
        chain.append(res_researcher.as_dict())
        if not res_researcher.ok:
            return self._result(symbol, timeframe, chain,
                                research={}, plan={}, risk=None)

        research = res_researcher.summary
        plan = self._build_plan(research)
        risk_task = {"symbol": symbol, "research": res_researcher.as_dict(),
                     "plan": plan}
        res_risk = self.risk_manager.run(risk_task)
        chain.append(res_risk.as_dict())

        return self._result(symbol, timeframe, chain, research=research,
                            plan=plan, risk=res_risk.summary)

    # ------------------------------------------------------------------
    def _result(self, symbol: str, timeframe: str, chain: list[dict], *,
                research: dict, plan: dict,
                risk: dict[str, Any] | None) -> dict[str, Any]:
        ok = bool(chain) and all(c["ok"] for c in chain) and risk is not None
        risk_ok = bool(risk and risk.get("risk_ok", False))
        warnings = list(risk.get("warnings", []) if risk else [])
        max_volume = float(risk.get("max_volume", 0.0) if risk else 0.0)

        direction = research.get("bias_direction") or "NEUTRAL"
        score = int(research.get("bias_score", 0))
        reasons = list(research.get("bias_reasons", []))
        conviction = min(1.0, abs(score) / max(1, self.threshold + 1))

        proposals: list[dict[str, Any]] = []
        can_propose = (
            ok and self.cfg.get("propose_trades")
            and direction in ("BULLISH", "BEARISH")
            and risk_ok and max_volume > 0
            and plan.get("entry") and plan.get("sl")
            and conviction >= self.cfg.get("conviction_min", 0.0)
        )
        if can_propose:
            params = {
                "symbol": symbol,
                "volume": round(max_volume, 2),
                "side": plan["side"],
                "sl": plan["sl"],
                "tp": plan["tp"],
            }
            proposals = [{
                "proposal_id": self._proposal_id(params),
                "action": "market_order",
                "permission": "mt5.market_order",
                "risk_class": "REVIEW",
                "params": params,
                "reason": (f"{direction} (score {score}); riesgo validado; "
                           f"volumen máx. {max_volume:.2f}"),
            }]

        return {
            "ok": ok,
            "symbol": symbol,
            "timeframe": timeframe,
            "chain": {"order": [a["agent"] for a in chain],
                      "agents": chain},
            "decision": {
                "direction": direction,
                "score": score,
                "threshold": self.threshold,
                "conviction": round(conviction, 2),
                "reasons": reasons,
                "risk_ok": risk_ok,
                "warnings": warnings,
                "plan": {
                    "side": plan.get("side") if can_propose else None,
                    "entry": plan.get("entry") if can_propose else None,
                    "sl": plan.get("sl") if can_propose else None,
                    "tp": plan.get("tp") if can_propose else None,
                },
                "proposed_volume": round(max_volume, 2),
            },
            "proposals": proposals,
            "executed": [],
            "note": ("El governor NUNCA ejecuta. Las propuestas requieren "
                     "política + modo de trading + confirmación humana."),
        }

    # ------------------------------------------------------------------
    def _build_plan(self, r: dict) -> dict[str, Any]:
        direction = r.get("bias_direction")
        close = r.get("last_close")
        if not close or direction not in ("BULLISH", "BEARISH"):
            return {"side": direction, "entry": close, "sl": None,
                    "tp": None}
        atr = r.get("atr14")
        mult = self.cfg.get("sl_fallback_atr_mult", 1.5)
        rr = self.cfg.get("take_profit_rr", 1.5)
        if direction == "BULLISH":
            side = "BUY"
            sl = r.get("last_swing_low")
            if sl is None or sl >= close:
                sl = close - atr * mult if atr else None
            tp = None
            if sl:
                risk = close - sl
                if risk > 0:
                    tp = close + risk * rr
            return {"side": side, "entry": close,
                    "sl": round(sl, 6) if sl else None,
                    "tp": round(tp, 6) if tp else None}
        side = "SELL"
        sl = r.get("last_swing_high")
        if sl is None or sl <= close:
            sl = close + atr * mult if atr else None
        tp = None
        if sl:
            risk = sl - close
            if risk > 0:
                tp = close - risk * rr
        return {"side": side, "entry": close,
                "sl": round(sl, 6) if sl else None,
                "tp": round(tp, 6) if tp else None}

    @staticmethod
    def _proposal_id(params: dict[str, Any]) -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]