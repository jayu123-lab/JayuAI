"""BiasEngine — combina señal técnica + estructura + SMC en un bias con
razones explícitas (Fase 5). Puntúa cada componente con +1/-1/0 y emite
BULLISH / BEARISH / NEUTRAL con un umbral configurable. Solo ANÁLISIS.
"""

from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLD = 2


class BiasEngine:
    def __init__(self, threshold: int = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold

    def compute(self, data: dict[str, Any]) -> dict[str, Any]:
        """`data` es el resultado completo de MarketAnalyzer.analyze()."""
        score = 0
        reasons: list[str] = []
        ind = data.get("indicators", {})
        struct = data.get("structure", {})
        smc = data.get("smc", {})
        last = data.get("last_candle", {})

        close = last.get("close")
        if close is not None:
            ema20 = _num(ind.get("ema20"))
            ema50 = _num(ind.get("ema50"))
            if ema20:
                if close > ema20:
                    score += 1
                    reasons.append("Precio por ENCIMA de EMA20 (tendencia alcista de corto plazo)")
                else:
                    score -= 1
                    reasons.append("Precio por DEBAJO de EMA20 (tendencia bajista de corto plazo)")
            if ema50:
                if close > ema50:
                    score += 1
                    reasons.append("Precio por ENCIMA de EMA50 (tendencia de medio plazo)")
                else:
                    score -= 1
                    reasons.append("Precio por DEBAJO de EMA50 (tendencia de medio plazo)")

        rsi_val = _num(ind.get("rsi14"))
        if rsi_val:
            if rsi_val >= 55:
                score += 1
                reasons.append(f"RSI14={rsi_val:.1f} >= 55 (momento alcista)")
            elif rsi_val <= 45:
                score -= 1
                reasons.append(f"RSI14={rsi_val:.1f} <= 45 (momento bajista)")
            else:
                reasons.append(f"RSI14={rsi_val:.1f} en zona neutral")

        trend = struct.get("trend")
        if trend == "UP":
            score += 1
            reasons.append("Estructura de mercado alcista (HH/HL)")
        elif trend == "DOWN":
            score -= 1
            reasons.append("Estructura de mercado bajista (LH/LL)")
        else:
            reasons.append("Estructura de mercado en rango")

        breakout = struct.get("breakout")
        if breakout:
            if breakout.get("kind") == "BOS" and breakout.get("direction") == "UP":
                score += 1
                reasons.append("BOS al alza confirmado (breakout de swing high)")
            elif breakout.get("kind") == "BOS" and breakout.get("direction") == "DOWN":
                score -= 1
                reasons.append("BOS a la baja confirmado (breakout de swing low)")
            elif breakout.get("kind") == "CHoCH" and breakout.get("direction") == "DOWN":
                score -= 1
                reasons.append("CHoCH bajista: ruptura de estructura alcista")
            elif breakout.get("kind") == "CHoCH" and breakout.get("direction") == "UP":
                score += 1
                reasons.append("CHoCH alcista: ruptura de estructura bajista")

        pd_zone = (smc.get("premium_discount") or {}).get("zone")
        if pd_zone == "premium":
            score -= 1
            reasons.append("Precio en zona PREMIUM del rango (caro; posible rechazo)")
        elif pd_zone == "discount":
            score += 1
            reasons.append("Precio en zona DISCOUNT del rango (barato; posible soporte)")

        direction = "NEUTRAL"
        if score >= self.threshold:
            direction = "BULLISH"
        elif score <= -self.threshold:
            direction = "BEARISH"

        return {
            "ok": True,
            "direction": direction,
            "score": score,
            "threshold": self.threshold,
            "reasons": reasons,
            "key_levels": {
                "last_swing_high": struct.get("last_swing_high"),
                "last_swing_low": struct.get("last_swing_low"),
                "premium_discount": smc.get("premium_discount"),
                "nearest_fvg": _nearest_fvg(smc.get("fvgs", []), close),
            },
        }


def _nearest_fvg(fvgs: list[dict[str, Any]], price: float | None):
    if not fvgs or price is None:
        return None
    best = None
    best_d = float("inf")
    for f in fvgs:
        if f.get("mitigated"):
            continue
        mid = (f.get("top", 0) + f.get("bottom", 0)) / 2.0
        d = abs(mid - price)
        if d < best_d:
            best_d = d
            best = f
    return best


def _num(v: Any) -> float | None:
    try:
        f = float(v)
        return None if f != f else f  # NaN -> None
    except (TypeError, ValueError):
        return None