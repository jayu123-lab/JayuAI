"""TTS — texto a voz con tono natural (no robótico).

Backends:
  - ``edge``  (por defecto): voz neuronal de Microsoft Edge. Muy natural,
    multiidioma, con rate/pitch ajustables. Requiere red en la síntesis.
  - ``piper`` (alternativa 100% local): no requiere red, pero suena menos
    natural. No disponible hasta que ``piper-tts`` esté instalado.

La configuración (voz, rate, pitch) busca dar un tono cálido/fluido.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("voice.tts")

# Voz femenina española cálida y fluida (es-MX tiene un tono muy natural).
EDGE_VOICES = ["es-ES-ElviraNeural", "es-MX-DaliaNeural", "es-MX-SalomeNeural",
               "es-ES-AlvaroNeural", "es-AR-ElenaNeural"]
PIPER_ES_VOICES = ["es_ES-davefx-medium", "es_ES-sharvard-medium",
                   "es_MX-claude-high"]


class TTSUnavailable(Exception):
    """El motor de TTS no puede funcionar (no instalado / sin red)."""


class TextToSpeech:
    def __init__(
        self,
        *,
        engine: str = "edge",
        voice: str = "es-MX-DaliaNeural",
        rate: str = "+0%",
        pitch: str = "-2Hz",
        output_dir: str | Path | None = None,
        volume: str = "+0%",
    ) -> None:
        self.engine = engine
        self.voice = voice
        self.rate = rate            # ejemplo: "+10%" para respuestas ágiles
        self.pitch = pitch          # "-2Hz": tono algo más grave y cálido
        self.volume = volume
        self.output_dir = Path(output_dir) if output_dir else Path(
            tempfile.gettempdir()) / "jayuai_voice"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def available(self) -> dict[str, Any]:
        info: dict[str, Any] = {"engine": self.engine, "voice": self.voice,
                                "installed": False}
        if self.engine == "edge":
            try:
                import edge_tts  # noqa: F401
                info["installed"] = True
                info["voices_available"] = EDGE_VOICES
                info["online_required"] = True
            except Exception as exc:  # noqa: BLE001
                info["reason"] = f"edge-tts no instalado: {exc}"
        else:  # piper
            try:
                import piper  # noqa: F401
                info["installed"] = True
                info["voices_available"] = PIPER_ES_VOICES
                info["online_required"] = False
            except Exception as exc:  # noqa: BLE001
                info["reason"] = f"piper-tts no instalado: {exc}"
        return info

    # ------------------------------------------------------------------
    def synthesize(self, text: str, out_path: str | Path | None = None,
                   ) -> dict[str, Any]:
        """Genera el audio de `text` y devuelve la ruta (sin reproducir)."""
        av = self.available()
        if not av["installed"]:
            raise TTSUnavailable(av.get("reason", f"backend {self.engine} "
                                                  "no disponible"))
        out_path = Path(out_path) if out_path else (
            self.output_dir / "jayuai_speak.mp3")
        text = text.strip()
        if not text:
            raise TTSUnavailable("texto vacío para sintetizar.")
        if self.engine == "edge":
            return self._synthesize_edge(text, out_path)
        return self._synthesize_piper(text, out_path)

    # ------------------------------------------------------------------
    def speak(self, text: str, *, wait: bool = True,
              out_path: str | Path | None = None) -> dict[str, Any]:
        """Sintetiza y reproduce por el altavoz del sistema."""
        out = self.synthesize(text, out_path=out_path)
        player = _play_audio(out["path"], wait=wait)
        return {"ok": True, "engine": self.engine, "voice": self.voice,
                "path": out["path"], "player": player}

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------
    def _synthesize_edge(self, text: str, out_path: Path) -> dict[str, Any]:
        try:
            import edge_tts
        except Exception as exc:  # noqa: BLE001
            raise TTSUnavailable(f"edge-tts no instalado: {exc}") from exc
        try:
            communicate = edge_tts.Communicate(
                text, self.voice, rate=self.rate, pitch=self.pitch,
                volume=self.volume)
            asyncio.run(communicate.save(str(out_path)))
        except Exception as exc:  # noqa: BLE001
            raise TTSUnavailable(
                f"Síntesis edge falló (¿sin red?): {exc}") from exc
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise TTSUnavailable("edge-tts no generó audio (¿sin red?).")
        return {"ok": True, "engine": "edge", "voice": self.voice,
                "path": str(out_path), "size": out_path.stat().st_size}

    def _synthesize_piper(self, text: str, out_path: Path) -> dict[str, Any]:
        try:
            import piper
        except Exception as exc:  # noqa: BLE001
            raise TTSUnavailable(f"piper-tts no instalado: {exc}") from exc
        # Piper usa onnx; la voz debe estar descargada. Si falta, aviso honesto.
        try:
            piper.synthesize(text, self.voice, str(out_path))
        except Exception as exc:  # noqa: BLE001
            raise TTSUnavailable(f"Síntesis piper falló: {exc}") from exc
        return {"ok": True, "engine": "piper", "voice": self.voice,
                "path": str(out_path), "size": out_path.stat().st_size}


# -----------------------------------------------------------------------
def _play_audio(path: str | Path, wait: bool = True) -> dict[str, Any]:
    """Reproduce un archivo de audio con pygame. Si no hay pygame, honesto."""
    try:
        import pygame
    except Exception as exc:  # noqa: BLE001
        return {"played": False,
                "reason": f"pygame no instalado: {exc} (archivo en {path})"}
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        if wait:
            while pygame.mixer.music.get_busy():
                import time
                time.sleep(0.05)
        return {"played": True, "path": str(path)}
    except Exception as exc:  # noqa: BLE001
        return {"played": False, "reason": str(exc)}


def available_engines() -> dict[str, dict[str, Any]]:
    """Estado de cada backend TTS (para status / configuración)."""
    out: dict[str, dict[str, Any]] = {}
    for engine in ("edge", "piper"):
        try:
            tts = TextToSpeech(engine=engine)
            out[engine] = tts.available()
        except Exception as exc:  # noqa: BLE001
            out[engine] = {"installed": False,
                           "reason": f"error al instanciar: {exc}"}
    return out