"""Skill: voz — PENDIENTE (Fase 2).

El pipeline STT -> interpretación -> razonamiento -> respuesta -> TTS con
VAD e interrupciones se implementará en la Fase 2 (faster-whisper + Piper).
Estado actual: no hay motor de voz.
"""

from __future__ import annotations

from typing import Any

from ..base import Skill

PERMISSIONS = ["voice.config"]


def _not_implemented(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "implemented": False,
        "phase": "FASE 2 - voz (faster-whisper + Piper + VAD)",
        "message": ("La voz todavía no está implementada. El plan: faster-"
                    "whisper (STT), Piper o Kokoro (TTS femenino local), "
                    "webrtcvad para interrupciones."),
    }


def transcribe(audio_path: str = "") -> dict[str, Any]:
    return _not_implemented("transcribe")


def speak(text: str = "") -> dict[str, Any]:
    return _not_implemented("speak")


def register(registry) -> None:
    registry.register(Skill(
        name="voice",
        description="Voz: STT, TTS femenino local y detección de "
                    "interrupciones. PENDIENTE: Fase 2.",
        category="voice",
        tools={"transcribe": transcribe, "speak": speak},
        permission_actions=PERMISSIONS,
        version="0.1.0",
    ))