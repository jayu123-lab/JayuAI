"""Tests de estructura, SMC, bias y MarketAnalyzer (Fase 5)."""

from __future__ import annotations

import pandas as pd
import pytest

from jayu.market.analyzer import MarketAnalyzer
from jayu.market.smc import analyze as smc_analyze, detect_fvg, order_blocks, \
    premium_discount
from jayu.market.structure import (breakthroughs, build, sequence, swings,
                                   trend)
from jayu.mt5.connector import MT5Connector

from .fakes import FakeMT5


def _df(open_, high, low, close) -> pd.DataFrame:
    return pd.DataFrame({
        "time": list(range(len(open_))),
        "open": [float(x) for x in open_],
        "high": [float(x) for x in high],
        "low": [float(x) for x in low],
        "close": [float(x) for x in close],
    })


# ------------------------------------------------------------------
# Structure — swings, secuencia, tendencia, BOS/CHoCH
# ------------------------------------------------------------------
def test_swings_detecta_pivote_alto():
    high = [3, 4, 5, 6, 10, 6, 5, 4, 5, 6, 7]
    low = [2.5, 3.5, 4.5, 5.5, 6.0, 5.5, 4.5, 3.5, 4.5, 5.5, 6.5]
    df = _df(high, high, low, high)
    pts = swings(df)
    kinds = [p["type"] for p in pts]
    assert "H" in kinds
    hi_pivots = [p for p in pts if p["type"] == "H"]
    assert hi_pivots[0]["index"] == 4
    assert hi_pivots[0]["price"] == 10.0


def test_sequence_etiqueta_hh_hl():
    points = [
        {"index": 0, "type": "L", "price": 1.0},
        {"index": 2, "type": "H", "price": 3.0},
        {"index": 4, "type": "L", "price": 2.0},
        {"index": 6, "type": "H", "price": 4.0},
    ]
    seq = sequence(points)
    labels = [s["label"] for s in seq]
    assert "HH" in labels and "HL" in labels
    assert trend(points, seq) == "UP"


def test_sequence_etiqueta_ll_lh_y_tendencia_down():
    points = [
        {"index": 0, "type": "H", "price": 10.0},
        {"index": 2, "type": "L", "price": 8.0},
        {"index": 4, "type": "H", "price": 9.0},
        {"index": 6, "type": "L", "price": 6.0},
    ]
    seq = sequence(points)
    labels = [s["label"] for s in seq]
    assert "LH" in labels and "LL" in labels
    assert trend(points, seq) == "DOWN"


def test_breakthrough_bos_al_alza():
    closes = [96.0, 96.5, 97.0, 97.5, 98.0, 98.5, 97.0, 96.5, 101.0]
    df = _df(closes, closes, [c - 0.5 for c in closes], closes)
    points = [{"index": 3, "type": "L", "price": 90.0},
              {"index": 5, "type": "H", "price": 100.0},
              {"index": 7, "type": "L", "price": 95.0}]
    evts = breakthroughs(df, points)
    assert evts
    last = evts[-1]
    assert last["kind"] == "BOS"
    assert last["direction"] == "UP"


def test_build_devuelve_secciones():
    rg = list(range(30))
    df = _df(rg, [v + 1 for v in rg], [v - 1 for v in rg], rg)
    res = build(df)
    assert res["ok"] is True
    assert res["trend"] in ("UP", "DOWN", "RANGE")
    assert "last_swing_high" in res
    assert "breakthroughs" in res


# ------------------------------------------------------------------
# SMC — FVG, order blocks, premium/discount
# ------------------------------------------------------------------
def test_detect_fvg_bullish():
    df = _df(
        open_=[9.0, 9.5, 10.0],
        high=[10.0, 11.0, 12.0],
        low=[9.0, 9.5, 10.5],   # low[2]=10.5 > high[0]=10 -> hueco alcista
        close=[9.2, 9.8, 10.8],
    )
    fvgs = detect_fvg(df, lookback=10, active_range=0)
    bulls = [f for f in fvgs if f["kind"] == "bullish"]
    assert bulls
    assert bulls[0]["bottom"] == 10.0
    assert bulls[0]["top"] == 10.5


def test_detect_fvg_bearish():
    # hueco bajista real: high[2] < low[0]
    df = _df(
        open_=[12.0, 11.6, 11.2],
        high=[12.2, 11.8, 11.3],
        low=[11.5, 11.4, 11.0],
        close=[11.7, 11.5, 11.1],
    )
    fvgs = detect_fvg(df, lookback=10, active_range=0)
    bears = [f for f in fvgs if f["kind"] == "bearish"]
    assert bears
    assert bears[0]["top"] == 11.5
    assert bears[0]["bottom"] == 11.3


