"""Skills integradas de JAYU_JAR (Fases 1, 5 y 6).

Nota de honestidad: las skills web/voice están registradas pero NO
implementadas todavía (Fases 3/2). Sus tools devuelven un resultado explícito
con ok=False indicando que la capacidad aún no existe. NO se simulan datos reales.

`mt5` y `market_intelligence` NO se registran aquí: necesitan el
connector/executor vivos del orquestador. `market` se registra aparte vía
`make_market_skill(connector)` (Fase 5); `mt5` vía `make_mt5_skill(...)` (Fase 6).
El `register()` de `market` se conserva para compatibilidad (connector
desconectado: nunca arranca el terminal desde los tests).
"""

from __future__ import annotations

from .system import register as register_system
from .memory import make_store as make_memory_skill
from .web import register as register_web
from .market import register as register_market
from .voice import register as register_voice
from .mt5 import make_mt5_skill  # lo registra el orquestador (necesita contexto)


def register_all(registry, store) -> None:
    """Registra todas las skills integradas. `store` es el MemoryStore vivo.

    Nota: la skill mt5 se registra aparte en el Orchestrator porque depende
    del connector/executor/sizer (ver core/orchestrator.py).
    """
    register_system(registry)
    register_web(registry)
    register_market(registry)
    register_voice(registry)
    registry.register(make_memory_skill(lambda: store))