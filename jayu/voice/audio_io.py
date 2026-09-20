"""Audio I/O — grabar del micrófono y guardar a WAV (sounddevice)."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("voice.audio")


class AudioUnavailable(Exception):
    """No hay dispositivo de captura / sounddevice no instalado."""


def record_wav(duration: float = 5.0, *, sample_rate: int = 16000,
               channels: int = 1, out_path: str | Path | None = None,
               device: int | None = None) -> dict[str, Any]:
    """Graba `duration` segundos del micrófono y guarda un WAV.

    Devuelve {ok, path, duration_s, sample_rate}. Si no hay sounddevice o
    no hay micrófono, devuelve ok=False (error honesto).
    """
    try:
        import sounddevice as sd
    except Exception as exc:  # noqa: BLE001
        raise AudioUnavailable(f"sounddevice no instalado: {exc}") from exc
    try:
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        raise AudioUnavailable(f"numpy no instalado: {exc}") from exc

    out_path = Path(out_path) if out_path else Path(
        tempfile.gettempdir()) / "jayuai_mic.wav"
    try:
        frames = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                        channels=channels, dtype="int16", device=device)
        sd.wait()
    except Exception as exc:  # noqa: BLE001
        raise AudioUnavailable(f"grabación falló: {exc}") from exc
    data = np.asarray(frames)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())
    return {"ok": True, "path": str(out_path), "duration_s": duration,
            "sample_rate": sample_rate, "channels": channels}