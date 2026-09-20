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


# ----------------------------------------------------------------------
# Analistas especialistas (Fase 8 ampliada): macro y sentimiento.
# Ambos EMITEN VOTOS (-100..+100) sobre XAUUSD/oro desde datos reales o
# contextuales. NUNCA inventan datos: sin insumos votan NEUTRAL con nota
# honesta ("sin datos").
# ----------------------------------------------------------------------

# Léxico oro-específico para el voto de sentimiento (análisis léxico).
_SENT_POS = (
    "oro sube", "respaldado", "al alza", "máximos", "récord", "refugio",
    "recorte", "dovish", "dólar débil", "debilidad del dólar", "compra",
    "acumula", "bancos centrales compran", "tasas bajan", "inflación alta",
    "geopolítico", "riesgo de recesión", "demanda", "flujos de entrada",
    "tasas reales negativas",
)
_SENT_NEG = (
    "oro cae", "presión", "a la baja", "pérdidas", "dólar fuerte",
    "vende", "ventas", "salidas", "hawkish", "suben las tasas",
    "tasas al alza", "rendimientos suben", "presiona", "correctivo",
    "débil demanda", "reversión", "toma de beneficios",
)


class MacroAnalyst(Agent):
    """Especialista macro: FED, tasas reales, bonos, DXY y bancos centrales.

    Fuentes de datos (con preferencia real):
      1. `macro_context` inyectado en la tarea (datos/noticias reales que el
         usuario o el LLM aportan: expectativas de recortes, DXY, bonos...).
      2. Quotes en vivo de DXY/US10Y si el broker los ofrece (quote_fn).
      3. Marco de drivers de la KB del oro (jayu.kb.gold) como contexto.

    Vota NEUTRAL si no hay datos en vivo/contextuales (honesto, no adivina).
    """

    role = "analista macro (FED, tasas reales, DXY, bonos, bancos centrales)"
    name = "macro_analyst"
    tools = ["gold.context", "mt5.quote"]

    def __init__(self, *, kb_fn: Callable[[], dict[str, Any]] | None = None,
                 quote_fn: Callable[[str], dict[str, Any]] | None = None,
                 **kw) -> None:
        super().__init__(**kw)
        self.kb_fn = kb_fn or (lambda: {"ok": False,
                                        "error": "KB de oro no conectada"})
        self.quote_fn = quote_fn

    # ------------------------------------------------------------------
    def run(self, task: dict[str, Any]) -> AgentResult:
        # 1) contexto macro inyectado (datos reales aportados por el
        #    usuario/LLM) tiene prioridad; si viene sin clave "ok" se
        #    acepta tal cual (es dato externo, no un estado de conexión).
        ctx = task.get("macro_context")
        if isinstance(ctx, dict) and ctx:
            if "ok" not in ctx:
                ctx = {**ctx, "ok": True}
        else:
            ctx = None

        if ctx is None:
            try:
                kb = self.kb_fn()
            except Exception as exc:  # noqa: BLE001
                return AgentResult(self.name, "Análisis macro", False,
                                   error=str(exc))
            if isinstance(kb, dict) and kb.get("ok"):
                ctx = kb
            else:
                ctx = None

        if ctx is None:
            # Sin insumos reales -> voto NEUTRAL honesto (no se adivina).
            return AgentResult(self.name, "Análisis macro", True,
                               summary={"vote": 0, "direction": "NEUTRAL",
                                        "confidence": 0.0,
                                        "reasons": [
                                            "Sin datos macro en vivo ni "
                                            "contexto (DXY/bonos pendientes "
                                            "en este broker)."],
                                        "inputs": [],
                                        "data_status": "pendiente"})

        score = 0.0
        reasons: list[str] = []
        inputs: list[str] = []

        # --- expectativa de recortes/subidas (contexto) ---------------
        expectation = ctx.get("rate_expectation")  # "cuts" | "hikes" | None
        if expectation == "cuts":
            score += 50
            reasons.append("Expectativa de RECORTES de tipos -> tasas reales "
                           "a la baja, viento de cola para el oro.")
            inputs.append("recortes esperados")
        elif expectation == "hikes":
            score -= 45
            reasons.append("Expectativa de SUBIDAS de tipos -> oro bajo "
                           "presión (costo de oportunidad mayor).")
            inputs.append("subidas esperadas")

        infl = ctx.get("inflation_trend")  # "high" | "cooling" | "low"
        if infl == "high":
            score += 25
            reasons.append("Inflación alta: el oro funciona como reserva de "
                           "valor.")
            inputs.append("inflación alta")
        elif infl == "cooling":
            score -= 12
            reasons.append("Inflación enfriándose: algo menos de impulso "
                           "refugio.")
            inputs.append("inflación a la baja")

        cbb = ctx.get("central_bank_buying")  # "strong" | "low"
        if cbb == "strong":
            score += 20
            reasons.append("Bancos centrales acumulando oro (demanda "
                           "estructural).")
            inputs.append("compras de bancos centrales")
        elif cbb == "low":
            score -= 8
            reasons.append("Compras oficiales moderadas.")
            inputs.append("compras oficiales moderadas")

        # --- datos en vivo DXY / US10Y (si el broker los ofrece) -------
        # Señal normalizada: desviación respecto a un nivel neutro
        # (DXY 100, US10Y 4.0%), capada a ±3 puntos.
        if self.quote_fn is not None:
            for sym, base, weight in (("DXY", 100.0, -0.8),
                                      ("US10Y", 4.0, -0.6)):
                try:
                    q = self.quote_fn(sym)
                except Exception:  # noqa: BLE001
                    q = None
                if q and q.get("bid") is not None:
                    delta = float(q["bid"]) - base
                    score += weight * min(3.0, max(-3.0, delta))
                    inputs.append(f"{sym} en vivo")

        # --- neutralidad honesta si no hubo ninguna señal -------------
        if not inputs:
            return AgentResult(self.name, "Análisis macro", True,
                               summary={
                                   "vote": 0,
                                   "direction": "NEUTRAL",
                                   "confidence": 0.0,
                                   "reasons": [
                                       "Sin datos macro en vivo ni contexto "
                                       "(DXY/bonos pendientes en este broker)."],
                                   "inputs": [],
                                   "data_status": "pendiente",
                               })

        direction = ("BULLISH" if score >= 20 else
                     "BEARISH" if score <= -20 else "NEUTRAL")
        confidence = min(1.0, abs(score) / 60.0)
        return AgentResult(
            self.name, "Análisis macro", True,
            summary={"vote": round(score, 1), "direction": direction,
                     "confidence": round(confidence, 2),
                     "reasons": reasons, "inputs": inputs,
                     "data_status": "ok"})


