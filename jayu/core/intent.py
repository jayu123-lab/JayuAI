"""Clasificación de intención y complejidad (reglas, sin LLM).

Principio de velocidad: la clasificación se hace con reglas locales baratas.
El LLM solo se usa cuando la tarea lo necesita. El modelo a usar se decide
después con el ModelRouter según intent + complejidad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (patrón, intent, complejidad_base)
_RULES: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"\b(hola|buenas|hey|saludos|buenos días|buenas tardes|buenas noches)\b", re.I), "chat", 1),
    (re.compile(r"\b(mt5|metatrader|posiciones|órdenes\b|exposición)\b", re.I), "mt5", 2),
    (re.compile(r"\b(habla|voz|dilo por voz|audio)\b", re.I), "voice", 1),
    (re.compile(r"\b(busca|investiga|búscame|noticias|artículo|fuentes?)\b", re.I), "research", 2),
    (re.compile(r"\b(recuerda|recuérdame|guarda que|no olvides|qué sabes de mí|olvida|prefiero|mi broker|mi cuenta)\b", re.I), "memory", 1),
    (re.compile(r"\b(memoria|recuerdos|working|tareas activas)\b", re.I), "memory_query", 1),
    (re.compile(
        r"\b(oro|gold|dax|ibex|eurusd|gbpusd|dxy|bitcoin|btc|ethereum|eth|"
        r"xrp|solana|acciones|futuros|forex|trading|mercados?|cotizaci[oó]n|"
        r"precio del|bonos?|plata|silver|oil|crudo|nasdaq|sp500|nq|es)\b"
        r"|\bxau[a-z0-9]*\b|\bgc[a-z0-9]*\b",
        re.I), "market", 3),
    (re.compile(r"\b(código|codigo|programa|script|función|bug|error en|excepción|debug|refactor|test)\b", re.I), "code", 2),
    (re.compile(r"\b(estado|status|qué puedes hacer|ayuda|help|skills)\b", re.I), "system", 1),
]


@dataclass(frozen=True)
class Intent:
    name: str
    complexity: int
    routing_role: str  # clave de config/models.yaml -> routing


_INTENT_ROLE = {
    "chat": "chat",
    "classify": "classify",
    "market": "market",
    "mt5": "chat",
    "code": "code",
    "research": "research",
    "reason": "deep",
    "memory": "chat",
    "memory_query": "chat",
    "voice": "classify",
    "system": "classify",
}


def classify_intent(text: str) -> Intent:
    """Devuelve la intención dominante según reglas de palabras clave."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    for pattern, intent, complexity in _RULES:
        if pattern.search(cleaned):
            if len(cleaned) > 600:
                complexity = min(3, complexity + 1)
            return Intent(intent, complexity, _INTENT_ROLE.get(intent, "chat"))
    return Intent("chat", 1, "chat")


def complexity_score(text: str) -> int:
    """Heurística: 1 simple, 2 medio, 3 profundo."""
    length = len(text.split())
    if length > 80 or any(w in text.lower() for w in
                          ("analiza", "explica en detalle", "por qué",
                           "compare", "estrategia")):
        return 3
    if length > 25:
        return 2
    return 1