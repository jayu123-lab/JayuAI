"""FASE 8 — Multi-agente de mercado.

Un equipo de agentes especializados coordinados por un GOVERNOR:
  1. `MarketResearcher`  -> analiza el mercado (indicadores, estructura, SMC).
  2. `RiskManager`       -> valida el riesgo de una propuesta (lote, spread,
                            posiciones abiertas, pérdida diaria).
  3. `MarketGovernor`    -> coordina a los anteriores, agrega y DECIDE
                            (direction + conviction) — NUNCA ejecuta.

Los agentes emiten PROPUESTAS (REVIEW). La ejecución solo puede ocurrir a
través de la ruta protegida existente (política + modo trading + confirmación
humana + audit_log), nunca en READ_ONLY.

Honestidad: los agentes son deterministas y se prueban con FakeMT5; si MT5 no
está disponible devuelven error explícito. La base `Agent` está lista para
agentes guiados por LLM en fases posteriores (router de modelos), pero hoy no
se simula ningún análisis.
"""

from .base import Agent, AgentResult
from .market import MarketGovernor, MarketResearcher, RiskManager

__all__ = ["Agent", "AgentResult", "MarketGovernor", "MarketResearcher",
           "RiskManager"]