class SentimentAnalyst(Agent):
    """Especialista en sentimiento: análisis léxico de titulares reales.

    `headlines`: lista de titulares/noticias (inyectadas desde web research
    o por el usuario). Si no hay titulares, vota NEUTRAL con nota honesta.
    """

    role = "analista de sentimiento (noticias)"
    name = "sentiment_analyst"
    tools = ["web.search"]

    def __init__(self, **kw) -> None:
        super().__init__(**kw)

    # ------------------------------------------------------------------
    def run(self, task: dict[str, Any]) -> AgentResult:
        headlines = [h for h in (task.get("headlines") or [])
                     if isinstance(h, str) and h.strip()]
        if not headlines:
            return AgentResult(self.name, "Análisis de sentimiento", True,
                               summary={
                                   "vote": 0, "direction": "NEUTRAL",
                                   "confidence": 0.0,
                                   "reasons": ["Sin titulares/noticias para "
                                               "analizar (honesto)."],
                                   "headlines_analizadas": 0,
                                   "data_status": "pendiente",
                               })
        pos = neg = 0
        pos_hits: list[str] = []
        neg_hits: list[str] = []
        for h in headlines:
            low = h.lower()
            if any(w in low for w in _SENT_POS):
                pos += 1
                pos_hits.append(h[:90])
            if any(w in low for w in _SENT_NEG):
                neg += 1
                neg_hits.append(h[:90])
        total = max(1, len(headlines))
        score = round((pos - neg) / total * 100.0, 1)
        direction = ("BULLISH" if score >= 25 else
                     "BEARISH" if score <= -25 else "NEUTRAL")
        confidence = min(1.0, abs(score) / 100.0)
        reasons: list[str] = []
        if pos_hits:
            reasons.append(f"{pos} titular(es) a favor: "
                           f"{pos_hits[0]!r}"
                           + (f" (+{len(pos_hits)-1} más)" if len(pos_hits) > 1
                              else ""))
        if neg_hits:
            reasons.append(f"{neg} titular(es) en contra: "
                           f"{neg_hits[0]!r}"
                           + (f" (+{len(neg_hits)-1} más)" if len(neg_hits) > 1
                              else ""))
        return AgentResult(
            self.name, "Análisis de sentimiento", True,
            summary={"vote": score, "direction": direction,
                     "confidence": round(confidence, 2),
                     "reasons": reasons,
                     "headlines_analizadas": len(headlines),
                     "positivos": pos, "negativos": neg,
                     "data_status": "ok"})


