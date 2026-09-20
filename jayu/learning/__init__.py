"""FASE 9 — Aprendizaje gradual (recolección → etiquetado → export).

Convierte conversaciones útiles en un dataset local para entrenar la LLM
poco a poco. Nada sale de la máquina; el fine-tuning real queda
documentado en `data/learning/COMO_ENTRENAR.md`.
"""

from .dataset import build_dataset, export_jsonl
from .labeller import classify, usefulness
from .store import LearningStore

__all__ = ["LearningStore", "classify", "usefulness", "build_dataset",
           "export_jsonl"]