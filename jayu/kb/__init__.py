"""jayu.kb — Base de conocimiento de JayuAI.

Conocimiento estructurado (estático, razonado) sobre los mercados que analiza
JayuAI, encabezado por el ORO (XAUUSD) y su ecosistema: plata (XAGUSD), DXY,
bonos del Tesoro, tasas reales, bancos centrales, ETFs y minería.

Honestidad: este módulo es CONOCIMIENTO (marcos, drivers, niveles típicos,
correlaciones históricas), no datos en vivo. Los datos en tiempo real siempre
vienen de MT5/quotas; aquí se marcan explícitamente los campos que requieren
datos externos.
"""

from .gold import (GOLD_ASSETS, GOLD_DRIVERS, gold_context, gold_levels,
                   macro_calendar)

__all__ = ["GOLD_ASSETS", "GOLD_DRIVERS", "gold_context", "gold_levels",
           "macro_calendar"]