"""Etiquetado automático de ejemplos (Fase 9).

Categoriza cada conversación (oro/mercado, voz, visión, sistema, general)
y decide si es útil para entrenar: útiles son respuestas generadas con
tools/skills reales, sin errores y con suficiente longitud — no ruido.
Reglas explícitas y transparentes, nunca LLM.
"""

from __future__ import annotations

from typing import Any

# Palabras relativas al núcleo del especialista: XAUUSD / oro en todos
# sus ámbitos (macro, FED, DXY, bonos, plata, bancos centrales).
_GOLD_TOKENS = (
    "oro", "gold", "xau", "xagusd", "plata", "silver", "dxy", "dólar",
    "dolar", "bonos", "tesoro", "yield", "us10y", "fed", "fomc", "cpi",
    "pce", "nfp", "inflación", "inflacion", "tasas reales", "tasa real",
    "bancos centrales", "recorte", "recortes", "hawkish", "dovish",
)
_VOICE_TOKENS = ("voz", "habla", "audio", "texto a voz", "transcribe",
                 "micrófono", "microfono", "escucha")
_VISION_TOKENS = ("captura", "pantalla", "ocr", "screenshot", "imagen",
                  "localiza", "ve la")
_SYSTEM_TOKENS = ("estado", "skills", "modelos", "memoria", "auditoría",
                  "auditoria", "permisos", "ayuda", "help")

# Modos que indican que la respuesta NO vino de un modelo real.
_BAD_MODE = ("offline", "blocked", "degraded")
_BAD_FRAGMENTS = (
    "no hay proveedor", "no está disponible", "no hay ningún modelo",
    "comando desconocido", "traceback", "error al",
)


def classify(prompt: str, intent: str = "", skills_used: list[str] | None = None
             ) -> str:
    """Categoría de un ejemplo según intención, skills y palabras clave."""
    skills = " ".join(skills_used or []).lower()
    text = f"{prompt} {intent} {skills}".lower()
    if any(t in text for t in _GOLD_TOKENS) \
            or "gold" in skills or "market" in skills:
        return "gold_market"
    if any(t in text for t in _VOICE_TOKENS) or "voice" in skills:
        return "voice"
    if any(t in text for t in _VISION_TOKENS) or "vision" in skills:
        return "vision"
    if any(t in text for t in _SYSTEM_TOKENS) or "system" in skills:
        return "system"
    return "general"


def usefulness(*, reply: str, mode: str = "", ok: bool = True,
               skills_used: list[str] | None = None,
               min_reply_chars: int = 40) -> tuple[int, str]:
    """0/1 + razón: ¿ejemplo digno de entrenar la LLM?

    Útil = respuesta larga, de un modelo/tool real, sin errores y, mejor
    aún, usando skills. Ruido (offline/bloqueos/degradado) nunca entra.
    """
    reply = reply.strip()
    if not ok:
        return 0, "respuesta con error"
    if mode in _BAD_MODE:
        return 0, f"modo {mode} (sin generar contenido útil)"
    if len(reply) < min_reply_chars:
        return 0, "respuesta demasiado corta"
    low = reply.lower()
    if any(b in low for b in _BAD_FRAGMENTS):
        return 0, "contenido de fallo/negación"
    if skills_used:
        return 1, "usó skills reales y respondió"
    return 1, "respuesta completa del modelo"