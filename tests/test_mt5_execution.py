"""Tests del MT5Executor: modos de trading, confirmación y auditoría (Fase 6).

IMPORTANTE: nada se envía a un terminal real. Se usa FakeMT5 (tests/fakes.py)
cuyo order_send solo registra la petición.
"""

from __future__ import annotations

import pytest

from jayu.memory.db import MemoryDB
from jayu.mt5.connector import MT5Connector
from jayu.mt5.execution import (MT5Executor, TradingMode, resolve_trading_mode)
from jayu.security.audit import Auditor
from jayu.security.policy import Policy

from .fakes import FakeMT5, sample_position

_CONF = {
    "mode": "READ_ONLY",
    "autonomous_trading_enabled": False,
    "execution": {"default_magic": 7654321, "deviation_points": 20,
                  "default_comment": "JAYU"},
    "risk": {"max_open_positions": 5},
}


def _perm(level: str = "confirm_before_execution") -> Policy:
    return Policy({
        "actions": {
            "mt5.market_order": "REVIEW",
            "mt5.pending_order": "REVIEW",
            "mt5.modify_position": "REVIEW",
            "mt5.modify_order": "REVIEW",
            "mt5.close_position": "REVIEW",
            "mt5.breakeven": "REVIEW",
            "mt5.trailing": "REVIEW",
            "mt5.close_all": "DANGEROUS",
            "llm.chat": "SAFE",
        },
        "modes": {},
    }, autonomy_level=level)


def _executor(trading_conf: dict | None = None, *,
              fake: FakeMT5 | None = None, confirmer=None,
              level: str = "confirm_before_execution"):
    conf = dict(_CONF)
    conf.update(trading_conf or {})
    fake = fake or FakeMT5(positions=[sample_position()])
    conn = MT5Connector(mt5_module=fake)
    policy = _perm(level)
    auditor = Auditor(MemoryDB(":memory:"))
    ex = MT5Executor(conn, policy, auditor, conf, confirmer=confirmer)
    return ex, fake, auditor


# ------------------------------------------------------------------
# Resolución de modo
# ------------------------------------------------------------------
def test_modo_por_defecto_read_only():
    assert resolve_trading_mode({"mode": None}) == TradingMode.READ_ONLY


def test_autonomous_requiere_flag_true():
    assert resolve_trading_mode(
        {"mode": "AUTONOMOUS_TRADING",
         "autonomous_trading_enabled": False}) == (
        TradingMode.CONFIRM_BEFORE_EXECUTION)


def test_autonomous_con_flag_true():
    assert resolve_trading_mode(
        {"mode": "AUTONOMOUS_TRADING",
         "autonomous_trading_enabled": True}) == (
        TradingMode.AUTONOMOUS_TRADING)


def test_modo_invalido_degrada_a_read_only():
    assert resolve_trading_mode({"mode": "RANDOM"}) == TradingMode.READ_ONLY


# ------------------------------------------------------------------
# READ_ONLY: ninguna ejecución
# ------------------------------------------------------------------
def test_read_only_bloquea_mercado():
    ex, fake, auditor = _executor({"mode": "READ_ONLY"})
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=True,
                          user_ok=True)
    assert res.ok is False
    assert res.blocked == "trading_mode=READ_ONLY"
    assert fake.sent == []
    # audit deja traza de la denegación
    rows = auditor.recent(limit=20)
    assert any(r["action"] == "mt5.market_order" and
               r["decision"] == "deny" for r in rows)


def test_read_only_bloquea_cierre_total():
    ex, fake, _ = _executor({"mode": "READ_ONLY"})
    res = ex.close_all(interactive=True, user_ok=True)
    assert res.ok is False
    assert fake.sent == []


# ------------------------------------------------------------------
# CONFIRM_BEFORE_EXECUTION
# ------------------------------------------------------------------
def test_confirm_requiere_confirmacion():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"},
                            confirmer=lambda _p: False)
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=True,
                          user_ok=False)
    assert res.ok is False
    assert "confirmación" in res.blocked
    assert fake.sent == []


