"""Skill: vision — FASE 7 implementada (captura, OCR local, localización).

Tools:
  - capture(...)        vision.capture      SAFE — captura de pantalla a PNG.
  - ocr(image_path)     vision.ocr          SAFE — OCR local (RapidOCR).
  - capture_read(...)   vision.capture_read SAFE — captura + OCR de una región.
  - locate(image, tpl)  vision.locate       SAFE — coordenadas de un patrón.

Nunca se inventa texto ni coordenadas: sin pantalla, sin modelo o sin OpenCV
la skill devuelve ok=False con el motivo exacto.
"""

from __future__ import annotations

from typing import Any

from ...vision.capture import VisionUnavailable, capture_screen
from ...vision.locate import LocateUnavailable, locate_template
from ...vision.ocr import OCRUnavailable, ocr_image
from ..base import Skill


def make_vision_skill() -> Skill:
    # ------------------------------------------------------------------
    def capture(**kw) -> dict[str, Any]:
        try:
            return capture_screen(**{k: v for k, v in kw.items()
                                     if k in ("monitor", "region",
                                              "out_path")})
        except VisionUnavailable as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    def ocr(image_path: str = "", **kw) -> dict[str, Any]:
        if not image_path:
            return {"ok": False, "error": "falta image_path (PNG/JPG)."}
        try:
            return ocr_image(image_path, **{k: v for k, v in kw.items()
                                            if k == "lang"})
        except OCRUnavailable as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    def capture_read(region: dict[str, int] | None = None,
                     monitor: int | None = None, **kw) -> dict[str, Any]:
        try:
            cap = capture_screen(monitor=monitor, region=region)
        except VisionUnavailable as exc:
            return {"ok": False, "error": str(exc)}
        try:
            res = ocr_image(cap["path"])
        except OCRUnavailable as exc:
            res = {"ok": False, "error": str(exc)}
        res["capture"] = {"path": cap["path"], "width": cap["width"],
                          "height": cap["height"]}
        return res

    # ------------------------------------------------------------------
    def locate(image_path: str = "", template_path: str = "",
               threshold: float = 0.75, **kw) -> dict[str, Any]:
        if not image_path or not template_path:
            return {"ok": False,
                    "error": "faltan image_path y template_path."}
        try:
            return locate_template(image_path, template_path,
                                   threshold=threshold)
        except LocateUnavailable as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    return Skill(
        name="vision",
        description="Visión: captura de pantalla, OCR local sin nube y "
                    "localización de patrones (botones/logos).",
        category="vision",
        tools={"capture": capture, "ocr": ocr, "capture_read": capture_read,
               "locate": locate},
        permission_actions=["vision.capture", "vision.ocr",
                            "vision.capture_read", "vision.locate"],
        tool_actions={"capture": "vision.capture", "ocr": "vision.ocr",
                      "capture_read": "vision.capture_read",
                      "locate": "vision.locate"},
        version="0.1.0",
    )