def test_premium_y_discount():
    df = _df([10.0, 40.0, 60.0], [10.0, 40.0, 60.0],
             [10.0, 40.0, 60.0], [10.0, 40.0, 60.0])
    sh = {"price": 100.0}
    sl = {"price": 0.0}
    pd_ = premium_discount(df, sh, sl)
    assert pd_["price_position_pct"] == 60.0
    assert pd_["zone"] == "premium"


def test_order_blocks_alcista():
    highs, lows, opens, closes = [], [], [], []
    for i in range(18):  # rango suave alrededor de 100
        lows.append(99.5)
        highs.append(100.5)
        opens.append(100.0 if i % 2 == 0 else 99.8)
        closes.append(100.0 if i % 2 == 0 else 100.2)
    # vela bajista seguida de un empuje alcista fuerte
    opens += [100.0, 99.5]
    closes += [99.5, 106.0]
    highs += [100.2, 106.5]
    lows += [99.2, 99.0]
    df = _df(opens, highs, lows, closes)
    obs = order_blocks(df, strength=1.2)
    assert any(o["kind"] == "bullish_ob" for o in obs)


def test_smc_analyze_integrado():
    df = _df([1.0] * 5 + [2.0] * 5, [2.0] * 10, [0.5] * 10,
             [1.5] * 9 + [1.9])
    struct = build(_with_pivots(df))
    res = smc_analyze(df, struct)
    assert res["ok"] is True
    assert "fvgs" in res and "order_blocks" in res
    assert "premium_discount" in res


def _with_pivots(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["time"] = list(range(len(df)))
    return df


# ------------------------------------------------------------------
# MarketAnalyzer — integración con MT5 (fake) y honestidad sin terminal
# ------------------------------------------------------------------
def test_analyzer_pipeline_con_fake_mt5():
    fake = FakeMT5()
    conn = MT5Connector(mt5_module=fake)
    an = MarketAnalyzer(conn)
    res = an.analyze("XAUUSD", "H1", count=200)
    assert res["ok"] is True
    assert res["candles"] == 200
    assert res["bias"]["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(res["bias"]["reasons"], list)
    assert res["indicators"]["rsi14"] is not None
    assert res["structure"]["trend"] in ("UP", "DOWN", "RANGE")
    assert res["quote"]["symbol"] == "XAUUSD"


def test_analyzer_requiere_min_velas():
    fake = FakeMT5()
    conn = MT5Connector(mt5_module=fake)
    an = MarketAnalyzer(conn)
    res = an.analyze("XAUUSD", "H1", count=10)
    assert res["ok"] is False
    assert "velas" in res["error"]


def test_analyzer_honesto_sin_terminal(monkeypatch):
    import jayu.mt5.connector as connector_mod
    from jayu.mt5.connector import MT5Error

    def _boom():
        raise MT5Error("El paquete MetaTrader5 no está instalado.",
                       hint="pip install MetaTrader5")

    monkeypatch.setattr(connector_mod, "_import_mt5", _boom)
    conn = MT5Connector()
    an = MarketAnalyzer(conn)
    res = an.analyze("XAUUSD", "H1", count=200)
    assert res["ok"] is False
    assert "MetaTrader" in res["error"]


def test_analyze_df_sin_mt5():
    """analyze_df funciona sobre un DataFrame directo (para tests/EDA)."""
    rg = list(range(60))
    df = _df(rg, [v + 1 for v in rg], [v - 1 for v in rg], rg)
    an = MarketAnalyzer(connector=__import__("types").SimpleNamespace(
        available=False), threshold=2)
    res = an.analyze_df("XAUUSD", "M5", df)
    assert res["ok"] is True
    assert res["bias"]["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")


# ------------------------------------------------------------------
# Skill market_intelligence a través del orquestador (Fase 5)
# ------------------------------------------------------------------
def test_orquestador_skill_market(tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5())
    try:
        res = orch.run_skill("market_intelligence", "analyze",
                             {"symbol": "XAUUSD", "timeframe": "H1",
                              "count": 120}, interactive=False)
        assert res["ok"] is True
        assert res["bias"]["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")
        assert res["structure"]["trend"] in ("UP", "DOWN", "RANGE")
        # las tools de ejecución siguen bloqueadas por READ_ONLY
        r2 = orch.run_skill("mt5", "market_order",
                            {"symbol": "XAUUSD", "volume": 0.1,
                             "side": "BUY"}, interactive=True, user_ok=True)
        assert r2["ok"] is False
    finally:
        orch.close()


def test_orquestador_skill_market_honesto_sin_mt5(tmp_settings,
                                                  fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5(fail_init=True))
    try:
        res = orch.run_skill("market_intelligence", "bias",
                             {"symbol": "XAUUSD"}, interactive=False)
        assert res["ok"] is False
        assert res.get("error")
    finally:
        orch.close()