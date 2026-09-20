"""Plan: capa intermedia de planificación/validación.

JAYU no responde solo con la salida bruta del LLM: define un plan con pasos,
los ejecuta, valida el resultado y lo repite si algo falla. Cada paso deja
un registro (working + episodic + audit cuando toque).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    kind: str                 # "llm" | "tool" | "validation"
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    validate: str = ""        # condición de validación (descripción)
    max_retries: int = 1


@dataclass
class Plan:
    objective: str
    steps: list[PlanStep] = field(default_factory=list)

    def add(self, step: PlanStep) -> None:
        self.steps.append(step)


def build_default_plan(intent_name: str, objective: str) -> Plan:
    """Plan por defecto según intención (se refina por skill en Fases 5-8)."""
    plan = Plan(objective=objective)
    if intent_name in ("memory_query", "memory"):
        plan.add(PlanStep("tool", "memory.recall",
                          {"query": objective}, validate="result.ok"))
        plan.add(PlanStep("llm", "answer", {}))
    elif intent_name == "market":
        plan.add(PlanStep("tool", "market_intelligence.quote",
                          {"symbol": objective}))
        plan.add(PlanStep("llm", "analysis", {},
                          validate="result.content"))
    else:
        plan.add(PlanStep("llm", "answer", {},
                          validate="result.opcional"))
    plan.add(PlanStep("validation", "check", {}))
    return plan