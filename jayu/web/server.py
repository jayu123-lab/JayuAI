"""FASE 10 — Servidor web local de JayuAI (chat + cerebro hablante + PWA).

Sirve la interfaz moderna (`jayu/web/static`) y una API JSON local en
127.0.0.1 (solo acceso local). Incluye:
  - POST /api/chat     -> respuesta del orquestador (LLM local como motor).
  - POST /api/speak    -> sintetiza voz (TTS) y devuelve URL del audio.
  - POST /api/listen   -> graba micrófono (STT local) y transcribe.
  - GET  /api/markets/gold  -> especialista oro (drivers/levels/calendar).
  - POST /api/markets/governor -> análisis multi-agente (solo análisis).
  - GET  /api/vision/read   -> captura pantalla + OCR (lectura).
  - GET  /api/learning / api/voice / api/status / api/memory.

Nunca expone ejecución de trading: el governor y las skills solo analizan;
ejecutar sigue requiriendo política + confirmación + modo de trading.
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("web")

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PORT = 8765


# ----------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    server_version = "JayuAI/0.1"
    app: "JayuWebServer"  # type: ignore[assignment]

    # -- log silencioso ------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:
        logger.debug("web %s", fmt % args)

    # ------------------------------------------------------------------
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 1_000_000:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _serve_file(self, path: Path, content_type: str | None = None) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            self._send_json({"ok": False, "error": "archivo no encontrado"},
                            404)
            return
        self.send_response(200)
        self.send_header(
            "Content-Type", content_type or
            mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (API http)
        app = self.app
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html"):
                self._serve_file(STATIC_DIR / "index.html")
            elif path == "/manifest.json":
                self._serve_file(STATIC_DIR / "manifest.json")
            elif path == "/sw.js":
                self._serve_file(STATIC_DIR / "sw.js", "text/javascript")
            elif path.startswith("/static/"):
                rel = path[len("/static/"):]
                fp = (STATIC_DIR / rel).resolve()
                if not str(fp).startswith(str(STATIC_DIR.resolve())):
                    return self._send_json(
                        {"ok": False, "error": "ruta inválida"}, 403)
                self._serve_file(fp)
            elif path.startswith("/audio/"):
                name = Path(path[len("/audio/"):]).name
                fp = app.audio_dir / name
                self._serve_file(fp, "audio/mpeg")
            elif path == "/api/status":
                self._send_json(app.api_status())
            elif path == "/api/voice":
                self._send_json({"ok": True, "tts": app.orch.tts.available(),
                                 "stt": app.orch.stt.available()})
            elif path == "/api/markets/gold":
                self._send_json(app.api_gold())
            elif path == "/api/vision/read":
                self._send_json(app.api_vision_read())
            elif path == "/api/learning":
                self._send_json(app.api_learning())
            elif path == "/api/memory":
                self._send_json(app.api_memory())
            else:
                self._send_json({"ok": False,
                                 "error": f"ruta desconocida: {path}"}, 404)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GET %s -> %s", path, exc)
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self) -> None:  # noqa: N802
        app = self.app
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
            if path == "/api/chat":
                self._send_json(app.api_chat(
                    str(body.get("message", "")).strip(),
                    str(body.get("session_id", "web"))))
            elif path == "/api/speak":
                self._send_json(app.api_speak(
                    str(body.get("text", "")).strip()))
            elif path == "/api/listen":
                self._send_json(app.api_listen(
                    float(body.get("seconds", 5.0))))
            elif path == "/api/markets/governor":
                self._send_json(app.api_governor(body))
            else:
                self._send_json({"ok": False,
                                 "error": f"ruta desconocida: {path}"}, 404)
        except Exception as exc:  # noqa: BLE001
            logger.warning("POST %s -> %s", path, exc)
            self._send_json({"ok": False, "error": str(exc)}, 500)


# ----------------------------------------------------------------------
class JayuWebServer:
    """Servidor HTTP local sobre un orquestador ya construido."""

    def __init__(self, orch, *, host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
        self.orch = orch
        self.audio_dir = orch.settings.data_dir / "web_audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, str] = {}
        handler = type("Handler", (_Handler,), {"app": self})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.port = int(self.httpd.server_address[1])
        self.host = host
        self.open_browser = open_browser
        self.url = f"http://{host}:{self.port}"
        logger.info("web en %s", self.url)

    # ------------------------------------------------------------------
    def start(self, *, block: bool = False) -> None:
        thread = threading.Thread(target=self.httpd.serve_forever,
                                  daemon=True)
        thread.start()
        if self.open_browser:
            webbrowser.open(self.url)

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def api_status(self) -> dict[str, Any]:
        st = self.orch.status()
        # skills disponibles por categoría (para el panel)
        skills = {s["name"]: {"category": s["category"],
                              "version": s["version"],
                              "description": s["description"]}
                  for s in st.get("skills", [])}
        tts = self.orch.tts.available()
        return {"ok": True, "name": st.get("name"),
                "autonomy_level": st.get("autonomy_level"),
                "language": st.get("language"),
                "trading_mode": (st.get("mt5") or {}).get("trading_mode"),
                "mt5_available": (st.get("mt5") or {}).get("available"),
                "providers": st.get("providers", {}),
                "skills": skills,
                "voice": {"tts": tts, "stt": self.orch.stt.available()},
                "url": self.url}

    def api_chat(self, message: str, session_id: str) -> dict[str, Any]:
        if not message:
            return {"ok": False, "error": "mensaje vacío"}
        try:
            res = self.orch.chat(message, session_id=session_id,
                                 interactive=False)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "reply": res.text, "intent": res.intent,
                "mode": res.mode, "provider": res.provider,
                "model": res.model, "session_id": session_id}

    def api_speak(self, text: str) -> dict[str, Any]:
        if not text:
            return {"ok": False, "error": "texto vacío"}
        name = f"jayuai_speak_{int(time.time() * 1000)}.mp3"
        out = self.audio_dir / name
        try:
            res = self.orch.tts.synthesize(text, out_path=out)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "TTS falló")}
        return {"ok": True, "url": f"/audio/{name}",
                "engine": res.get("engine"), "size": out.stat().st_size}

    def api_listen(self, seconds: float) -> dict[str, Any]:
        from ..voice.audio_io import record_wav
        seconds = max(0.5, min(15.0, seconds))
        record = record_wav(seconds,
                            out_path=self.audio_dir / "jayuai_listen.wav")
        if not record.get("ok"):
            return {"ok": False, "error": record.get("error", "grabación "
                                                              "falló")}
        try:
            stt = self.orch.stt.transcribe(record["path"])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        stt["duration_s"] = record.get("duration_s")
        return stt

    def api_gold(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": True}
        g = self.orch.registry.get("gold_analyst")
        if g is None:
            return {"ok": False, "error": "skill gold_analyst no disponible"}
        drivers = self.orch.run_skill(
            "gold_analyst", "drivers", {"symbol": "XAUUSD"}, interactive=False)
        levels = self.orch.run_skill(
            "gold_analyst", "levels", {"symbol": "XAUUSD"}, interactive=False)
        calendar = self.orch.run_skill(
            "gold_analyst", "calendar", {}, interactive=False)
        out["drivers"] = drivers if drivers.get("ok") else {
            "ok": False, "error": drivers.get("error")}
        out["levels"] = levels if levels.get("ok") else {
            "ok": False, "error": levels.get("error")}
        out["calendar"] = calendar if calendar.get("ok") else {
            "ok": False, "error": calendar.get("error")}
        return out

    def api_governor(self, body: dict[str, Any]) -> dict[str, Any]:
        task = {"symbol": str(body.get("symbol", "XAUUSD")),
                "timeframe": str(body.get("timeframe", "H1")),
                "count": int(body.get("count", 300)),
                "macro_context": body.get("macro_context") or {},
                "headlines": body.get("headlines") or []}
        res = self.orch.run_skill("market_governor", "run", task,
                                  interactive=False)
        if not res.get("ok"):
            return res
        d = res.get("decision", {})
        return {"ok": True, "direccion": d.get("direction"),
                "score": d.get("score"), "conviccion": d.get("conviction"),
                "votes": d.get("votes"), "reasons": d.get("reasons"),
                "propuestas": len(res.get("proposals", [])),
                "chain": res.get("chain", {}).get("order", [])}

    def api_vision_read(self) -> dict[str, Any]:
        res = self.orch.run_skill("vision", "capture_read", {},
                                  interactive=False)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "captura falló")}
        return {"ok": True, "text": res.get("text", ""),
                "lines": res.get("lines_count", 0),
                "capture": res.get("capture", {})}

    def api_learning(self) -> dict[str, Any]:
        if self.orch.learning_store is None:
            return {"ok": False,
                    "error": "aprendizaje deshabilitado en config"}
        data = self.orch.learning_store.stats()
        data["ok"] = True
        return data

    def api_memory(self) -> dict[str, Any]:
        rows = self.orch.store.all_long_term(limit=15)
        return {"ok": True, "entradas": rows}


def run_server(orch, *, port: int = DEFAULT_PORT,
               open_browser: bool = True,
               block: bool = True) -> JayuWebServer:
    """Lanza el servidor. Con `block=True` queda sirviendo hasta Ctrl+C."""
    server = JayuWebServer(orch, port=port, open_browser=open_browser)
    server.start(block=False)
    if block:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
    return server