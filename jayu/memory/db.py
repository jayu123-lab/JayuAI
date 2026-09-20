"""Capa de persistencia SQLite de JAYU_JAR.

Backbone durable con stdlib (sqlite3). Diseñada para migrar después a
PostgreSQL / vector DB / RAG cambiando únicamente este módulo.

Tablas:
    short_term  -> contexto de la conversación actual
    working     -> tareas activas / objetivos / procesos en curso
    long_term   -> hechos, preferencias, conocimientos aprendidos
    episodic    -> historial de lo que JAYU ha hecho
    audit_log   -> quién, qué, cuándo, por qué, qué herramienta, resultado
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS short_term (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_short_session ON short_term(session_id, id);

CREATE TABLE IF NOT EXISTS working (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title   TEXT NOT NULL UNIQUE,
    status  TEXT NOT NULL DEFAULT 'active',
    payload TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS long_term (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT NOT NULL UNIQUE,
    value      TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'fact',
    importance REAL NOT NULL DEFAULT 1.0,
    source     TEXT,
    created    TEXT NOT NULL,
    updated    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_long_category ON long_term(category);

CREATE TABLE IF NOT EXISTS episodic (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    kind    TEXT NOT NULL,
    actor   TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created        TEXT NOT NULL,
    actor          TEXT NOT NULL,
    action         TEXT NOT NULL,
    classification TEXT NOT NULL,
    decision       TEXT NOT NULL,
    reason         TEXT,
    tool           TEXT,
    result         TEXT,
    session        TEXT
);
"""


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class MemoryDB:
    """Conexión SQLite con bloqueo para uso desde varios hilos."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # -- primitivas ---------------------------------------------------------
    def exec(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            up = sql.lstrip().upper()
            if up.startswith(("DELETE", "UPDATE")):
                return cur.rowcount if cur.rowcount >= 0 else 0
            return cur.lastrowid

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()