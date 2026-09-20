"""Base de agentes de JAYU_JAR (Fase 8).

Hoy los agentes son deterministas (ejecutan tools de análisis y agregan
resultados). Esta base permite que en fases posteriores un agente sea guiado
por un LLM (via router de modelos) sin cambiar la interfaz: cada agente recibe
una tarea y devuelve un `AgentResult` auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentResult:
    """Salida de un agente: resumen + errores honestos."""
    name: str
    step: str
    ok: bool
    summary: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "step": self.step,
            "ok": self.ok,
            "summary": self.summary,
            "error": self.error,
        }


class Agent:
    """Contrato mínimo de un agente.

    `run(task)` recibe un dict con la tarea y devuelve un `AgentResult`.
    Los agentes NO tienen acceso a rutas de ejecución por diseño.
    """

    role: str = "agente"
    name: str = "agent"
    tools: list[str] = []

    def __init__(self, *, name: str | None = None) -> None:
        if name:
            self.name = name

    def run(self, task: dict[str, Any]) -> AgentResult:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "role": self.role, "tools": list(self.tools)}


def run_agent_chain(agents: list[Callable[[], AgentResult]]) -> list[dict[str, Any]]:
    """Ejecuta una cadena de pasos de agente y devuelve sus resultados."""
    results = []
    for task_fn in agents:
        res = task_fn()
        results.append(res.as_dict())
        if not res.ok:
            break  # cadena interrumpida: no se propone nada sin análisis válido
    return results