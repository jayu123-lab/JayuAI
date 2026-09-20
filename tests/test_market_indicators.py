"""Tests de indicadores técnicos (Fase 5)."""

from __future__ import annotations

import pandas as pd

from jayu.market import atr, ema, rsi, sma


def _sr(values) -> pd.Series:
    return pd.Series([float(v) for v in values], dtype="float64")


def test_sma_simple():
    out = sma(_sr(range(1, 11)), 3)
    assert out.iloc[-1] == pytest_approx(9.0)


def test_ema_constante():
    out = ema(_sr([5.0] * 20), 5)
    assert out.iloc[-1] == pytest_approx(5.0)


def test_rsi_subida_perfecta_es_100():
    out = rsi(_sr(range(1, 21)), 14)
    assert out.iloc[-1] == pytest_approx(100.0)


def test_rsi_bajada_perfecta_es_0():
    out = rsi(_sr(range(20, 0, -1)), 14)
    assert out.iloc[-1] == pytest_approx(0.0)


def test_rsi_oscila_entre_0_y_100():
    # serie con subidas y bajadas mezcladas
    vals = [10, 11, 10.5, 12, 11, 13, 12.5, 14, 13, 15, 14, 16,
            15, 17, 16, 18, 17, 19, 18, 20]
    out = rsi(_sr(vals), 14)
    last = float(out.iloc[-1])
    assert 0.0 <= last <= 100.0


def test_atr_constante():
    out = atr(_sr([10.0] * 6), _sr([9.0] * 6), _sr([9.5] * 6), 3)
    assert out.iloc[-1] == pytest_approx(1.0)


def pytest_approx(v):
    import pytest
    return pytest.approx(v, abs=1e-6)