"""Skills integradas de JayuAI (Fases 1, 2, 5, 6 y 8).

Nota de honestidad: la skill web está registrada pero NO implementada todavía
(Fase 3). Sus tools devuelven un resultado explícito con ok=False indicando
que la capacidad aún no existe. NO se simulan datos reales.

`mt5`, `market_intelligence` y `market_governor` NO se registran aquí:
necesitan conectores/executores vivos del orquestador. `voice` se registra con
motores vivos vía `make_voice_skill(tts, stt)` (Fase 2); `register()` se
conserva para compatibilidad (motores desconectados, nunca toca el micrófono
desde los tests).
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