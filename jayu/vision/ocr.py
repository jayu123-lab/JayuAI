"""OCR local con RapidOCR (onnxruntime) — sin nube ni GPU necesaria.

Los modelos ONNX de RapidOCR se descargan la primera vez; si no hay red ni
modelos, la función devuelve el error exacto (nunca inventa un texto).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("vision.ocr")


class OCRUnavailable(Exception):
    """OCR no disponible (dependencia/modelo ausente)."""


def _elapse_to_s(elapse) -> float:
    """RapidOCR devuelve elapse como lista [det, cls, recog] o float."""
    if isinstance(elapse, (list, tuple)):
        return round(sum(float(e) for e in elapse if e is not None), 3)
    return round(float(elapse), 3)


def ocr_image(image_path: str | Path, *, lang: str = "es",
              ) -> dict[str, Any]:
    path = Path(image_path)
    if not path.exists():
        raise OCRUnavailable(f"Imagen no encontrada: {path}")
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # noqa: BLE001
        raise OCRUnavailable(f"rapidocr-onnxruntime no instalado: {exc}") from exc
    try:
        engine = RapidOCR()
        result, elapse = engine(str(path))
    except Exception as exc:  # noqa: BLE001
        raise OCRUnavailable(f"OCR falló: {exc}") from exc

    lines: list[dict[str, Any]] = []
    text_parts: list[str] = []
    if result:
        for item in result:
            # item: [box, texto, confianza]
            if len(item) >= 3:
                box = item[0]
                txt = str(item[1])
                conf = float(item[2]) if item[2] is not None else 0.0
            else:
                box, txt, conf = None, str(item[1]), 0.0
            lines.append({"text": txt, "confidence": conf, "box": box})
            text_parts.append(txt)
    return {"ok": True, "text": "\n".join(text_parts), "lines": lines,
            "lines_count": len(lines),
            "elapsed_s": _elapse_to_s(elapse)}