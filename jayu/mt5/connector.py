"""MT5Connector — capa de LECTURA con MetaTrader 5.

Todo lo que es análisis (cuenta, posiciones, órdenes, OHLC, ticks, símbolos,
historial) pasa por aquí. NUNCA ejecuta operaciones: la ejecución vive en
`execution.py` y es la única vía protegida por permisos.

El módulo MetaTrader5 se inyecta opcionalmente (`mt5_module`) para poder
probar con un módulo falso (ver tests/fakes.py).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

TIMEFRAME_ALIASES = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1", "MN1": "TIMEFRAME_MN1",
}


class MT5Error(Exception):
    def __init__(self, message: str, *, hint: str = "", code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.code = code

    def __str__(self) -> str:
        base = f"{self.message}"
        if self.code:
            base += f" (código {self.code})"
        if self.hint:
            base += f" — {self.hint}"
        return base


def _import_mt5() -> Any:
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError as exc:
        raise MT5Error(
            "El paquete MetaTrader5 no está instalado.",
            hint="python -m pip install MetaTrader5",
        ) from exc


class MT5Connector:
    """Wrapper de lectura sobre la API `MetaTrader5`."""

    def __init__(
        self,
        *,
        mt5_module: Any | None = None,
        terminal_path: str | None = None,
        connect_on_use: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        if mt5_module is not None:
            self._mt5 = mt5_module
            self._available = True
        else:
            try:
                self._mt5 = _import_mt5()
                self._available = True
            except MT5Error:
                self._mt5 = None
                self._available = False
        self.terminal_path = terminal_path
        self._connected = False
        self._connect_on_use = connect_on_use

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """¿Está el paquete Python MetaTrader5 disponible?"""
        return self._available

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, login: int | None = None, password: str | None = None,
                server: str | None = None, *, timeout: int = 30) -> bool:
        """Conecta al terminal (si no está ya, lo arranca desde la ruta)."""
        if not self._available:
            return False
        with self._lock:
            kwargs: dict[str, Any] = {"timeout": timeout}
            if self.terminal_path:
                kwargs["path"] = self.terminal_path
            if login:
                kwargs["login"] = login
                kwargs["password"] = password or ""
                if server:
                    kwargs["server"] = server
            try:
                self._connected = bool(self._mt5.initialize(**kwargs))
            except Exception as exc:  # noqa: BLE001
                self._connected = False
                raise MT5Error(f"initialize() falló: {exc}",
                               hint="¿El terminal MT5 está instalado?") from exc
            return self._connected

    def _ensure(self) -> None:
        if not self._available:
            raise MT5Error("MetaTrader5 no disponible en esta máquina.")
        if self._connect_on_use and not self._connected:
            if not self.connect():
                code, text = (self.last_error()
                              if self._mt5 else (None, "sin módulo"))
                raise MT5Error("No hay conexión con el terminal MT5.",
                               hint="Abre MetaTrader 5 y entra en tu cuenta.",
                               code=code)
        if not self._connected:
            raise MT5Error("Terminal MT5 no conectado.",
                           hint="Usa connector.connect(...) o abre el terminal.")

    def shutdown(self) -> None:
        with self._lock:
            if self._available and self._mt5 is not None:
                try:
                    self._mt5.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            self._connected = False

    def last_error(self) -> tuple[int, str]:
        if not self._available or self._mt5 is None:
            return (-1, "MetaTrader5 no disponible")
        try:
            return tuple(self._mt5.last_error())
        except Exception:  # noqa: BLE001
            return (-1, "last_error() no disponible")

    def status(self) -> dict[str, Any]:
        """Estado de la integración (lectura)."""
        if not self._available:
            return {"available": False, "connected": False,
                    "reason": "Paquete MetaTrader5 no instalado"}
        return {"available": True, "connected": self._connected,
                "terminal_path": self.terminal_path,
                "error": list(self.last_error())}

    # ------------------------------------------------------------------
    # Cuenta
    # ------------------------------------------------------------------
    def account_info(self) -> dict[str, Any]:
        self._ensure()
        acc = self._mt5.account_info()
        if acc is None:
            raise MT5Error("account_info() devolvió None.",
                           hint=f"last_error={self.last_error()}")
        return _as_dict(acc)

    # ------------------------------------------------------------------
    # Posiciones y órdenes
    # ------------------------------------------------------------------
    def positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        self._ensure()
        try:
            rows = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        except TypeError:
            rows = self._mt5.positions_get()
        return [_as_dict(p) for p in (rows or [])]

    def orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Órdenes pendientes (pending orders)."""
        self._ensure()
        rows = self._mt5.orders_get(symbol=symbol) if symbol else self._mt5.orders_get()
        return [_as_dict(o) for o in (rows or [])]

    # ------------------------------------------------------------------
    # Símbolos
    # ------------------------------------------------------------------
    def symbols(self) -> list[str]:
        self._ensure()
        syms = self._mt5.symbols_get()
        return [s.name for s in (syms or []) if getattr(s, "name", None)]

    def symbol_info(self, name: str) -> dict[str, Any]:
        self._ensure()
        info = self._mt5.symbol_info(name)
        if info is None:
            raise MT5Error(f"Símbolo '{name}' no disponible en este broker.",
                           hint="Consulta connector.symbols() para ver la lista.")
        d = _as_dict(info)
        # campos clave para análisis y cálculo de lote
        keys = ("name", "digits", "point", "bid", "ask", "spread",
                "trade_tick_value", "trade_tick_size", "trade_contract_size",
                "volume_min", "volume_max", "volume_step",
                "trade_mode", "trade_stops_level", "description", "currency_base",
                "currency_profit", "session_open", "session_close")
        return {k: d.get(k) for k in keys if k in d}

    def quote(self, name: str) -> dict[str, Any]:
        """Cotización puntual bid/ask/spread con sello de tiempo opcional."""
        info = self.symbol_info(name)
        return {"symbol": name, "bid": info.get("bid"), "ask": info.get("ask"),
                "spread_points": info.get("spread"),
                "digits": info.get("digits")}

    # ------------------------------------------------------------------
    # Datos de mercado (OHLC / ticks / historial)
    # ------------------------------------------------------------------
    def timeframe(self, alias: str) -> Any:
        """Traduce alias ('M5','H1','D1'…) al atributo TIMEFRAME_* del módulo."""
        attr = TIMEFRAME_ALIASES.get(str(alias).upper())
        if not attr or not hasattr(self._mt5, attr):
            raise MT5Error(f"Timeframe desconocido: '{alias}'.",
                           hint="Usa M1 M5 M15 M30 H1 H4 D1 W1 MN1")
        return getattr(self._mt5, attr)

    def rates(self, symbol: str, timeframe: str = "H1",
              count: int = 100, from_pos: int = 0) -> list[dict[str, Any]]:
        """Velas OHLC (usar count<=~5000 en primera llamada)."""
        self._ensure()
        tf = self.timeframe(timeframe)
        try:
            arr = self._mt5.copy_rates_from_pos(symbol, tf, from_pos, count)
        except Exception as exc:  # noqa: BLE001
            raise MT5Error(f"copy_rates({symbol},{timeframe}) falló: {exc}",
                           hint="¿Símbolo visible en Market Watch?") from exc
        if arr is None or len(arr) == 0:
            raise MT5Error(
                f"Sin datos OHLC para {symbol} {timeframe} "
                f"(last_error={self.last_error()}).",
                hint="Puede que el broker limite historial; baja count.")
        out = []
        for row in arr:
            d = {f: _py(row[f]) for f in row.dtype.names}
            out.append(d)
        return out

    def ticks(self, symbol: str, count: int = 100,
              from_pos: int = 0) -> list[dict[str, Any]]:
        self._ensure()
        try:
            arr = self._mt5.copy_ticks_from_pos(symbol, from_pos, count)
        except Exception as exc:  # noqa: BLE001
            raise MT5Error(f"copy_ticks({symbol}) falló: {exc}") from exc
        if arr is None or len(arr) == 0:
            raise MT5Error(f"Sin ticks para {symbol}.", hint=str(self.last_error()))
        return [{f: _py(row[f]) for f in row.dtype.names} for row in arr]

    def history(self, *, days: int = 7,
                symbol: str | None = None) -> dict[str, Any]:
        """Historial de deals y órdenes de los últimos N días (lectura)."""
        self._ensure()
        now = datetime.now(timezone.utc)
        from_ = now.timestamp() - days * 86400
        to = now.timestamp()
        deals = self._mt5.history_deals_get(from_, to, symbol=symbol) \
            if symbol else self._mt5.history_deals_get(from_, to)
        orders = self._mt5.history_orders_get(from_, to, symbol=symbol) \
            if symbol else self._mt5.history_orders_get(from_, to)
        return {
            "days": days,
            "deals": [_as_dict(d) for d in (deals or [])],
            "orders": [_as_dict(o) for o in (orders or [])],
        }


# -----------------------------------------------------------------------

def _as_dict(obj: Any) -> dict[str, Any]:
    """Convierte tuplas/namedtuples/arrays de la API MT5 a dict."""
    if hasattr(obj, "_asdict"):
        return {k: _py(v) for k, v in obj._asdict().items()}
    if isinstance(obj, dict):
        return {k: _py(v) for k, v in obj.items()}
    raise MT5Error(f"No se pudo convertir a dict: {type(obj).__name__}")


def _py(value: Any) -> Any:
    import numpy as np
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (bytes, bytearray)):
        return value.decode(errors="replace")
    return value