# ----------------------------------------------------------------------
# Governor (con votación ponderada de los especialistas)
# ----------------------------------------------------------------------
class MarketGovernor(Agent):
    """Agente 3: coordina researcher + risk_manager (+ analistas macro y de
    sentimiento), agrega los votos ponderados y DECIDE.

    Salida: dict con la cadena de agentes, la decisión (dirección, convicción,
    razones, votos por agente), el plan validado y las propuestas.
    NUNCA ejecuta.
    """

    role = "gobernador de mercado"
    name = "governor"
    tools = ["market_intelligence.analyze", "mt5.sizer", "mt5.quote"]

    def __init__(self, researcher: MarketResearcher,
                 risk_manager: RiskManager, *,
                 macro_analyst: MacroAnalyst | None = None,
                 sentiment_analyst: SentimentAnalyst | None = None,
                 weights: dict[str, float] | None = None,
                 threshold: int = 2,
                 cfg: dict[str, Any] | None = None, **kw) -> None:
        super().__init__(**kw)
        self.researcher = researcher
        self.risk_manager = risk_manager
        self.macro_analyst = macro_analyst
        self.sentiment_analyst = sentiment_analyst
        # Pesos de cada especialista en la decisión combinada.
        self.weights = {"technical": 1.0, "macro": 0.4, "sentiment": 0.25,
                        **(weights or {})}
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
                                research={}, plan={}, risk=None,
                                votes={}, combined=0)

        research = res_researcher.summary
        votes: dict[str, dict[str, Any]] = {}
        technical_score = int(research.get("bias_score", 0))
        votes["technical"] = {
            "vote": technical_score,
            "direction": research.get("bias_direction"),
            "confidence": round(min(1.0, abs(technical_score) /
                                    max(1, self.threshold + 1)), 2),
            "reasons": research.get("bias_reasons", []),
        }

        # --- especialistas: macro y sentimiento (votos ponderados) -------
        macro_vote = sentiment_vote = 0.0
        if self.macro_analyst is not None:
            res_macro = self.macro_analyst.run(
                {"macro_context": task.get("macro_context")})
            chain.append(res_macro.as_dict())
            if res_macro.ok:
                macro_vote = float(res_macro.summary.get("vote", 0.0))
                votes["macro"] = res_macro.summary
        if self.sentiment_analyst is not None:
            res_sent = self.sentiment_analyst.run(
                {"headlines": task.get("headlines") or []})
            chain.append(res_sent.as_dict())
            if res_sent.ok:
                sentiment_vote = float(res_sent.summary.get("vote", 0.0))
                votes["sentiment"] = res_sent.summary

        w_tech = float(self.weights.get("technical", 1.0))
        w_macro = float(self.weights.get("macro", 0.4))
        w_sent = float(self.weights.get("sentiment", 0.25))
        combined = round(technical_score * w_tech
                         + macro_vote * w_macro
                         + sentiment_vote * w_sent, 1)

        combined_dir = self._combined_direction(combined, self.threshold)
        plan = self._build_plan(research)
        if (combined_dir is not None
                and combined_dir != research.get("bias_direction")):
            # La coalición de especialistas domina al técnico: el plan se
            # construye conforme a la dirección combinada (transparente).
            plano = dict(research)
            plano["bias_direction"] = combined_dir
            plano["bias_score"] = combined
            plan = self._build_plan(plano)
        risk_task = {"symbol": symbol, "research": res_researcher.as_dict(),
                     "plan": plan}
        res_risk = self.risk_manager.run(risk_task)
        chain.append(res_risk.as_dict())

        return self._result(symbol, timeframe, chain, research=research,
                            plan=plan, risk=res_risk.summary,
                            votes=votes, combined=combined)

    # ------------------------------------------------------------------
    def _result(self, symbol: str, timeframe: str, chain: list[dict], *,
                research: dict, plan: dict,
                risk: dict[str, Any] | None,
                votes: dict[str, dict[str, Any]] | None = None,
                combined: float = 0.0) -> dict[str, Any]:
        # ok depende SOLO de los agentes nucleares (researcher + risk).
        # Los especialistas sin datos (macro/sentimiento) informan en
        # `decision.votes` pero no tumban el resultado.
        core = [a for a in chain if a.get("agent") in
                ("researcher", "risk_manager")]
        ok = bool(core) and all(c["ok"] for c in core) and risk is not None
        risk_ok = bool(risk and risk.get("risk_ok", False))
        warnings = list(risk.get("warnings", []) if risk else [])
        max_volume = float(risk.get("max_volume", 0.0) if risk else 0.0)

        votes = votes or {}
        has_analysts = bool(votes) and len(votes) > 1
        direction = research.get("bias_direction") or "NEUTRAL"
        score = combined if has_analysts else int(
            research.get("bias_score", 0))
        reasons = list(votes.get("technical", {}).get("reasons", []))
        for name in ("macro", "sentiment"):
            v = votes.get(name)
            if v:
                reasons.extend(v.get("reasons", []))
        if not has_analysts:
            reasons = list(research.get("bias_reasons", []))
        conviction = min(1.0, abs(score) / max(1, self.threshold + 1))

        # Dirección combinada solo si los especialistas la dominan (|score|)
        if has_analysts:
            combined_dir = self._combined_direction(score)
            if combined_dir is not None:
                direction = combined_dir

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
                "votes": votes,
                "weights": dict(self.weights),
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
    @staticmethod
    def _combined_direction(score: float, threshold: int = 2) -> str | None:
        """Dirección de la coalición cuando |score| es dominante."""
        if score >= max(1.5, threshold * 0.7):
            return "BULLISH"
        if score <= -max(1.5, threshold * 0.7):
            return "BEARISH"
        return None

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