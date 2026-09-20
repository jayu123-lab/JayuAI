"""FASE 7 — Tests de visión (captura/OCR/locate) — sin pantalla real ni red."""

from __future__ import annotations


def _skill():
    from jayu.skills.builtin.vision import make_vision_skill
    return make_vision_skill()


# ----------------------------------------------------------------------
# Honestidad: errores claros antes de tocar hardware/modelos
# ----------------------------------------------------------------------

def test_vision_ocr_sin_path():
    res = _skill().tools["ocr"]("")
    assert res["ok"] is False and "image_path" in res["error"]


def test_vision_ocr_archivo_faltante(tmp_path):
    res = _skill().tools["ocr"](str(tmp_path / "no_existe.png"))
    assert res["ok"] is False and "no encontrada" in res["error"]


def test_vision_locate_sin_paths():
    res = _skill().tools["locate"]("", "")
    assert res["ok"] is False and "faltan" in res["error"]


def test_vision_capture_honesta_sin_dependencia(monkeypatch):
    from jayu.skills.builtin import vision as vision_module
    from jayu.vision.capture import VisionUnavailable

    def _boom(**kw):
        raise VisionUnavailable("mss no instalado (fake)")
    monkeypatch.setattr(vision_module, "capture_screen", _boom)
    res = _skill().tools["capture"]()
    assert res["ok"] is False and "mss" in res["error"]


def test_vision_capture_ok_con_fake(monkeypatch):
    from jayu.skills.builtin import vision as vision_module

    def _ok(**kw):
        return {"ok": True, "path": "fake/cap.png", "width": 1280,
                "height": 720, "monitor": kw.get("monitor", 1)}
    monkeypatch.setattr(vision_module, "capture_screen", _ok)
    res = _skill().tools["capture"](monitor=1)
    assert res["ok"] is True and res["path"].endswith(".png")


def test_vision_capture_read_combina(monkeypatch):
    from jayu.skills.builtin import vision as vision_module

    def _ok(**kw):
        return {"ok": True, "path": "fake/cap.png", "width": 1280,
                "height": 720}
    def _ocr(p, **kw):
        return {"ok": True, "text": "Comprar Oro", "lines": [],
                "lines_count": 1, "elapsed_s": 0.1}
    monkeypatch.setattr(vision_module, "capture_screen", _ok)
    monkeypatch.setattr(vision_module, "ocr_image", _ocr)
    res = _skill().tools["capture_read"](region={"left": 0, "top": 0,
                                                 "width": 100, "height": 50})
    assert res["ok"] is True
    assert res["text"] == "Comprar Oro"
    assert res["capture"]["path"].endswith(".png")


# ----------------------------------------------------------------------
# locate_template con imagen sintética (OpenCV puro, sin descargas)
# ----------------------------------------------------------------------

def test_locator_encuentra_patron_sintetico(tmp_path):
    import cv2

    font = cv2.FONT_HERSHEY_SIMPLEX
    (fw, fh), base = cv2.getTextSize("JAYU", font, 1.0, 2)
    img = np_full_text((160, 220), None)  # fondo blanco limpio
    x0, y0 = 60, 60
    cv2.putText(img, "JAYU", (x0, y0), font, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    tpl = img[y0 - fh: y0 + base, x0: x0 + fw]  # glifo exacto "JAYU"

    img_p = tmp_path / "pantalla.png"
    tpl_p = tmp_path / "patron.png"
    cv2.imwrite(str(img_p), img)
    cv2.imwrite(str(tpl_p), tpl)

    res = _skill().tools["locate"](str(img_p), str(tpl_p), threshold=0.7)
    assert res["ok"] is True
    assert res["matches_count"] >= 1
    m = max(res["matches"], key=lambda x: x["confidence"])
    assert abs(m["x"] - x0) <= 2 and abs(m["y"] - (y0 - fh)) <= 2
    assert m["confidence"] > 0.8


def test_locator_sin_match_sintetico(tmp_path):
    import cv2

    img = np_full_text((160, 220), "HELLO WORLD")
    tpl = np_full_text((60, 90), "ZZZ")  # patrón que NO está en la imagen
    tpl = tpl[:40, :70]
    img_p = tmp_path / "a.png"
    tpl_p = tmp_path / "b.png"
    cv2.imwrite(str(img_p), img)
    cv2.imwrite(str(tpl_p), tpl)

    res = _skill().tools["locate"](str(img_p), str(tpl_p), threshold=0.7)
    assert res["ok"] is True
    assert res["matches_count"] == 0


def np_full_text(size, text):
    import cv2
    import numpy as np
    img = np.full((size[0], size[1], 3), 255, dtype=np.uint8)
    if text:
        cv2.putText(img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (0, 0, 0), 2, cv2.LINE_AA)
    return img


# ----------------------------------------------------------------------
# Permisos: leer la pantalla es SAFE (no requiere confirmación humana)
# ----------------------------------------------------------------------

def test_vision_permissions_safe(tmp_settings):
    from jayu.security.policy import Classification, Decision, Policy
    policy = Policy(tmp_settings.permissions_conf, "confirm_before_execution")
    verdict = policy.evaluate("vision.capture")
    assert verdict.classification == Classification.SAFE
    assert verdict.decision == Decision.ALLOW


def test_elapse_normalizacion():
    from jayu.vision.ocr import _elapse_to_s
    assert _elapse_to_s([0.5, 0.2, 0.1]) == 0.8
    assert _elapse_to_s(1.2345) == 1.234
    assert _elapse_to_s(None) == 0.0