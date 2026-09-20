"""Logs estructurados (JSON Lines) para JAYU_JAR.

Niveles estándar: DEBUG < INFO < WARNING < ERROR < CRITICAL.
Se escribe un fichero JSONL por componente principal y un fichero
global `jayu.jsonl`. Los eventos de decisión/seguridad se registran
además con metadata propia para trazabilidad completa.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_configured = False
_lock = threading.Lock()

_FILE_FORMAT = "%(asctime)sZ %(levelname)s %(name)s %(message)s"
_CONSOLE_FORMAT = "%(levelname)-8s %(name)-22s %(message)s"


class JsonLineFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("actor", "action", "tool", "decision",
                    "classification", "reason", "result"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(log_dir: Path, *, level: int = logging.INFO) -> str:
    """Configura el logging una única vez. Devuelve la ruta del log global."""
    global _configured
    with _lock:
        if _configured:
            return str(log_dir / "jayu.jsonl")
        log_dir.mkdir(parents=True, exist_ok=True)

        root = logging.getLogger("jayu")
        root.setLevel(level)
        root.handlers.clear()

        file_handler = logging.FileHandler(log_dir / "jayu.jsonl",
                                           encoding="utf-8")
        file_handler.setFormatter(JsonLineFormatter())
        root.addHandler(file_handler)

        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.WARNING)
        console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
        root.addHandler(console)

        root.propagate = False
        _configured = True
        root.info("logging inicializado", extra={"tool": "logging_setup"})
        return str(log_dir / "jayu.jsonl")


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger bajo el namespace `jayu.*`."""
    return logging.getLogger(f"jayu.{name}")


def log_event(
    logger_name: str,
    level: int,
    message: str,
    **metadata: object,
) -> None:
    """Log con metadatos estructurados (actor, action, tool, ...)."""
    get_logger(logger_name).log(level, message, extra=metadata)