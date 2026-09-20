"""FASE 8 — Tests del multi-agente de mercado (researcher/risk/governor)."""

from __future__ import annotations

import pytest

from jayu.agents.base import AgentResult
from jayu.agents.market import MarketGovernor, MarketResearcher, RiskManager
from jayu.mt5.connector import MT5Connector
from jayu.mt5.execution import TradingMode
from jayu.mt5.risk import PositionSizer
from tests.fakes import FakeMT5, sample_position

# ----------------------------------------------------------------------
# Ayudantes: agentes stub deterministas (unidad del governor)
# ----------------------------------------------------------------------


def _stub_researcher(summary: dict, *, ok: bool = True,
                     error: str = ""):
    class _Stub:
        name = "researcher"

        def run(self, task):
            return AgentResult("researcher", "Análisis de mercado", ok,
                               summary=summary, error=error)
    return _Stub()


def _stub_risk(summary: dict, *, ok: bool = True, error: str = ""):
    class _Stub:
        name = "risk_manager"

        def run(self, task):
            return AgentResult("risk_manager", "Validación de riesgo", ok,
                               summary=summary, error=error)
    return _Stub()


def _research(**overrides) -> dict:
    data = {"bias_direction": "BULLISH", "bias_score": 3,
            "bias_reasons": ["razón 1"], "last_close": 100.0, "atr14": 1.0,
            "last_swing_low": 98.0, "last_swing_high": 102.0}
    data.update(overrides)
    return data


def _risk(**overrides) -> dict:
    data = {"risk_ok": True, "warnings": [], "max_volume": 0.5}
    data.update(overrides)
    return data


# ----------------------------------------------------------------------
# Governor (unidad)
# ----------------------------------------------------------------------

def test_governor_bullish_propone():
    gov = MarketGovernor(_stub_researcher(_research()),
                         _stub_risk(_risk()), threshold=2, cfg={})
    out = gov.run({"symbol": "XAUUSD", "timeframe": "H1", "count": 100})
    assert out["ok"] is True
    assert out["chain"]["order"] == ["researcher", "risk_manager"]
    assert out["decision"]["direction"] == "BULLISH"
    assert out["decision"]["conviction"] == 1.0  # score 3 / (2+1)
    assert len(out["proposals"]) == 1
    p = out["proposals"][0]
    assert p["action"] == "market_order"
    assert p["risk_class"] == "REVIEW"
    assert p["permission"] == "mt5.market_order"
    assert p["params"]["side"] == "BUY"
    assert p["params"]["volume"] == 0.5
    assert p["params"]["sl"] == 98.0
    assert p["params"]["tp"] == 103.0  # 100 + (100-98)*1.5
    assert out["executed"] == []


def test_governor_neutral_no_propone():
    research = _research(bias_direction="NEUTRAL", bias_score=1,
                         bias_reasons=[], last_swing_low=None,
                         last_swing_high=None)
    out = MarketGovernor(_stub_researcher(research), _stub_risk(_risk()),
                         threshold=2, cfg={}).run({"symbol": "XAUUSD"})
    assert out["proposals"] == []
    assert out["decision"]["direction"] == "NEUTRAL"
    assert out["decision"]["risk_ok"] is True


def test_governor_riesgo_rechaza_propuesta():
    research = _research(bias_direction="BEARISH", bias_score=-3,
                         last_close=100.0, last_swing_high=102.0,
                         last_swing_low=None)
    risk = _risk(risk_ok=False, max_volume=0.0,
                 warnings=["pérdida diaria superada"])
    out = MarketGovernor(_stub_researcher(research), _stub_risk(risk),
                         threshold=2, cfg={}).run({"symbol": "XAUUSD"})
    assert out["proposals"] == []
    assert out["decision"]["risk_ok"] is False
    assert "pérdida diaria" in out["decision"]["warnings"][0]


def test_governor_researcher_falla_no_ejecuta_risk():
    out = MarketGovernor(
        _stub_researcher({}, ok=False, error="MT5 no disponible"),
        _stub_risk(_risk()), threshold=2, cfg={}).run({"symbol": "XAUUSD"})
    assert out["ok"] is False
    assert out["proposals"] == []
    # la cadena se interrumpe: el risk_manager NO se consulta
    assert [a["agent"] for a in out["chain"]["agents"]] == ["researcher"]
    assert out["chain"]["agents"][0]["error"] == "MT5 no disponible"


def test_governor_plan_sell_usa_swing_alto():
    research = _research(bias_direction="BEARISH", bias_score=-3,
                         last_close=100.0, last_swing_high=102.0,
                         last_swing_low=None)
    out = MarketGovernor(_stub_researcher(research), _stub_risk(_risk()),
                         threshold=2, cfg={}).run({"symbol": "XAUUSD"})
    p = out["proposals"][0]
    assert p["params"]["side"] == "SELL"
    assert p["params"]["sl"] == 102.0
    assert p["params"]["tp"] == 97.0  # 100 - 2*1.5


def test_proposal_id_es_estable():
    gov = MarketGovernor(_stub_researcher(_research()), _stub_risk(_risk()),
                         threshold=2, cfg={})
    a = gov.run({"symbol": "XAUUSD"})
    b = gov.run({"symbol": "XAUUSD"})
    assert (a["proposals"][0]["proposal_id"]
            == b["proposals"][0]["proposal_id"])


# ----------------------------------------------------------------------
# RiskManager con FakeMT5
# ----------------------------------------------------------------------

