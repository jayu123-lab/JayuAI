"""Integración MT5 a través del Orchestrator y la skill mt5 (Fase 6).

El trading real queda en READ_ONLY (config/trading.yaml), así que cualquier
tool de ejecución debe devolver `blocked` incluso con confirmación humana.
"""

from __future__ import annotations

from jayu.core.orchestrator import Orchestrator

from .fakes import FakeMT5


def _orch(tmp_settings, fake_providers, fake=None) -> Orchestrator:
    return Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=fake or FakeMT5())


def test_status_incluye_mt5(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        st = orch.status()
        assert st["mt5"]["available"] is True
        assert st["mt5"]["trading_mode"] == "READ_ONLY"
        names = [s["name"] for s in st["skills"]]
        assert "mt5" in names
    finally:
        orch.close()


def test_skill_lectura_cuenta(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        res = orch.run_skill("mt5", "account", {}, interactive=False)
        assert res["ok"] is True
        assert res["account"]["balance"] == 10000.0
    finally:
        orch.close()


def test_skill_lectura_posiciones_y_rates(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        pos = orch.run_skill("mt5", "positions", {}, interactive=False)
        assert pos["ok"] is True
        assert pos["count"] == 0  # fake sin posiciones
        rates = orch.run_skill("mt5", "rates",
                               {"symbol": "XAUUSD", "timeframe": "M5",
                                "count": 3}, interactive=False)
        assert rates["ok"] is True
        assert rates["count"] == 3
    finally:
        orch.close()


def test_skill_sizer_solo_sugiere(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        res = orch.run_skill("mt5", "sizer",
                             {"symbol": "XAUUSD", "entry": 4381.0,
                              "sl": 4371.0, "risk_pct": 1.0},
                             interactive=False)
        assert res["ok"] is True
        assert res["suggested_volume"] > 0
    finally:
        orch.close()


def test_ejecucion_bloqueada_en_read_only(tmp_settings, fake_providers):
    """Aunque el usuario confirme, READ_ONLY impide ejecutar la orden."""
    orch = _orch(tmp_settings, fake_providers)
    try:
        res = orch.run_skill("mt5", "market_order",
                             {"symbol": "XAUUSD", "volume": 0.1,
                              "side": "BUY"},
                             interactive=True, user_ok=True)
        assert res["ok"] is False
        assert res.get("blocked_reason") == "trading_mode=READ_ONLY"
    finally:
        orch.close()


def test_skill_lectura_no_disponible_se_reporta_honestamente(
        tmp_settings, fake_providers):
    """Con un fake que falla al inicializar, la lectura dice ok=False."""
    fake = FakeMT5(fail_init=True)
    orch = _orch(tmp_settings, fake_providers, fake=fake)
    try:
        res = orch.run_skill("mt5", "account", {}, interactive=False)
        assert res["ok"] is False
        assert res["error"]
    finally:
        orch.close()