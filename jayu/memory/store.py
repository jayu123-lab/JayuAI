"""Servicios de memoria de JAYU_JAR por niveles.

- Short-term : contexto de conversación (por session_id).
- Working    : tareas y objetivos activos.
- Long-term  : hechos, preferencias y conocimientos persistentes.
- Episodic   : historial de acciones realizadas.
"""

from __future__ import annotations

from typing import Any

from .db import MemoryDB, utc_now


class MemoryStore:
    def __init__(self, db: MemoryDB) -> None:
        self.db = db

    # ---------- SHORT-TERM ----------
    def add_short_term(self, session_id: str, role: str, content: str) -> None:
        self.db.exec(
            "INSERT INTO short_term(session_id, role, content, created) VALUES(?,?,?,?)",
            (session_id, role, content, utc_now()),
        )

    def session_history(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT role, content, created FROM short_term "
            "WHERE session_id=? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        )

    def clear_session(self, session_id: str) -> None:
        self.db.exec("DELETE FROM short_term WHERE session_id=?", (session_id,))

    # ---------- WORKING ----------
    def set_working(self, title: str, payload: str | None = None,
                    status: str = "active") -> None:
        now = utc_now()
        existing = self.db.query(
            "SELECT id, status FROM working WHERE title=?", (title,))
        if existing:
            self.db.exec(
                "UPDATE working SET status=?, payload=?, updated=? WHERE title=?",
                (status, payload, now, title),
            )
        else:
            self.db.exec(
                "INSERT INTO working(title, status, payload, created, updated) "
                "VALUES(?,?,?,?,?)",
                (title, status, payload, now, now),
            )

    def working_tasks(self, status: str | None = "active") -> list[dict[str, Any]]:
        if status is None:
            return self.db.query(
                "SELECT title, status, payload, updated FROM working "
                "ORDER BY updated DESC")
        return self.db.query(
            "SELECT title, status, payload, updated FROM working "
            "WHERE status=? ORDER BY updated DESC", (status,))

    def finish_working(self, title: str) -> None:
        self.db.exec("UPDATE working SET status='done', updated=? WHERE title=?",
                     (utc_now(), title))

    def archive_working(self, title: str) -> None:
        self.db.exec("UPDATE working SET status='archived', updated=? WHERE title=?",
                     (utc_now(), title))

    # ---------- LONG-TERM ----------
    def remember(self, key: str, value: str, category: str = "fact",
                 importance: float = 1.0, source: str | None = None) -> None:
        now = utc_now()
        existing = self.db.query("SELECT id FROM long_term WHERE key=?", (key,))
        if existing:
            self.db.exec(
                "UPDATE long_term SET value=?, category=?, source=?, importance=? "
                "WHERE key=?",
                (value, category, source, importance, key),
            )
        else:
            self.db.exec(
                "INSERT INTO long_term(key, value, category, importance, source, "
                "created, updated) VALUES(?,?,?,?,?,?,?)",
                (key, value, category, importance, source, now, now),
            )

    def recall(self, key: str) -> dict[str, Any] | None:
        rows = self.db.query(
            "SELECT key, value, category, importance, source, updated "
            "FROM long_term WHERE key=?", (key,))
        return rows[0] if rows else None

    def search_long_term(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        like = f"%{query}%"
        return self.db.query(
            "SELECT key, value, category, importance, source, updated "
            "FROM long_term WHERE key LIKE ? OR value LIKE ? OR category LIKE ? "
            "ORDER BY importance DESC, updated DESC LIMIT ?",
            (like, like, like, limit),
        )

    def all_long_term(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT key, value, category, importance, source, updated "
            "FROM long_term ORDER BY importance DESC, updated DESC LIMIT ?",
            (limit,))

    def forget(self, key: str) -> bool:
        cur = self.db.exec("DELETE FROM long_term WHERE key=?", (key,))
        return cur > 0

    # ---------- PERFIL DE USUARIO (preferencias aprendidas) ----------
    def set_pref(self, key: str, value: str) -> None:
        self.remember(key, value, category="preference", importance=2.0)

    def get_pref(self, key: str) -> str | None:
        row = self.recall(key)
        return row["value"] if row and row["category"] == "preference" else None

    def prefs(self) -> list[dict[str, Any]]:
        return [r for r in self.all_long_term() if r["category"] == "preference"]

    # ---------- EPISODIC ----------
    def log_episode(self, kind: str, actor: str, summary: str,
                    detail: str | None = None) -> int:
        return self.db.exec(
            "INSERT INTO episodic(created, kind, actor, summary, detail) "
            "VALUES(?,?,?,?,?)",
            (utc_now(), kind, actor, summary, detail),
        )

    def recent_episodes(self, limit: int = 25) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT created, kind, actor, summary, detail FROM episodic "
            "ORDER BY id DESC LIMIT ?", (limit,))