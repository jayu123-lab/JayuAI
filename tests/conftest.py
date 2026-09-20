"""Fixtures compartidos de los tests de JAYU_JAR."""

from __future__ import annotations

import pytest

from jayu.config import Settings
from jayu.memory.db import MemoryDB
from jayu.memory.store import MemoryStore

from .fakes import FakeProvider


@pytest.fixture
def tmp_settings(tmp_path) -> Settings:
    """Settings reales (config/) pero con db/log en directorio temporal."""
    s = Settings(env_overrides=False)
    s.config["data_dir"] = str(tmp_path / "data")
    s.config["log_dir"] = str(tmp_path / "logs")
    s.config["memory"] = {**(s.config.get("memory") or {}),
                          "db_file": "test.db"}
    return s


@pytest.fixture
def mem(tmp_path) -> MemoryStore:
    db = MemoryDB(tmp_path / "data" / "test.db")
    try:
        yield MemoryStore(db)
    finally:
        db.close()


@pytest.fixture
def fake_providers():
    return {"ollama": FakeProvider()}