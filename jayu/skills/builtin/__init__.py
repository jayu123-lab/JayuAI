"""Skills integradas de JAYU_JAR (Fase 1 + Fase 6 MT5).

Nota de honestidad: las skills web/market/voice están registradas pero NO
implementadas todavía (Fases 3/5). Sus tools devuelven un resultado explícito
con ok=False indicando que la capacidad aún no existe. NO se simulan datos reales.

`mt5` NO se registra aquí: necesita el connector/executor vivos del
orquestador, que los inyecta vía `make_mt5_skill(connector, executor, sizer)`.
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