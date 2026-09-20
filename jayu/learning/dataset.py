"""Exportación del dataset (Fase 9) para entrenar la LLM poco a poco.

Genera JSONL estilo OpenAI de fine-tuning (messages system/user/assistant)
a partir de los ejemplos útiles del LearningStore, listo para:
  - Ollama (modelfile con ADAPTER/epochs en futuro),
  - LLaMA-Factory / Unsloth / axolotl,
  - cualquier fine-tuner que acepte el formato chat estándar.

El dataset NUNCA sale de la máquina: la exportación es a disco local y
el entrenamiento queda documentado como pasos futuros (hardware local
limitado por ahora).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger
from .labeller import classify, usefulness

logger = get_logger("learning.dataset")

_DEFAULT_SYSTEM = (
    "Eres JayuAI, un asistente personal local experto en XAUUSD y el oro "
    "en todos sus ámbitos (macro, micro, fundamental, bancos centrales, "
    "plata, DXY y bonos del Tesoro), además de otros mercados. Analizas "
    "con datos reales, nunca inventas resultados, separas análisis de "
    "ejecución y respondes siempre en español con honestidad."
)


def build_dataset(store, *, system_prompt: str = _DEFAULT_SYSTEM,
                  only_useful: bool = True, limit: int = 5000,
                  extra_context: list[str] | None = None
                  ) -> list[dict[str, Any]]:
    """Construye la lista de ejemplos en formato chat estándar."""
    rows = store.examples(useful=1 if only_useful else None, limit=limit)
    dataset: list[dict[str, Any]] = []
    for r in rows:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": r["prompt"]},
                    {"role": "assistant", "content": r["reply"]}]
        if extra_context:
            # contexto adicional del reporte (skills usadas/razón de
            # utilidad) como mensaje de sistema auxiliar
            messages.insert(1, {"role": "system",
                                "content": "; ".join(extra_context)})
        dataset.append({
            "messages": messages,
            "category": r["category"],
            "intent": r["intent"],
            "skills_used": (r["skills_used"] or "").split(","),
            "useful_reason": r["useful_reason"] or "",
            "source": "jayuai-local",
            "timestamp": r["ts"],
        })
    return dataset


def export_jsonl(store, out_dir: str | Path, *,
                 system_prompt: str = _DEFAULT_SYSTEM,
                 only_useful: bool = True, limit: int = 5000,
                 include_guide: bool = True) -> dict[str, Any]:
    """Exporta el dataset a `<out_dir>/jayuai_finetune.jsonl` (UTF-8).

    Devuelve {ok, path, registros, bytes}. Nunca sube nada.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset(store, system_prompt=system_prompt,
                            only_useful=only_useful, limit=limit)
    path = out_dir / "jayuai_finetune.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for item in dataset:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    size = path.stat().st_size
    if include_guide:
        (out_dir / "COMO_ENTRENAR.md").write_text(
            _guide_text(len(dataset)), encoding="utf-8")
    return {"ok": True, "path": str(path), "registros": len(dataset),
            "bytes": size}


def _guide_text(n: int) -> str:
    return f"""# JayuAI — Cómo entrenar la LLM poco a poco (Fase 9)

Dataset local con {n} ejemplos útiles capturados de conversaciones reales
(`jayuai_finetune.jsonl`). NUNCA se exporta fuera de esta máquina.

## Enfoque recomendado (hardware local)

1. **Ollama + Modelfile (ajuste ligero, sin GPU potente)**
   - Prepara un modelo base (p.ej. `qwen2.5:3b`) y entrena un LoRA con
     `curl` a la API de Ollama (/api/train) usando este JSONL, o exporta
     a GGUF y usa `llama.cpp` (finetune) para un adapter LoRA.
   - `FROM qwen2.5:3b` + `ADAPTER ./lora.safetensors` en el Modelfile.

2. **Cuándo exportar de nuevo**: cuando el dataset supere ~3× el tamaño
   del entrenamiento anterior, o aparezcan 200+ ejemplos nuevos útiles.

3. **Reglas de oro**
   - `only_useful=True`: solo entran respuestas con skills reales y sin
     errores (el etiquetado es heurístico y transparente).
   - Antes de entrenar, revisa QA: 20-30 ejemplos de oro/mercado, voz y
     visión; anonimiza cualquier dato de cuenta/broker.
   - Si el modelo empeora en una categoría, vuelve a capturar más
     ejemplos de esa categoría (datos reales, no sintéticos).

## Formato
```
{{"messages": [{{"role":"system",...}}, {{"role":"user",...}},
               {{"role":"assistant",...}}], "category": ...}}
```
Compatible con LLaMA-Factory, axolotl, Unsloth y la API de OpenAI.
"""


# Re-export para conveniencia
__all__ = ["build_dataset", "export_jsonl", "classify", "usefulness"]