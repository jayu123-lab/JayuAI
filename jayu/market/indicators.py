"""Indicadores técnicos con pandas (sin TA-Lib / pandas_ta).

Suficientes para el análisis de estructura y bias de Fase 5. Son
deterministas y no dependen de Internet ni de binarios externos.
"""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, n: int = 20) -> pd.Series:
    """Media móvil simple."""
    return series.rolling(int(n), min_periods=int(n)).mean()


def ema(series: pd.Series, n: int = 20) -> pd.Series:
    """Media móvil exponencial."""
    return series.ewm(span=int(n), adjust=False).mean()


def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder (0-100). Si no hay pérdidas, RSI=100."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.where(avg_loss > 0, 100.0).where(avg_gain > 0, out)


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        n: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    prev_close = close.shift(1)
    tr = pd.concat([high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def true_range(high: pd.Series, low: pd.Series,
               close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([high - low,
                      (high - prev_close).abs(),
                      (low - prev_close).abs()], axis=1).max(axis=1)