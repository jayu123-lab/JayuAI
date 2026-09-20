"""Captura de pantalla multi-monitor (mss) a archivos PNG."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("vision.capture")


class VisionUnavailable(Exception):
    """Dependencia o monitor ausente para capturar pantalla."""


def capture_screen(*, monitor: int | None = None,
                   region: dict[str, int] | None = None,
                   out_path: str | Path | None = None,
                   ) -> dict[str, Any]:
    """Captura el escritorio (monitor 1 por defecto) y guarda un PNG.

    `monitor`: 0 = todos los monitores, 1+ = monitor específico.
    `region`: {left, top, width, height} en píxeles (requiere monitor único).
    Devuelve {ok, path, width, height, monitor}.
    """
    try:
        import mss
    except Exception as exc:  # noqa: BLE001
        raise VisionUnavailable(f"mss no instalado: {exc}") from exc

    out_path = Path(out_path) if out_path else Path(
        tempfile.gettempdir()) / "jayuai_capture.png"

    try:
        with mss.mss() as sct:
            if monitor is None:
                monitor = 1
            if region:
                # región explícita sobre el monitor principal
                box = {"left": int(region["left"]), "top": int(region["top"]),
                       "width": int(region["width"]),
                       "height": int(region["height"])}
            else:
                box = sct.monitors[int(monitor)]
            shot = sct.grab(box)
            import mss.tools
            mss.tools.to_png(shot.rgb, shot.size, output=str(out_path))
    except VisionUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VisionUnavailable(f"captura falló: {exc}") from exc

    return {"ok": True, "path": str(out_path),
            "width": shot.size[0], "height": shot.size[1],
            "monitor": monitor, "region": box}