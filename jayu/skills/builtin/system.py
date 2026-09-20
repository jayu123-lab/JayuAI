"""Skill: sistema (estado, ping, información de host). SAFE."""

from __future__ import annotations

import platform
import socket
import time
from datetime import datetime
from typing import Any

from ..base import Skill

PERMISSIONS = ["system.status", "system.ping"]


def _result(ok: bool, **data: Any) -> dict[str, Any]:
    return {"ok": ok, **data}


def ping() -> dict[str, Any]:
    return _result(True, pong=True, ts=time.time())


def now() -> dict[str, Any]:
    return _result(True, iso=datetime.now().isoformat(timespec="seconds"))


def host_info() -> dict[str, Any]:
    return _result(
        True,
        hostname=socket.gethostname(),
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        python=platform.python_version(),
    )


def register(registry) -> None:
    registry.register(Skill(
        name="system",
        description="Estado del sistema: ping, hora, información del host.",
        category="system",
        tools={"ping": ping, "now": now, "host_info": host_info},
        permission_actions=PERMISSIONS,
        version="0.1.0",
    ))