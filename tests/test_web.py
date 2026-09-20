"""FASE 10 — Tests del servidor web local (sin red, sin audio real,
sin captura de pantalla real)."""

from __future__ import annotations

import json
import urllib.request

import pytest


def _start(tmp_settings, fake_providers, monkeypatch):
    from jayu.core.orchestrator import Orchestrator
    from jayu.web.server import JayuWebServer
    from tests.fakes import FakeMT5, FakeSTT, FakeTTS
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5())
    monkeypatch.setattr(orch, "tts", FakeTTS())
    monkeypatch.setattr(orch, "stt", FakeSTT())
    srv = JayuWebServer(orch, port=0, open_browser=False)
    srv.start(block=False)
    return orch, srv


def _get(url: str):
    # urllib levanta HTTPError para 4xx/5xx; lo convertimos en (status, body)
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(url: str, body: dict):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


# ----------------------------------------------------------------------
def test_web_sirve_interfaz(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/")
        assert status == 200
        html = body.decode("utf-8", "replace")
        assert "JayuAI" in html
        assert "brain" in html.lower()  # cerebro hablante presente
    finally:
        srv.stop(); orch.close()


def test_web_estaticos_y_manifest(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        for path in ("/static/style.css", "/static/app.js",
                     "/static/manifest.json", "/static/sw.js",
                     "/static/icons/icon-192.png",
                     "/static/icons/icon-512.png"):
            status, body = _get(srv.url + path)
            assert status == 200, path
            assert len(body) > 20
    finally:
        srv.stop(); orch.close()


def test_web_api_status(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/api/status")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is True
        assert data["name"]
        assert "skills" in data
        assert data["voice"]["tts"]["installed"] is True
    finally:
        srv.stop(); orch.close()


def test_web_chat(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        res = _post(srv.url + "/api/chat",
                    {"message": "hola", "session_id": "t"})
        assert res["ok"] is True
        assert isinstance(res["reply"], str) and res["reply"]
        assert res["intent"]
        assert res["mode"] in ("ok", "degraded", "offline", "blocked", "tool")
    finally:
        srv.stop(); orch.close()


def test_web_chat_vacio_honesto(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        res = _post(srv.url + "/api/chat", {"message": "  "})
        assert res["ok"] is False
        assert "vacío" in res["error"].lower()
    finally:
        srv.stop(); orch.close()


def test_web_speak_devuelve_audio(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        res = _post(srv.url + "/api/speak", {"text": "hola JayuAI"})
        assert res["ok"] is True
        assert res["url"].startswith("/audio/")
        status, body = _get(srv.url + res["url"])
        assert status == 200
        assert body.startswith(b"ID3")
        # engine falso usado (sin red)
        assert orch.tts.spoken == ["hola JayuAI"]
    finally:
        srv.stop(); orch.close()


def test_web_speak_vacio(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        res = _post(srv.url + "/api/speak", {"text": " "})
        assert res["ok"] is False
    finally:
        srv.stop(); orch.close()


def test_web_mercado_oro(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/api/markets/gold")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is True
        assert data["drivers"]["ok"] is True
        assert data["drivers"]["en_vivo"]["XAUUSD"]["dato"] == "ok"
        assert data["calendar"]["ok"] is True
    finally:
        srv.stop(); orch.close()


def test_web_governor_solo_analisis(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        res = _post(srv.url + "/api/markets/governor",
                    {"symbol": "XAUUSD", "timeframe": "H1", "count": 120})
        assert res["ok"] is True
        assert res["direccion"] in ("BULLISH", "BEARISH", "NEUTRAL")
        assert "executed" not in res or res.get("executed") == []
        # los votos de los especialistas están presentes
        assert "votes" in res
    finally:
        srv.stop(); orch.close()


def test_web_vision_honesta_sin_pantalla(tmp_settings, fake_providers,
                                         monkeypatch):
    from jayu.skills.builtin import vision as vision_module
    from jayu.vision.capture import VisionUnavailable

    def _boom(**kw):
        raise VisionUnavailable("mss no disponible (fake, sin pantalla real)")
    monkeypatch.setattr(vision_module, "capture_screen", _boom)
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/api/vision/read")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is False
        assert "mss" in data["error"]
    finally:
        srv.stop(); orch.close()


def test_web_aprendizaje_y_memoria(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/api/learning")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is True
        assert "total" in data
        status, body = _get(srv.url + "/api/memory")
        assert status == 200
        assert json.loads(body)["ok"] is True
    finally:
        srv.stop(); orch.close()


def test_web_ruta_desconocida(tmp_settings, fake_providers, monkeypatch):
    orch, srv = _start(tmp_settings, fake_providers, monkeypatch)
    try:
        status, body = _get(srv.url + "/api/no-existe")
        assert status == 404
        assert json.loads(body)["ok"] is False
    finally:
        srv.stop(); orch.close()