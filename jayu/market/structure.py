"""Estructura de mercado: swings (fractales), secuencia HH/HL/LH/LL,
tendencia, y rupturas BOS/CHoCH (Fase 5 — análisis, nunca ejecuta).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

FRACTAL_WINDOW = 2  # pivotes con 2 velas a cada lado


def swings(df: pd.DataFrame, window: int = FRACTAL_WINDOW) -> list[dict[str, Any]]:
    """Pivotes fractales alternados: [{index, time, type: 'H'|'L', price}]."""
    high = df["high"]
    low = df["low"]
    n = int(window)
    points: list[dict[str, Any]] = []
    prev_type = None
    for i in range(n, len(df) - n):
        h = float(high.iloc[i])
        l = float(low.iloc[i])
        is_high = all(h > float(high.iloc[j])
                      for j in range(i - n, i + n + 1) if j != i)
        is_low = all(l < float(low.iloc[j])
                     for j in range(i - n, i + n + 1) if j != i)
        kind = None
        if is_high:
            kind = "H"
        elif is_low:
            kind = "L"
        if kind is None or kind == prev_type:
            continue
        points.append({
            "index": int(i),
            "time": str(df["time"].iloc[i]),
            "type": kind,
            "price": round(h if kind == "H" else l, 6),
        })
        prev_type = kind
    return points


def sequence(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Etiqueta los enlaces entre pivotes alternados: HH/HL/LH/LL."""
    out: list[dict[str, Any]] = []
    highs = [p for p in points if p["type"] == "H"]
    lows = [p for p in points if p["type"] == "L"]
    for i in range(1, len(highs)):
        cur = highs[i]
        prev = highs[i - 1]
        label = "HH" if cur["price"] >= prev["price"] else "LH"
        out.append({"from": prev["index"], "to": cur["index"],
                    "label": label, "price": cur["price"],
                    "kind": "high"})
    for i in range(1, len(lows)):
        cur = lows[i]
        prev = lows[i - 1]
        label = "HL" if cur["price"] >= prev["price"] else "LL"
        out.append({"from": prev["index"], "to": cur["index"],
                    "label": label, "price": cur["price"],
                    "kind": "low"})
    out.sort(key=lambda s: s["to"])
    return out


def trend(points: list[dict[str, Any]], seq: list[dict[str, Any]]) -> str:
    """Dirección de la estructura: UP / DOWN / RANGE."""
    if len(seq) < 2:
        # con pocos pivotes, comparamos los dos últimos
        last = points[-4:]
        if len(last) >= 4:
            highs = [p["price"] for p in last if p["type"] == "H"]
            lows = [p["price"] for p in last if p["type"] == "L"]
            if highs and lows and len(highs) >= 2 and len(lows) >= 2:
                if highs[-1] >= highs[-2] and lows[-1] >= lows[-2]:
                    return "UP"
                if highs[-1] <= highs[-2] and lows[-1] <= lows[-2]:
                    return "DOWN"
        return "RANGE"
    recent = seq[-3:]
    highs_up = sum(1 for s in recent if s["label"] in ("HH", "HL"))
    highs_down = sum(1 for s in recent if s["label"] in ("LH", "LL"))
    if highs_up > highs_down:
        return "UP"
    if highs_down > highs_up:
        return "DOWN"
    return "RANGE"


def breakthroughs(df: pd.DataFrame, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Últimos BOS/CHoCH confirmados por cierre de vela.

    UP   -> BOS: close supera el último swing high; CHoCH: close rompe el
            último swing low (cambio de carácter).
    DOWN -> BOS: close rompe el último swing low; CHoCH: close supera el
            último swing high.
    """
    if not points:
        return []
    highs = [p for p in points if p["type"] == "H"]
    lows = [p for p in points if p["type"] == "L"]
    if not highs or not lows:
        return []
    close = df["close"]
    events: list[dict[str, Any]] = []
    last_high = highs[-1]
    last_low = lows[-1]
    start = max(0, last_high["index"] - 5, last_low["index"] - 5)
    for i in range(start, len(close)):
        c = float(close.iloc[i])
        if c > last_high["price"]:
            events.append({"kind": "BOS", "direction": "UP",
                           "index": i, "time": str(df["time"].iloc[i]),
                           "level": round(last_high["price"], 6),
                           "price": round(c, 6)})
        elif c < last_low["price"]:
            events.append({"kind": "CHoCH", "direction": "DOWN",
                           "index": i, "time": str(df["time"].iloc[i]),
                           "level": round(last_low["price"], 6),
                           "price": round(c, 6)})
    return events[-5:]


def build(df: pd.DataFrame) -> dict[str, Any]:
    """Pipeline de estructura completo (dict JSON-friendly)."""
    sw = swings(df)
    seq = sequence(sw)
    tr = trend(sw, seq)
    brk = breakthroughs(df, sw)
    last_h = next((p for p in reversed(sw) if p["type"] == "H"), None)
    last_l = next((p for p in reversed(sw) if p["type"] == "L"), None)
    return {
        "ok": True,
        "swings": [{**p, "price": round(p["price"], 6)} for p in sw[-24:]],
        "sequence_labels": [s for s in seq[-12:]],
        "trend": tr,
        "breakthroughs": brk,
        "last_swing_high": last_h,
        "last_swing_low": last_l,
        "breakout": (brk[-1] if brk else None),
    }