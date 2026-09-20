"""Tests de la capa de configuración."""

from __future__ import annotations

import pytest

from jayu.config import ConfigError, Settings, load_data_file, project_root


def test_project_root_exists():
    root = project_root()
    assert (root / "config").is_dir()
    assert (root / "main.py").exists() or (root / "jayu").is_dir()


def test_load_settings_has_expected_keys(tmp_settings):
    assert tmp_settings.config.get("name") == "JayuAI"
    assert tmp_settings.config.get("autonomy_level") == "confirm_before_execution"
    assert "providers" in tmp_settings.models_conf
    assert "actions" in tmp_settings.permissions_conf
    assert "mode" in tmp_settings.trading_conf
    assert "pipeline" in tmp_settings.voice_conf


def test_missing_config_file_raises():
    with pytest.raises(ConfigError):
        load_data_file(project_root() / "config" / "no_existe.yaml")


def test_env_override(monkeypatch, tmp_path):
    d = {"base": {"host": "x"}}
    monkeypatch.setenv("JAYU_BASE__HOST", "127.0.0.1")
    s = Settings(env_overrides=True)
    # para no depender de la variable, comprobamos mecanismo de casteo
    from jayu.config import _apply_env_overrides
    out = _apply_env_overrides(d)
    assert out["base"]["host"] == "127.0.0.1"


def test_db_path_is_under_data_dir(tmp_settings):
    assert str(tmp_settings.db_path).endswith("test.db")
    assert "data" in str(tmp_settings.db_path)