"""Integración con MetaTrader 5 (FASE 6).

Separación estricta:
    ANÁLISIS  -> `MT5Connector` (lectura: cuenta, posiciones, OHLC, ticks…)
    EJECUCIÓN -> `MT5Executor` (órdenes, SL/TP, cierre) SIEMPRE protegida por:
                 - modo de trading (READ_ONLY por defecto)
                 - política de permisos (REVIEW/DANGEROUS)
                 - confirmación humana
                 - audit_log (antes y después)
"""

from .connector import MT5Connector, MT5Error
from .execution import MT5Executor, TradingMode
from .risk import PositionSizer

__all__ = ["MT5Connector", "MT5Error", "MT5Executor", "TradingMode",
           "PositionSizer"]