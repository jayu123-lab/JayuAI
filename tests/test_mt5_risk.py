"""Tests del PositionSizer (cálculo de lote por riesgo, Fase 6)."""

from __future__ import annotations

from jayu.mt5.connector import MT5Connector
from jayu.mt5.risk import PositionSizer

from .fakes import FakeMT5


def _sizer(trading_conf: dict | None = None,
           fake: FakeMT5 | None = None) -> PositionSizer:
    return PositionSizer(MT5Connector(mt5_module=fake or FakeMT5()),
                         trading_conf or {})


def test_lote_por_riesgo_xau():
    # equity 10000.5 · riesgo 1% = 100.005
    # SL 10.0 (4381 -> 4371) a tick 0.01 -> 1000 ticks · 1.0$/tick/lote
    # -> pérdida/lote 1000$ -> lote 0.100005 -> floor a step 0.01 = 0.1
    s = _sizer({"risk": {"max_position_pct_equity": 1.0,
                         "max_open_positions": 5}})
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4371.0)
    assert res["ok"] is True
    assert abs(res["suggested_volume"] - 0.1) < 1e-6
    assert res["method"] == "tick_value/tick_size"
    assert res["equity_usd"] == 10000.5


def test_riesgo_por_defecto_desde_config():
    s = _sizer({"risk": {"max_position_pct_equity": 2.0}})
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4371.0)
    # 2% = 200.01 -> lote 0.2
    assert abs(res["suggested_volume"] - 0.2) < 1e-6


def test_riesgo_override():
    s = _sizer({"risk": {"max_position_pct_equity": 2.0}})
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4371.0,
                     risk_pct=0.5)
    assert abs(res["suggested_volume"] - 0.05) < 1e-6


def test_respeta_volumen_max():
    fake = FakeMT5()
    s = _sizer({"risk": {"max_position_pct_equity": 10.0}}, fake=fake)
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4380.0,
                     risk_pct=50.0)
    assert res["suggested_volume"] <= 100.0  # volume_max del fake
    assert res["suggested_volume"] > 0


def test_volumen_max_pequeno():
    fake = FakeMT5(symbol_overrides={"XAUUSD": {"volume_max": 0.05}})
    s = _sizer({}, fake=fake)
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4371.0,
                     risk_pct=1.0)
    assert abs(res["suggested_volume"] - 0.05) < 1e-9


def test_sl_igual_entrada_error():
    s = _sizer({})
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4381.0)
    assert res["ok"] is False
    assert res["suggested_volume"] == 0.0


def test_advertencia_por_max_posiciones():
    fake = FakeMT5()
    fake._positions = [_pos() for _ in range(2)]
    s = _sizer({"risk": {"max_position_pct_equity": 1.0,
                         "max_open_positions": 2}}, fake=fake)
    res = s.lot_size("XAUUSD", entry_price=4381.0, stop_loss=4371.0)
    assert res["ok"] is True
    assert res["open_positions_now"] == 2
    assert any("Ya hay 2 posiciones" in w for w in res["warnings"])


def _pos(**overrides):
    from .fakes import sample_position
    return sample_position(**overrides)