def _rm_fake(fake: FakeMT5, risk_conf: dict) -> RiskManager:
    conn = MT5Connector(mt5_module=fake)
    sizer = PositionSizer(conn, {"risk": {
        "max_position_pct_equity": 2.0}})
    return RiskManager(conn, sizer, risk_conf=risk_conf)


def test_risk_manager_dimensiona_lote_con_fake():
    rm = _rm_fake(FakeMT5(), {"max_open_positions": 5})
    task = {"symbol": "XAUUSD",
            "research": {"summary": {"last_close": 4380.0}},
            "plan": {"side": "BUY", "entry": 4380.0, "sl": 4360.0}}
    res = rm.run(task)
    assert res.ok and res.summary["risk_ok"] is True
    assert res.summary["max_volume"] > 0
    assert res.summary["open_positions_on_symbol"] == 0
    assert res.summary["deals_seen_today"] == 0


def test_risk_manager_rechaza_spread_y_posiciones():
    fake = FakeMT5(positions=[sample_position(symbol="XAUUSD")])
    rm = _rm_fake(fake, {"max_open_positions": 1,
                         "max_spread_threshold": 2})
    task = {"symbol": "XAUUSD",
            "research": {"summary": {}},
            "plan": {"side": "BUY", "entry": 4380.0, "sl": 4360.0}}
    res = rm.run(task)
    assert res.summary["risk_ok"] is False
    warnings = " ".join(res.summary["warnings"])
    assert "Spread 10" in warnings            # XAUUSD fake spread=10 > 2
    assert "1 posición(es)" in warnings       # max_open_positions=1


def test_risk_manager_sin_plan_no_dimensiona():
    rm = _rm_fake(FakeMT5(), {})
    task = {"symbol": "XAUUSD", "research": {"summary": {}}, "plan": {}}
    res = rm.run(task)
    assert res.ok and res.summary["risk_ok"] is True
    assert res.summary["max_volume"] == 0.0


def test_researcher_falso_analisis_se_rechaza():
    analyze_fn = lambda s, tf, c: {"ok": False,
                                   "error": "MetaTrader no disponible"}
    res = MarketResearcher(analyze_fn).run({"symbol": "XAUUSD"})
    assert res.ok is False
    assert "MetaTrader" in res.error


# ----------------------------------------------------------------------
# Skill market_governor a través del orquestador (integración)
# ----------------------------------------------------------------------

_TF = {"symbol": "XAUUSD", "timeframe": "H1", "count": 120}


def test_orquestador_skill_market_governor_run(tmp_settings,
                                               fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5())
    try:
        res = orch.run_skill("market_governor", "run", dict(_TF),
                             interactive=False)
        assert res["ok"] is True
        assert res["decision"]["direction"] in ("BULLISH", "BEARISH",
                                                "NEUTRAL")
        assert res["chain"]["order"] == ["researcher", "risk_manager"]
        assert res["executed"] == []
        # con FakeMT5 el bias es determinista: se genera una propuesta
        assert len(res["proposals"]) == 1
        assert res["proposals"][0]["action"] == "market_order"
    finally:
        orch.close()


def test_orquestador_skill_market_governor_execute_read_only(
        tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5())
    try:
        res = orch.run_skill("market_governor", "run", dict(_TF),
                             interactive=False)
        pid = res["proposals"][0]["proposal_id"]
        r2 = orch.run_skill("market_governor", "execute",
                            {"proposal_id": pid}, interactive=True,
                            user_ok=True)
        # READ_ONLY: aunque la política permita con confirmación humana,
        # el executor bloquea por modo de trading (doble defensa)
        assert r2["ok"] is False
        assert r2.get("blocked") == "trading_mode=READ_ONLY"
        assert r2["trading_mode"] == "READ_ONLY"
    finally:
        orch.close()


def test_orquestador_skill_market_governor_execute_confirmado(
        tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5())
    try:
        orch.mt5_executor.mode = TradingMode.CONFIRM_BEFORE_EXECUTION
        res = orch.run_skill("market_governor", "run", dict(_TF),
                             interactive=False)
        pid = res["proposals"][0]["proposal_id"]
        r2 = orch.run_skill("market_governor", "execute",
                            {"proposal_id": pid}, interactive=True,
                            user_ok=True)
        assert r2["ok"] is True
        assert r2["data"]["retcode"] == 10009      # DONE (fake)
        assert r2["trading_mode"] == "CONFIRM_BEFORE_EXECUTION"
        # la misma propuesta ya se consumió -> rechazo honesto
        r3 = orch.run_skill("market_governor", "execute",
                            {"proposal_id": pid}, interactive=True,
                            user_ok=True)
        assert r3["ok"] is False and "consumida" in r3["error"]
        # propuesta inventada -> rechazo honesto
        r4 = orch.run_skill("market_governor", "execute",
                            {"proposal_id": "no-existe"},
                            interactive=True, user_ok=True)
        assert r4["ok"] is False and "no encontrada" in r4["error"]
        # la ejecución quedó auditable en el audit_log
        rows = orch.auditor.recent(limit=200)
        assert any(r["action"] == "mt5.market_order"
                   and r["decision"] == "allow" for r in rows)
    finally:
        orch.close()


def test_orquestador_skill_market_governor_honesto_sin_mt5(
        tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5(fail_init=True))
    try:
        res = orch.run_skill("market_governor", "run", dict(_TF),
                             interactive=False)
        assert res["ok"] is False
        assert res["chain"]["agents"][0]["error"]
    finally:
        orch.close()