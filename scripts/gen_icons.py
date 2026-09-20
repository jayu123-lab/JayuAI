"""Genera los iconos PWA de JayuAI (cerebro dorado) con Pillow.

Uso:  python scripts/gen_icons.py
Crea jayu/web/static/icons/icon-192.png e icon-512.png (con margen
seguro para `maskable`). Sin Pillow, falla con aviso claro.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "jayu" / "web" / "static" / "icons"


def draw_brain(size: int) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover
        print(f"pillow no instalado: {exc}")
        sys.exit(1)

    img = Image.new("RGBA", (size, size), (10, 14, 26, 255))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2

    # halo
    r_halo = int(size * 0.47)
    for i in range(12, 0, -1):
        alpha = int(10 + i * 2)
        d.ellipse([cx - r_halo + i, cy - r_halo + i,
                   cx + r_halo - i, cy + r_halo - i],
                  outline=(245, 197, 66, alpha), width=1)

    # núcleo dorado (círculo brillante)
    r_core = int(size * 0.26)
    d.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core],
              fill=(250, 213, 120, 255))
    # sombra inferior del núcleo
    d.ellipse([cx - r_core, cy - int(r_core * 0.9),
               cx + r_core, cy + int(r_core * 1.1)],
              fill=(255, 230, 160, 255))
    d.ellipse([cx - int(r_core * 0.85), cy - int(r_core * 0.85),
               cx + int(r_core * 0.85), cy + int(r_core * 0.85)],
              fill=(255, 243, 200, 255))

    # ojos del cerebro
    eye_r = max(2, int(size * 0.045))
    for sgn in (-1, 1):
        ex = cx + int(sgn * r_core * 0.42)
        ey = cy - int(r_core * 0.08)
        d.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r],
                  fill=(40, 24, 4, 255))
        d.ellipse([ex - int(eye_r * 0.45), ey - int(eye_r * 0.45),
                   ex + int(eye_r * 0.05), ey + int(eye_r * 0.05)],
                  fill=(255, 255, 255, 230))

    # partículas doradas alrededor
    import math
    import random
    rng = random.Random(42)
    for _ in range(60):
        ang = rng.random() * 6.2832
        rad = rng.uniform(r_core * 1.15, size * 0.46)
        x = cx + math.cos(ang) * rad
        y = cy + math.sin(ang) * rad
        pr = rng.uniform(1.0, max(2.2, size * 0.006))
        d.ellipse([x - pr, y - pr, x + pr, y + pr],
                  fill=(245, 197, 66, rng.randint(120, 255)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / f"icon-{size}.png")
    print(f"  ok icon-{size}.png ({size}x{size})")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generando iconos JayuAI…")
    draw_brain(192)
    draw_brain(512)
    print("listo.")


if __name__ == "__main__":
    main()