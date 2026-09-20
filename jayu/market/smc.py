"""SMC — Smart Money Concepts básicos (Fase 5).

Detalles sencillos y honestos:
  - Fair Value Gaps: hueco de 3 velas sin solapamiento.
  - Order Blocks: última vela en contra antes de un movimiento fuerte.
  - Premium/Discount: posición del precio dentro del rango reciente.

Son heurísticas deterministas sobre velas reales; no prometen señales.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .indicators import atr


def detect_fvg(df: pd.DataFrame, lookback: int = 60,
               active_range: int = 10) -> list[dict[str, Any]]:
    """FVG: bullish si low[i] > high[i-2] (hueco al alza); bearish si
    high[i] < low[i-2]. Devuelve los activos (sin mitigar) más recientes."""
    out: list[dict[str, Any]] = []
    n = len(df)
    start = max(2, n - lookback)
    for i in range(start, n):
        lo = float(df["low"].iloc[i])
        hi = float(df["high"].iloc[i])
        hi2 = float(df["high"].iloc[i - 2])
        lo2 = float(df["low"].iloc[i - 2])
        if lo > hi2:
            fvg = {"kind": "bullish", "index": i,
                   "top": round(lo, 6), "bottom": round(hi2, 6),
                   "time": str(df["time"].iloc[i]),
                   "mitigated": False}
        elif hi < lo2:
            fvg = {"kind": "bearish", "index": i,
                   "top": round(lo2, 6), "bottom": round(hi, 6),
                   "time": str(df["time"].iloc[i]),
                   "mitigated": False}
        else:
            continue
        # mitigación: precio posterior entró en el hueco
        for j in range(i + 1, min(n, i + active_range)):
            p = float(df["close"].iloc[j])
            if fvg["bottom"] <= p <= fvg["top"]:
                fvg["mitigated"] = True
                break
        out.append(fvg)
    return out[-6:]


def order_blocks(df: pd.DataFrame, strength: float = 1.2) -> list[dict[str, Any]]:
    """Últimas OB: vela en contra inmediatamente anterior a un empuje con
    cuerpo >= strength * ATR."""
    tr_avg = atr(df["high"], df["low"], df["close"], 14)
    out: list[dict[str, Any]] = []
    n = len(df)
    for i in range(1, n):
        a = tr_avg.iloc[i]
        if pd.isna(a) or a <= 0:
            continue
        body = abs(float(df["close"].iloc[i]) - float(df["open"].iloc[i]))
        if body < strength * float(a):
            continue
        bullish_push = float(df["close"].iloc[i]) > float(df["open"].iloc[i])
        prev = df.iloc[i - 1]
        if bullish_push and float(prev["close"]) < float(prev["open"]):
            out.append({"kind": "bullish_ob", "index": i - 1,
                        "top": round(float(prev["high"]), 6),
                        "bottom": round(float(prev["low"]), 6),
                        "time": str(df["time"].iloc[i - 1])})
        elif not bullish_push and float(prev["close"]) > float(prev["open"]):
            out.append({"kind": "bearish_ob", "index": i - 1,
                        "top": round(float(prev["high"]), 6),
                        "bottom": round(float(prev["low"]), 6),
                        "time": str(df["time"].iloc[i - 1])})
    return out[-4:]


def premium_discount(df: pd.DataFrame, last_swing_high: dict | None,
                     last_swing_low: dict | None) -> dict[str, Any] | None:
    """Posición del precio en el rango (0% = mín del rango, 100% = máx).
    premium (caro) por encima del 50%; discount (barato) por debajo."""
    if not last_swing_high or not last_swing_low:
        return None
    sh = float(last_swing_high["price"])
    sl = float(last_swing_low["price"])
    if sh <= sl:
        return None
    price = float(df["close"].iloc[-1])
    pos = (price - sl) / (sh - sl) * 100.0
    pos = max(0.0, min(100.0, pos))
    return {
        "range_high": round(sh, 6),
        "range_low": round(sl, 6),
        "price_position_pct": round(pos, 1),
        "zone": "premium" if pos > 50.0 else "discount",
        "halfway": round((sh + sl) / 2, 6),
    }


def analyze(df: pd.DataFrame, structure: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "fvgs": detect_fvg(df),
        "order_blocks": order_blocks(df),
        "premium_discount": premium_discount(
            df,
            structure.get("last_swing_high"),
            structure.get("last_swing_low")),
    }