"""Fase 5 — Market Intelligence de JAYU_JAR.

ANÁLISIS puro, sin ejecutar nada:
  indicators.py -> SMA/EMA/RSI/ATR (pandas, sin dependencias externas)
  structure.py  -> swings (fractales) + estructura de mercado + BOS/CHoCH
  smc.py        -> Fair Value Gaps, order blocks, premium/discount
  bias.py       -> BiasEngine: puntúa y emite BULLISH/BEARISH/NEUTRAL
  analyzer.py   -> MarketAnalyzer: pipeline completo sobre datos reales MT5

Los datos provienen EXCLUSIVAMENTE de `MT5Connector` (Fase 6). Si no hay
terminal/paquete disponible, las tools devuelven un error explícito y honesto
(no se simulan precios).
"""

from .analyzer import MarketAnalyzer
from .bias import BiasEngine
from .indicators import atr, ema, rsi, sma

__all__ = ["MarketAnalyzer", "BiasEngine", "atr", "ema", "rsi", "sma"]