"""Skill: voz — FASE 2 implementada (STT local + TTS natural).

Tools:
  - status(...)        voice.status  SAFE  — estado de los motores y config.
  - speak(text)        voice.speak   SAFE  — sintetiza y reproduce.
  - transcribe(path)   voice.stt     SAFE  — texto desde un WAV.
  - listen(duration)   voice.listen  SAFE  — graba micro y transcribe.
  - configure(...)     voice.config  REVIEW— cambia voz/tono (confirmado).

Honestidad: si un motor no está instalado o no hay red/micrófono, se devuelve
ok=False con el motivo exacto. Nunca se simula transcripción ni síntesis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ...voice.audio_io import AudioUnavailable, record_wav
from ...voice.stt import STTUnavailable
from ...voice.tts import TTSUnavailable
from ..base import Skill

# Parámetros de configuración de voz admisibles en `configure`.
_VOICE_PARAMS = ("engine", "voice", "rate", "pitch", "volume")


def make_voice_skill(get_tts: Callable[[], Any],
                     get_stt: Callable[[], Any]) -> Skill:
    # ------------------------------------------------------------------
    def status(**kw) -> dict[str, Any]:
        tts = get_tts()
        stt = get_stt()
        out: dict[str, Any] = {"ok": True}
        try:
            out["tts"] = tts.available() if tts else {
                "installed": False, "reason": "motor TTS no conectado"}
        except Exception as exc:  # noqa: BLE001
            out["tts"] = {"installed": False, "reason": str(exc)}
        try:
            out["stt"] = stt.available() if stt else {
                "installed": False, "reason": "motor STT no conectado"}
        except Exception as exc:  # noqa: BLE001
            out["stt"] = {"installed": False, "reason": str(exc)}
        if tts and hasattr(tts, "voice"):
            out["current_voice"] = {"engine": tts.engine, "voice": tts.voice,
                                    "rate": getattr(tts, "rate", None),
                                    "pitch": getattr(tts, "pitch", None)}
        return out

    # ------------------------------------------------------------------
    def speak(text: str = "", **kw) -> dict[str, Any]:
        tts = get_tts()
        if tts is None:
            return {"ok": False, "error": "motor de voz no conectado"}
        if not text.strip():
            return {"ok": False, "error": "texto vacío para hablar."}
        try:
            return tts.speak(text)
        except TTSUnavailable as exc:
            return _err(exc)

    # ------------------------------------------------------------------
    def transcribe(audio_path: str = "", **kw) -> dict[str, Any]:
        stt = get_stt()
        if stt is None:
            return {"ok": False, "error": "motor de voz no conectado"}
        if not audio_path:
            return {"ok": False, "error": "falta audio_path (WAV)."}
        try:
            return stt.transcribe(Path(audio_path))
        except STTUnavailable as exc:
            return _err(exc)

    # ------------------------------------------------------------------
    def listen(duration: float = 5.0, **kw) -> dict[str, Any]:
        stt = get_stt()
        if stt is None:
            return {"ok": False, "error": "motor de voz no conectado"}
        try:
            rec = record_wav(float(duration))
        except AudioUnavailable as exc:
            return _err(exc)
        try:
            out = stt.transcribe(rec["path"])
        except STTUnavailable as exc:
            return _err(exc)
        out["audio"] = {"path": rec["path"], "duration_s": rec["duration_s"]}
        return out

    # ------------------------------------------------------------------
    def configure(**kw) -> dict[str, Any]:
        tts = get_tts()
        if tts is None:
            return {"ok": False, "error": "motor de voz no conectado"}
        updates = {k: v for k, v in kw.items()
                   if k in _VOICE_PARAMS and v not in (None, "")}
        before = {"engine": tts.engine, "voice": tts.voice}
        for key, value in updates.items():
            if key == "voice":
                # validar contra la lista conocida del engine antes de aplicar
                av = tts.available()
                known = av.get("voices_available", [])
                if known and value not in known:
                    return {"ok": False,
                            "error": f"voz '{value}' no soportada por "
                                     f"'{tts.engine}'. Disponibles: {known}"}
            setattr(tts, key, value)
        return {"ok": True, "before": before,
                "after": {"engine": tts.engine, "voice": tts.voice,
                          "rate": getattr(tts, "rate", None),
                          "pitch": getattr(tts, "pitch", None)}}

    # ------------------------------------------------------------------
    return Skill(
        name="voice",
        description="Voz natural: STT local (faster-whisper), TTS neuronal "
                    "no robótico (edge-tts), grabación por micrófono.",
        category="voice",
        tools={"status": status, "speak": speak, "transcribe": transcribe,
               "listen": listen, "configure": configure},
        permission_actions=["voice.status", "voice.speak", "voice.stt",
                            "voice.listen", "voice.config"],
        tool_actions={"status": "voice.status", "speak": "voice.speak",
                      "transcribe": "voice.stt", "listen": "voice.listen",
                      "configure": "voice.config"},
        version="0.2.0",
    )


def _err(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc)}


def register(registry) -> None:
    """Compatibilidad: registra la skill con motores DESCONECTADOS (tests)."""
    registry.register(make_voice_skill(lambda: None, lambda: None))