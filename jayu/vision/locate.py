"""Localización de plantillas con OpenCV (matchTemplate).

Sirve para encontrar un botón/logo/patrón dentro de una captura y devolver
sus coordenadas (para clicks posteriores controlados por políticas).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("vision.locate")


class LocateUnavailable(Exception):
    """OpenCV o imágenes ausentes."""


def locate_template(image_path: str | Path, template_path: str | Path,
                    *, threshold: float = 0.75,
                    max_matches: int = 5) -> dict[str, Any]:
    """Busca `template_path` dentro de `image_path`.

    Devuelve {ok, matches: [{x, y, w, h, center_x, center_y, confidence}],
              image_size}. Solo matches con confianza >= threshold.
    """
    try:
        import cv2
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        raise LocateUnavailable(f"opencv/numpy no instalados: {exc}") from exc

    img_p = Path(image_path)
    tpl_p = Path(template_path)
    if not img_p.exists():
        raise LocateUnavailable(f"Imagen no encontrada: {img_p}")
    if not tpl_p.exists():
        raise LocateUnavailable(f"Plantilla no encontrada: {tpl_p}")

    try:
        img = cv2.imread(str(img_p), cv2.IMREAD_COLOR)
        tpl = cv2.imread(str(tpl_p), cv2.IMREAD_COLOR)
        if img is None:
            raise LocateUnavailable(f"No se pudo leer la imagen: {img_p}")
        if tpl is None:
            raise LocateUnavailable(f"No se pudo leer la plantilla: {tpl_p}")
        h, w = tpl.shape[:2]
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
        # regiones de varianza cero (fondos uniformes) dan valores
        # inestables/NaN: nunca son matches reales
        res[np.isnan(res)] = -1.0
        loc = np.where(res >= float(threshold))
        matches: list[dict[str, Any]] = []
        ih, iw = img.shape[:2]
        # filtrar solapamientos: ordena por confianza desc
        # loc = (rows, cols) -> se invierte para iterar (x, y)
        scored = sorted(
            ((float(res[pt[1], pt[0]]), int(pt[0]), int(pt[1]))
             for pt in zip(*loc[::-1])),
            key=lambda t: t[0], reverse=True)
        used: list[Any] = []
        for conf, x, y in scored:
            if any(abs(x - ux) < w and abs(y - uy) < h
                   for ux, uy in used):
                continue
            used.append((x, y))
            matches.append({
                "x": x, "y": y, "w": int(w), "h": int(h),
                "center_x": x + w // 2, "center_y": y + h // 2,
                "confidence": round(conf, 4)})
            if len(matches) >= max_matches:
                break
    except LocateUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LocateUnavailable(f"localización falló: {exc}") from exc

    return {"ok": True, "matches": matches, "matches_count": len(matches),
            "image_size": {"width": iw, "height": ih},
            "template_size": {"width": int(w), "height": int(h)},
            "threshold": threshold}