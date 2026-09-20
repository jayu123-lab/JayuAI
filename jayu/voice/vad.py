"""VAD — detección de actividad de voz por energía (numpy puro).

Suficiente para recortar silencios antes de transcribir y para el modo
push-to-talk. no requiere webrtcvad (que no tiene wheels en todas las
versiones de Python).
"""

from __future__ import annotations

import wave
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


def read_wav(path: str) -> tuple[Any, int]:
    """Devuelve (señal mono float [-1,1], sample_rate) de un WAV."""
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
        if wf.getnchannels() == 1:
            data = np.frombuffer(raw, dtype=np.int16)
        else:
            stereo = np.frombuffer(raw, dtype=np.int16)
            data = stereo[::2]
    return data.astype(np.float32) / 32768.0, sr


def _rms(x: Any, frame: int, sr: int, t: float) -> float:
    i0 = int(t * sr)
    seg = x[i0:i0 + frame]
    if len(seg) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(seg))))


def trim_silence(path: str, *, threshold_db: float = -35.0,
                 min_voice_s: float = 0.2,
                 padding_s: float = 0.15) -> dict[str, Any]:
    """Recorta silencio inicial/final del WAV.

    threshold_db: RMS por debajo del cual se considera silencio.
    Devuelve {start_s, end_s, duration_s, trimmed} para recortar luego.
    """
    if np is None:
        return {"error": "numpy no instalado"}
    x, sr = read_wav(path)
    duration = len(x) / sr
    frame = max(1, int(sr * 0.02))          # ventana de 20 ms
    threshold = 10.0 ** (threshold_db / 20.0)
    step = 0.02
    start = 0.0
    voiced = 0.0
    for t in np.arange(0.0, duration, step):
        if _rms(x, frame, sr, float(t)) > threshold:
            if voiced == 0.0:
                start = max(0.0, float(t) - padding_s)
            voiced += step
        else:
            if voiced > min_voice_s:
                break
    end = duration
    for t in np.arange(duration, 0.0, -step):
        if _rms(x, frame, sr, max(0.0, float(t) - step)) > threshold:
            end = min(duration, float(t) + padding_s)
            break
    if end <= start:
        return {"start_s": 0.0, "end_s": duration, "duration_s": duration,
                "trimmed": False, "voiced_s": 0.0}
    return {"start_s": round(start, 2), "end_s": round(end, 2),
            "duration_s": round(duration, 2),
            "voiced_s": round(max(0.0, end - start), 2), "trimmed": True}