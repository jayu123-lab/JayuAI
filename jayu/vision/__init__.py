"""FASE 7 — Visión de JayuAI (captura de pantalla, OCR local y localización).

  - capture.py: captura de pantalla multi-monitor (mss) -> PNG.
  - ocr.py:     OCR local con RapidOCR (onnxruntime, sin nube ni torch).
  - locate.py:  localización de plantillas/patrones con OpenCV.

Honestidad: si una dependencia no está instalada o no hay pantalla/monitor,
las tools devuelven ok=False con el motivo exacto. Nunca se inventa un OCR.
"""

from .capture import VisionUnavailable, capture_screen
from .locate import locate_template
from .ocr import ocr_image

__all__ = ["capture_screen", "ocr_image", "locate_template",
           "VisionUnavailable"]