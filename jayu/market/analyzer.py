"""MarketAnalyzer — pipeline de análisis sobre datos reales de MT5.

Construye un DataFrame desde `connector.rates()`, calcula indicadores,
estructura, SMC y bias. No ejecuta ninguna operación (Fase 5, análisis).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..mt5.connector import MT5Error
from . import bias as bias_mod
from . import indicators as ind
from . import smc as smc_mod
from . import structure as struct_mod

MIN_CANDLES = 50


class MarketAnalyzer:
    def __init__(self, connector, threshold: int = 2) -> None:
        self.connector = connector
        self.bias_engine = bias_mod.BiasEngine(threshold=threshold)

    # ------------------------------------------------------------------
    def analyze(self, symbol: str, timeframe: str = "H1",
                count: int = 400) -> dict[str, Any]:
        # HONESTIDAD: si MT5 no está disponible, error explícito.
        if not self.connector.available:
            return {"ok": False, "symbol": symbol, "timeframe": timeframe,
                    "error": "MetaTrader 5 no disponible en esta máquina.",
                    "hint": "Instala el paquete y abre el terminal."}
        if count < MIN_CANDLES:
            return {"ok": False, "symbol": symbol, "timeframe": timeframe,
                    "error": f"Se necesitan al menos {MIN_CANDLES} velas "
                             f"(count={count}).",
                    "hint": "Sube el parámetro count (> 50)."}
        try:
            rates = self.connector.rates(symbol, timeframe, count=count)
        except MT5Error as exc:
            return {"ok": False, "symbol": symbol, "timeframe": timeframe,
                    "error": str(exc), "hint": getattr(exc, "hint", "")}
        if not rates:
            return {"ok": False, "symbol": symbol, "timeframe": timeframe,
                    "error": "Sin velas devueltas por MT5."}
        df = self._to_df(rates)
        return self._pipeline(symbol, timeframe, df)

    # ------------------------------------------------------------------
    def analyze_df(self, symbol: str, timeframe: str,
                   df: pd.DataFrame) -> dict[str, Any]:
        return self._pipeline(symbol, timeframe, df)

    # ------------------------------------------------------------------
    def _pipeline(self, symbol: str, timeframe: str,
                  df: pd.DataFrame) -> dict[str, Any]:
        last = df.iloc[-1]
        close = pd.to_numeric(df["close"], errors="coerce")
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")

        indicators = {
            "sma20": _round(ind.sma(close, 20).iloc[-1]),
            "sma50": _round(ind.sma(close, 50).iloc[-1]),
            "ema20": _round(ind.ema(close, 20).iloc[-1]),
            "ema50": _round(ind.ema(close, 50).iloc[-1]),
            "rsi14": _round(ind.rsi(close, 14).iloc[-1], 2),
            "atr14": _round(ind.atr(high, low, close, 14).iloc[-1]),
        }
        atr_v = indicators["atr14"]
        if atr_v:
            indicators["atr14_pct"] = round(atr_v / float(close.iloc[-1]) * 100, 3)

        structure = struct_mod.build(df)
        smc = smc_mod.analyze(df, structure)
        bias = self.bias_engine.compute({
            "indicators": indicators,
            "structure": structure,
            "smc": smc,
            "last_candle": _candle(last),
        })

        quote = None
        try:
            quote = self.connector.quote(symbol)
        except (MT5Error, AttributeError):
            # AttributeError: vectores sin quotation (EDA/tests directos)
            quote = None

        return {
            "ok": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": len(df),
            "ts": str(df["time"].iloc[-1]),
            "quote": quote,
            "last_candle": _candle(last),
            "indicators": indicators,
            "structure": structure,
            "smc": smc,
            "bias": bias,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _to_df(rates: list[dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(rates)
        # normaliza valores (numpy -> float/int)
        for col in ("open", "high", "low", "close", "tick_volume",
                    "spread", "real_volume"):
            if col in df:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("time").reset_index(drop=True)
        return df


def _candle(row: Any) -> dict[str, Any]:
    out = {}
    for key in ("time", "open", "high", "low", "close", "tick_volume",
                "spread", "real_volume"):
        if key in row:
            v = row[key]
            if key == "time" and not isinstance(v, str):
                try:
                    v = datetime.fromtimestamp(int(v),
                                               tz=timezone.utc).isoformat()
                except (TypeError, ValueError, OSError):
                    v = str(v)
            if key != "time":
                try:
                    v = round(float(v), 6) if float(v) == float(v) else None
                except (TypeError, ValueError):
                    pass
            out[key] = v
    return out


def _round(v, digits: int = 6):
    try:
        f = float(v)
        if f != f:
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None