def test_confirm_ejecuta_con_user_ok():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=True,
                          user_ok=True)
    assert res.ok is True
    assert len(fake.sent) == 1
    req = fake.sent[0]
    assert req["symbol"] == "XAUUSD"
    assert req["volume"] == 0.1
    assert req["type"] in (0, 1)  # BUY
    assert req["magic"] == 7654321


def test_confirm_usa_confirmer():
    calls = []

    def _confirm(prompt):
        calls.append(prompt)
        return True

    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"},
                            confirmer=_confirm)
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=True)
    assert res.ok is True
    assert calls


def test_sin_canal_interactivo_bloquea():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=False)
    assert res.ok is False
    assert fake.sent == []


def test_broker_rechaza_se_reporta():
    fake = FakeMT5(fail_orders=True, positions=[sample_position()])
    ex, _, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"}, fake=fake)
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=True,
                          user_ok=True)
    assert res.ok is False
    assert "invalid volume" in res.reason


def test_side_invalido():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.market_order("XAUUSD", 0.1, "NORTE", interactive=True,
                          user_ok=True)
    assert res.ok is False
    assert fake.sent == []


# ------------------------------------------------------------------
# AUTONOMOUS_TRADING (solo con flag)
# ------------------------------------------------------------------
def test_autonomous_ejecuta_review_sin_confirmar():
    ex, fake, _ = _executor(
        {"mode": "AUTONOMOUS_TRADING", "autonomous_trading_enabled": True},
        level="autonomous")
    res = ex.market_order("XAUUSD", 0.1, "BUY", interactive=False)
    assert res.ok is True
    assert fake.sent


def test_autonomous_dangerous_sigue_necesitando_confirmacion():
    ex, fake, _ = _executor(
        {"mode": "AUTONOMOUS_TRADING", "autonomous_trading_enabled": True},
        level="autonomous")
    res = ex.close_all(interactive=True, user_ok=False)
    assert res.ok is False
    assert fake.sent == []
    res2 = ex.close_all(interactive=True, user_ok=True)
    assert res2.ok is True
    assert fake.sent


# ------------------------------------------------------------------
# Gestión de posiciones
# ------------------------------------------------------------------
def test_close_all_confirmado():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.close_all(interactive=True, user_ok=True)
    assert res.ok is True
    assert res.data["count"] == 1
    assert len(fake.sent) == 1
    # cierre de una COMPRA => orden de VENTA
    assert fake.sent[0]["type"] == 1


def test_close_position_ticket_inexistente():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.close_position(99999, interactive=True, user_ok=True)
    assert res.ok is False
    assert res.blocked == "posición no encontrada"
    assert fake.sent == []


def test_breakeven_mueve_sl():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.breakeven(10001, offset_points=5, interactive=True,
                       user_ok=True)
    assert res.ok is True
    req = fake.sent[-1]
    # compra en 4380.0 -> breakeven + 5 puntos*0.01 = 4380.05
    assert req.get("sl") == pytest.approx(4380.05)
    assert req["ticket"] == 10001


def test_trailing_mueve_sl_cuando_mejora():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"},
                            fake=FakeMT5(positions=[sample_position()]))
    res = ex.trailing("XAUUSD", trail_points=10, step_points=2,
                      interactive=True, user_ok=True)
    assert res.ok is True
    data = res.data["results"][0]
    assert data["moved"] is True
    # bid=4381.0 -> nuevo SL = 4381.0 - 10*0.01 = 4380.9
    assert data["sl"] == pytest.approx(4380.9)


def test_modify_position_requiere_sl_o_tp():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.modify_position(10001, interactive=True, user_ok=True)
    assert res.ok is False
    assert fake.sent == []


def test_modify_position_ok():
    ex, fake, _ = _executor({"mode": "CONFIRM_BEFORE_EXECUTION"})
    res = ex.modify_position(10001, sl=4380.5, tp=4400.0,
                             interactive=True, user_ok=True)
    assert res.ok is True
    req = fake.sent[-1]
    assert req["sl"] == 4380.5
    assert req["tp"] == 4400.0