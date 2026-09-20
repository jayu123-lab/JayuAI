"""Skill: market_governor (FASE 8 — multi-agente de mercado).

El governor coordina la cadena researcher -> risk_manager -> governor,
emite una DECISIÓN (dirección + convicción + razones) y PROPUESTAS.

  - `run(...)`     (SAFE)  -> análisis multi-agente. NUNCA ejecuta.
  - `execute(proposal_id)` (REVIEW) -> ejecuta SOLO una propuesta emitida por
    `run`, a través de MT5Executor (política + modo trading + auditoría).

Honestidad: sin terminal MT5, `run` devuelve ok=False con error explícito.
No se simulan decisiones: la skill está registrada por el orquestador con el
connector/executor vivos.
"""

from __future__ import annotations

from typing import Any, Callable

from ...agents.market import MarketGovernor, MarketResearcher, RiskManager
from ...market.analyzer import MarketAnalyzer
from ...mt5.connector import MT5Error
from ..base import Skill


def make_market_governor_skill(get_connector, get_executor, get_sizer,
                               get_trading_conf) -> Skill:
    # Registro interno de propuestas (id -> propuesta) entre run y execute.
    pending: dict[str, dict[str, Any]] = {}

    def _cfg() -> dict[str, Any]:
        conf = get_trading_conf() or {}
        governor_cfg = dict(conf.get("governor") or {})
        threshold = int(governor_cfg.pop("threshold", 2) or 2)
        return governor_cfg, threshold

    def _governor() -> MarketGovernor:
        conn = get_connector()
        conf = get_trading_conf() or {}
        governor_cfg, threshold = _cfg()
        researcher = MarketResearcher(
            lambda s, tf, cnt: MarketAnalyzer(conn).analyze(s, tf, cnt))
        risk_manager = RiskManager(conn, get_sizer(),
                                   conf.get("risk") or {})
        return MarketGovernor(researcher, risk_manager,
                              threshold=threshold, cfg=governor_cfg)

    def run(symbol: str = "XAUUSD", timeframe: str = "H1",
            count: int = 400) -> dict[str, Any]:
        try:
            out = _governor().run({"symbol": symbol,
                                   "timeframe": timeframe,
                                   "count": count})
        except MT5Error as exc:
            return _err(exc)
        # Las propuestas solo son ejecutables tras el run más reciente.
        pending.clear()
        for proposal in out.get("proposals", []):
            pending[proposal["proposal_id"]] = proposal
        return out

    def execute(proposal_id: str = "", **kw) -> dict[str, Any]:
        authorized = kw.pop("_jayu_authorized", False)
        interactive = kw.pop("_jayu_interactive", False)
        prop = pending.get(proposal_id)
        if not prop:
            return {"ok": False,
                    "error": "Propuesta no encontrada o caducada. "
                             "Ejecuta 'run' de nuevo."}
        if prop.get("used"):
            return {"ok": False, "error": "Propuesta ya consumida."}
        if prop.get("action") != "market_order":
            return {"ok": False,
                    "error": f"Acción no soportada por el governor: "
                             f"{prop.get('action')!r}"}
        params = prop["params"]
        try:
            res = get_executor().market_order(
                symbol=params["symbol"], volume=params["volume"],
                side=params["side"], sl=params.get("sl"),
                tp=params.get("tp"),
                interactive=interactive, user_ok=authorized)
        except MT5Error as exc:
            return _err(exc)
        out = res.as_dict()
        out["trading_mode"] = get_executor().mode.value
        if getattr(res, "blocked", None):
            out["blocked_reason"] = res.blocked
        out["proposal_id"] = proposal_id
        out["proposal"] = {k: v for k, v in prop.items()
                           if k not in ("params",)}
        if res.ok and not getattr(res, "blocked", None):
            prop["used"] = True
        return out

    return Skill(
        name="market_governor",
        description="Multi-agente de mercado: researcher + risk_manager + "
                    "governor emiten decisión y propuestas (NUNCA ejecuta "
                    "sin confirmación humana).",
        category="market",
        tools={"run": run, "execute": execute},
        permission_actions=["market.governor", "mt5.market_order"],
        tool_actions={"run": "market.governor",
                      "execute": "mt5.market_order"},
        version="0.1.0",
    )


def _err(e: MT5Error) -> dict[str, Any]:
    return {"ok": False, "error": str(e), "hint": getattr(e, "hint", "")}