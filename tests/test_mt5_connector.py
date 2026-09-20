"""Tests del MT5Connector (capa de LECTURA / análisis, Fase 6)."""

from __future__ import annotations

import pytest

import jayu.mt5.connector as connector_mod
from jayu.mt5.connector import MT5Connector, MT5Error

from .fakes import FakeMT5, sample_pending, sample_position


def _conn(fake=None, **kw) -> MT5Connector:
    return MT5Connector(mt5_module=fake or FakeMT5(), **kw)


def test_available_y_connect():
    c = _conn()
    assert c.available is True
    assert c.connect() is True
    assert c.connected is True


def test_status_refleja_estado():
    c = _conn()
    st = c.status()
    assert st["available"] is True
    assert st["connected"] is False  # status() no conecta automáticamente
    assert "terminal_path" in st
    c.connect()
    assert c.status()["connected"] is True


def test_connect_fail_init():
    c = _conn(fake=FakeMT5(fail_init=True))
    assert c.connect() is False
    assert c.connected is False


def test_account_info():
    c = _conn()
    acc = c.account_info()
    assert acc["login"] == 1514603387
    assert acc["balance"] == 10000.0
    assert acc["currency"] == "USD"


def test_positions_y_orders():
    fake = FakeMT5(positions=[sample_position()],
                   orders=[sample_pending()])
    c = _conn(fake)
    rows = c.positions()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "XAUUSD"
    assert len(c.positions(symbol="XAUUSD")) == 1
    assert c.positions(symbol="EURUSD") == []
    assert len(c.orders()) == 1


def test_symbols_y_quote():
    c = _conn()
    syms = c.symbols()
    assert "XAUUSD" in syms
    q = c.quote("XAUUSD")
    assert q["symbol"] == "XAUUSD"
    assert q["bid"] and q["ask"]
    assert q["spread_points"] == 10


def test_symbol_info_inexistente_raise():
    c = _conn()
    with pytest.raises(MT5Error):
        c.symbol_info("NOEXISTE")


def test_rates_parseo():
    c = _conn()
    rows = c.rates("XAUUSD", "M5", count=5)
    assert len(rows) == 5
    assert isinstance(rows[0]["time"], int)
    assert rows[0]["close"] > 0
    assert rows[0]["open"] == rows[0]["open"]  # no NaN


def test_rates_timeframe_invalido():
    c = _conn()
    with pytest.raises(MT5Error):
        c.rates("XAUUSD", "ZZZ")


def test_rates_simbolo_invalido():
    c = _conn()
    with pytest.raises(MT5Error):
        c.rates("NOEXISTE", "M5")


def test_ticks():
    c = _conn()
    rows = c.ticks("XAUUSD", count=3)
    assert len(rows) == 3
    assert "bid" in rows[0]


def test_history():
    c = _conn()
    h = c.history(days=1)
    assert h["days"] == 1
    assert isinstance(h["deals"], list)
    assert isinstance(h["orders"], list)


def test_last_error_es_tupla():
    c = _conn()
    err = c.last_error()
    assert isinstance(err, tuple) and len(err) == 2


def test_modulo_no_instalado(monkeypatch):
    def _boom():
        raise MT5Error("El paquete MetaTrader5 no está instalado.",
                       hint="pip install MetaTrader5")

    monkeypatch.setattr(connector_mod, "_import_mt5", _boom)
    c = MT5Connector()
    assert c.available is False
    assert c.status()["available"] is False
    with pytest.raises(MT5Error):
        c.account_info()
    with pytest.raises(MT5Error):
        c.rates("XAUUSD", "M5", count=1)


def test_sin_conexion_levanta_error():
    c = MT5Connector(mt5_module=FakeMT5(fail_init=True))
    assert c.connected is False
    with pytest.raises(MT5Error):
        c.account_info()


def test_shutdown():
    c = _conn()
    c.connect()
    c.shutdown()
    assert c.connected is False