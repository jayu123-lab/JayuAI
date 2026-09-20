"""Carga centralizada de configuración de JAYU_JAR.

Reglas:
- Los YAML de `config/` son la fuente de verdad (no hardcodear sensible).
- Los secretos NUNCA van en YAML; se leen de variables de entorno.
- Cualquier clave de YAML puede sobreescribirse con variables de entorno
  `JAYU_<CLAVE>` (definido en .env.example).

API:
    Settings.load() -> Settings
    settings.config  # dict del settings.yaml
    settings.models  # dict del models.yaml
    settings.permissions  # dict del permissions.yaml
    settings.trading / settings.voice
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - fallback mínimo sin PyYAML
    yaml = None  # type: ignore[assignment]


class ConfigError(Exception):
    """Error de carga/parseo de configuración."""


def project_root() -> Path:
    """Localiza la raíz del proyecto (donde vive `config/`)."""
    env = os.environ.get("JAYU_ROOT")
    if env:
        root = Path(env).resolve()
        if root.is_dir():
            return root
        raise ConfigError(f"JAYU_ROOT no existe: {env}")
    # jayu/config.py -> parents[1] es la raíz
    return Path(__file__).resolve().parents[1]


def load_data_file(path: Path) -> dict[str, Any]:
    """Carga un YAML (o JSON de respaldo) y devuelve dict."""
    if not path.exists():
        raise ConfigError(f"Falta archivo de configuración: {path}")
    raw = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            data = yaml.safe_load(raw)
        except Exception as exc:  # noqa: BLE001
            raise ConfigError(f"YAML inválido en {path.name}: {exc}") from exc
    else:
        try:
            data = json.loads(_yaml_to_json(raw))
        except Exception as exc:  # noqa: BLE001
            raise ConfigError(f"JSON inválido en {path.name}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _yaml_to_json(raw: str) -> str:
    """Conversión mínima de YAML simple a JSON (respaldo sin PyYAML)."""
    out: list[str] = []
    indent = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:]
        if ":" in stripped and not stripped.startswith(("{", "[")):
            k, _, v = stripped.partition(":")
            v = v.strip()
            if v:
                out.append("  " * indent + json.dumps(k) + ": " + v)
        elif stripped in ("true", "false", "null"):
            out.append("  " * indent + stripped)
        else:
            out.append("  " * indent + json.dumps(stripped))
    return "{" + ", ".join(out) + "}"


def _apply_env_overrides(data: dict[str, Any], prefix: str = "JAYU_") -> dict[str, Any]:
    """Aplica sobreescrituras de variables de entorno (prefijo JAYU_)."""
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        nested = data
        parts = key[len(prefix):].lower().split("__")
        for part in parts[:-1]:
            nested = nested.setdefault(part, {})
        if not isinstance(nested, dict):
            continue
        nested[parts[-1]] = _cast(value)
    return data


def _cast(value: str) -> Any:
    low = value.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low == "none":
        return None
    return value


class Settings:
    """Agregado de configuración cargada desde config/."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        env_overrides: bool = True,
    ) -> None:
        self.root = root or project_root()
        self.config_dir = self.root / "config"

        self.config = self._load("settings.yaml", env_overrides=env_overrides)
        self.models_conf = self._load("models.yaml", env_overrides=env_overrides)
        self.permissions_conf = self._load("permissions.yaml", env_overrides=env_overrides)
        self.trading_conf = self._load("trading.yaml", env_overrides=env_overrides)
        self.voice_conf = self._load("voice.yaml", env_overrides=env_overrides)
        self.research_conf = self._load("research.yaml", env_overrides=env_overrides)

    def _load(self, name: str, *, env_overrides: bool) -> dict[str, Any]:
        data = load_data_file(self.config_dir / name)
        if env_overrides:
            data = _apply_env_overrides(data)
        return data

    # -- acceso conveniente -------------------------------------------------
    @property
    def data_dir(self) -> Path:
        p = Path(str(self.config.get("data_dir", "data")))
        return p if p.is_absolute() else (self.root / p)

    @property
    def log_dir(self) -> Path:
        p = Path(str(self.config.get("log_dir", "logs")))
        return p if p.is_absolute() else (self.root / p)

    @property
    def db_path(self) -> Path:
        mem = self.config.get("memory", {})
        fname = mem.get("db_file", "jayu.db")
        p = Path(str(fname))
        return p if p.is_absolute() else (self.data_dir / p)

    @property
    def autonomy_level(self) -> str:
        return str(self.config.get("autonomy_level", "confirm_before_execution"))


def load() -> Settings:
    """Carga Settings con la configuración del proyecto."""
    return Settings()