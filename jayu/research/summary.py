"""Resumen de textos: generativo (LLM local) o extractivo (sin LLM).

Honestidad: si no hay LLM disponible, el resumen es extractivo (primeros
párrafos sustantivos) y se marca `mode='extractive'`.
"""

from __future__ import annotations

import re
from typing import Any, Callable

_SPLIT_RE = re.compile(r"\n{2,}")


def summarize_text(text: str, *, chat_fn: Callable[[str], str] | None = None,
                   max_summary_chars: int = 1400) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {"ok": True, "summary": "", "mode": "extractive"}
    if chat_fn is not None:
        try:
            prompt = (
                "Resume en español, en 4-6 líneas claras, la idea central de "
                "este texto. Si habla de mercados (oro, plata, DXY, bonos, "
                "FED, inflación) destaca los datos/posiciones clave:\n\n"
                f"{text[:6000]}")
            summary = chat_fn(prompt).strip()
            if summary:
                return {"ok": True, "summary": summary[:max_summary_chars],
                        "mode": "llm"}
        except Exception:  # noqa: BLE001
            pass  # degrada a extractivo
    # Resumen extractivo: párrafos más largos (más sustancia).
    paras = [p.strip() for p in _SPLIT_RE.split(text) if len(p.strip()) > 80]
    if not paras:
        paras = [p.strip() for p in text.splitlines() if len(p.strip()) > 40]
    paras.sort(key=len, reverse=True)
    kept = " ".join(paras[:5])[:max_summary_chars]
    return {"ok": True, "summary": kept, "mode": "extractive"}