"""FASE 2 — Voz de JAYUAI (STT + TTS + VAD + audio I/O).

Pipeline:
  micrófono -> [VAD] -> faster-whisper (STT) -> orquestador -> respuesta
  -> TTS (edge-tts: voz neuronal natural, no robótica) -> altavoz

Honestidad: cada motor declara `available()` con su estado exacto. Si un
backend no está instalado o no hay red, la skill devuelve `ok=False` con el
motivo; nunca simula una transcripción ni una síntesis.
"""

from .audio_io import record_wav
from .stt import SpeechToText
from .tts import TextToSpeech
from .vad import trim_silence

__all__ = ["SpeechToText", "TextToSpeech", "record_wav", "trim_silence"]