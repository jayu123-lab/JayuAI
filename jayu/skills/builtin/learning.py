"""Skill: learning — FASE 9 (aprender poco a poco).

Tools:
  - status(category)   learning.status  SAFE — estado del dataset local.
  - stats()            learning.stats   SAFE — recuentos por categoría/utilidad.
  - capture(id=None)   learning.capture SAFE — marca ejemplos como útiles.
  - export(...)        learning.export  SAFE — dataset JSONL para fine-tuning
                                             (a disco local, nunca a la nube).

Todo es local y de solo lectura/preparación. La captura automática la hace
el orquestador tras cada respuesta (ver config/learning.yaml).
"""

from __future__ import annotations

from typing import Any

from ..base import Skill


def make_learning_skill(get_store) -> Skill:
    # ------------------------------------------------------------------
    def status(**kw) -> dict[str, Any]:
        store = get_store()
        if store is None:
            return {"ok": False, "error": "almacén de aprendizaje no "
                                          "inicializado"}
        return {"ok": True, **store.stats()}

    # ------------------------------------------------------------------
    def stats(**kw) -> dict[str, Any]:
        return status(**kw)

    # ------------------------------------------------------------------
    def capture(example_id: int | None = None, **kw) -> dict[str, Any]:
        store = get_store()
        if store is None:
            return {"ok": False, "error": "almacén no inicializado"}
        if example_id is None:
            # marcar como útiles los ejemplos aún sin etiquetar (revisión)
            n = 0
            for ex in store.examples(useful=0, limit=500):
                if store.mark_useful(ex["id"], "marcado a mano"):
                    n += 1
            return {"ok": True, "marcados": n,
                    "nota": "sin explícito de grabación del último turno: "
                            "los ejemplos ya están etiquetados en escritura"}
        ok = store.mark_useful(int(example_id), "marcado a mano")
        return {"ok": ok, "id": example_id}

    # ------------------------------------------------------------------
    def export(format: str = "openai", limit: int = 5000,
               only_useful: bool = True, out_dir: str = "") -> dict[str, Any]:
        from ...learning.dataset import export_jsonl
        store = get_store()
        if store is None:
            return {"ok": False, "error": "almacén no inicializado"}
        if format != "openai":
            return {"ok": False,
                    "error": f"formato '{format}' no soportado (openai)"}
        out = out_dir or _default_out_dir()
        return export_jsonl(store, out, only_useful=only_useful,
                            limit=int(limit))

    # ------------------------------------------------------------------
    def _default_out_dir():
        import os
        from ...config import project_root
        root = project_root()
        conf_dir = os.environ.get("JAYUAI_LEARNING_DIR", "")
        base = root / "data" / "learning"
        return conf_dir or str(base)

    return Skill(
        name="learning",
        description="Aprendizaje gradual: recolecta conversaciones útiles, "
                    "las etiqueta y exporta un dataset local (JSONL de "
                    "fine-tuning). Nada se sube a la nube.",
        category="learning",
        tools={"status": status, "stats": stats, "capture": capture,
               "export": export},
        permission_actions=["learning.status", "learning.stats",
                            "learning.capture", "learning.export"],
        tool_actions={"status": "learning.status", "stats": "learning.stats",
                      "capture": "learning.capture",
                      "export": "learning.export"},
        version="0.1.0",
    )