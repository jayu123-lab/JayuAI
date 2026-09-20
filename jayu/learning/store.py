"""Almacén de aprendizaje (Fase 9): guarda conversaciones útiles.

`LearningStore` persiste ejemplos (prompt → reply) en SQLite junto con
etiquetas: intención, categoría, skills usadas, si fue útil y el modo de
la respuesta. Es la materia prima del dataset para entrenar la LLM
"poco a poco". Nada se sube a ningún sitio.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


class LearningStore:
    """Base SQLite con ejemplos de conversación para entrenamiento futuro."""

    def __init__(self, db_path: str | Path,
                 max_examples: int = 20000) -> None:
        self.db_path = Path(db_path)
        self.max_examples = max_examples
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                session_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                reply TEXT NOT NULL,
                intent TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                skills_used TEXT DEFAULT '[]',
                mode TEXT DEFAULT '',
                useful INTEGER DEFAULT 0,
                useful_reason TEXT DEFAULT '',
                dedup_key TEXT UNIQUE
            )""")
        self._conn.commit()

    # ------------------------------------------------------------------
    def add_example(self, *, prompt: str, reply: str, session_id: str,
                    intent: str = "", category: str = "general",
                    skills_used: list[str] | None = None,
                    mode: str = "", useful: int = 0,
                    useful_reason: str = "") -> int:
        """Inserta un ejemplo. Devuelve el id o -1 si duplicado/fuera de
        capacidad (el dataset se mantiene acotado)."""
        import hashlib
        dedup = hashlib.sha1(
            (prompt.strip().lower() + "|" + reply.strip().lower())
            .encode("utf-8")).hexdigest()
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM examples")
        if cur.fetchone()[0] >= self.max_examples:
            return -1
        try:
            cur = self._conn.execute(
                """INSERT INTO examples
                   (ts, session_id, prompt, reply, intent, category,
                    skills_used, mode, useful, useful_reason, dedup_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), session_id, prompt, reply, intent, category,
                 ",".join(skills_used or []), mode, useful,
                 useful_reason, dedup))
            self._conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return -1

    # ------------------------------------------------------------------
    def mark_useful(self, example_id: int, reason: str = "") -> bool:
        cur = self._conn.execute(
            "UPDATE examples SET useful = 1, useful_reason = ? WHERE id = ?",
            (reason, example_id))
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    def examples(self, *, category: str | None = None,
                 useful: int | None = None,
                 limit: int = 500) -> list[dict[str, Any]]:
        sql = "SELECT * FROM examples"
        conds: list[str] = []
        params: list[Any] = []
        if category:
            conds.append("category = ?")
            params.append(category)
        if useful is not None:
            conds.append("useful = ?")
            params.append(useful)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        cols = [d[0] for d in self._conn.execute("SELECT * FROM examples")
                .description]
        return [dict(zip(cols, r)) for r in rows]

    @property
    def count(self) -> int:
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM examples").fetchone()[0])

    def stats(self) -> dict[str, Any]:
        total = self.count
        by_cat: dict[str, int] = {}
        by_useful = {"utiles": 0, "no_utiles": 0}
        for row in self._conn.execute(
                "SELECT category, useful, COUNT(*) FROM examples "
                "GROUP BY category, useful"):
            cat, useful, n = row[0], row[1], row[2]
            by_cat[cat] = by_cat.get(cat, 0) + n
            by_useful["utiles" if useful else "no_utiles"] += n
        return {"total": total, "por_categoria": by_cat,
                "utilidad": by_useful,
                "max": self.max_examples}

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass