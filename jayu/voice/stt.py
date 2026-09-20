"""STT — voz a texto con faster-whisper (local, sin nube).

El modelo se descarga la primera vez desde HuggingFace (necesita red una vez)
y luego funciona 100% local en CPU.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

logger = get_logger("voice.stt")


class STTUnavailable(Exception):
    """El motor de STT no puede funcionar (dependencia/modelo ausente)."""


class SpeechToText:
    def __init__(self, *, model: str = "small",
                 device: str = "cpu",
                 compute_type: str = "int8") -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._load_error: str | None = None

    # ------------------------------------------------------------------
    def available(self) -> dict[str, Any]:
        if self._load_error:
            return {"installed": False, "engine": "faster-whisper",
                    "model": self.model_name, "reason": self._load_error}
        try:
            import faster_whisper  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return {"installed": False, "engine": "faster-whisper",
                    "model": self.model_name,
                    "reason": f"faster-whisper no instalado: {exc}"}
        return {"installed": True, "engine": "faster-whisper",
                "model": self.model_name, "device": self.device,
                "compute_type": self.compute_type}

    # ------------------------------------------------------------------
    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"faster-whisper no instalado: {exc}"
            raise STTUnavailable(self._load_error) from exc
        try:
            # El modelo se descarga en la primera ejecución (HF hub).
            self._model = WhisperModel(self.model_name, device=self.device,
                                       compute_type=self.compute_type)
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"no se pudo cargar el modelo '{self.model_name}': {exc}"
            logger.warning(self._load_error)
            raise STTUnavailable(self._load_error) from exc
        return self._model

    # ------------------------------------------------------------------
    def transcribe(self, audio_path: str | Path) -> dict[str, Any]:
        """Transcribe un WAV (16 kHz mono recomendado) a texto."""
        av = self.available()
        if not av["installed"]:
            raise STTUnavailable(av.get("reason", "STT no disponible"))
        path = Path(audio_path)
        if not path.exists():
            raise STTUnavailable(f"Audio no encontrado: {path}")
        model = self._ensure_model()
        try:
            segments, info = model.transcribe(str(path),
                                              language=None,
                                              vad_filter=True)
            text = "".join(seg.text for seg in segments).strip()
        except Exception as exc:  # noqa: BLE001
            raise STTUnavailable(f"Transcripción falló: {exc}") from exc
        return {"ok": True, "text": text, "language": info.language,
                "language_probability": round(float(info.language_probability),
                                              3),
                "model": self.model_name}