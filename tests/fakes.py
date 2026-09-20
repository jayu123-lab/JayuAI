"""Proveedor falso para tests (sin red)."""

from __future__ import annotations

import types
from typing import Any

from jayu.models.providers import LLMError

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

FAKE_ANSWER = "Respuesta de prueba JAYU."

_RATES_DTYPE = [
    ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
    ("close", "f8"), ("tick_volume", "i8"), ("spread", "i8"),
    ("real_volume", "i8"),
]
_TICKS_DTYPE = [
    ("time", "i8"), ("bid", "f8"), ("ask", "f8"), ("last", "f8"),
    ("volume", "i8"), ("time_msc", "i8"), ("flags", "i8"),
]

DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"]


class FakeMT5:
    """Módulo MetaTrader5 simulado: sin red y sin terminal real.

    Implementa el subconjunto de la API que usan MT5Connector/MT5Executor.
    `order_send` NO opera nada real: guarda la petición en `sent` y devuelve
    retcode 10009 (TRADE_RETCODE_DONE) salvo que `fail_orders=True`.
    """

    def __init__(
        self,
        *,
        connected: bool = True,
        fail_init: bool = False,
        fail_orders: bool = False,
        symbols: list[str] | None = None,
        positions: list[dict[str, Any]] | None = None,
        orders: list[dict[str, Any]] | None = None,
        account: dict[str, Any] | None = None,
        symbol_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._ok = connected
        self.fail_init = fail_init
        self.fail_orders = fail_orders
        self.symbol_names = list(symbols or DEFAULT_SYMBOLS)
        self.symbol_overrides = symbol_overrides or {}
        self._positions = list(positions) if positions else []
        self._orders = list(orders) if orders else []
        self._account = account or {
            "login": 1514603387, "trade_mode": 0, "leverage": 100,
            "company": "Fake Broker", "currency": "USD",
            "server": "Fake-Server", "balance": 10000.0, "equity": 10000.5,
            "margin": 0.0, "free_margin": 10000.5, "margin_level": 0.0,
            "profit": 0.5,
        }
        self.sent: list[dict[str, Any]] = []  # peticiones order_send

        # --- constantes del módulo (valores coherentes con MT5 real) ------
        self.TIMEFRAME_M1, self.TIMEFRAME_M5 = 1, 5
        self.TIMEFRAME_M15, self.TIMEFRAME_M30 = 15, 30
        self.TIMEFRAME_H1, self.TIMEFRAME_H4 = 60, 240
        self.TIMEFRAME_D1, self.TIMEFRAME_W1 = 1440, 10080
        self.TIMEFRAME_MN1 = 43200
        self.ORDER_TYPE_BUY, self.ORDER_TYPE_SELL = 0, 1
        self.ORDER_TYPE_BUY_LIMIT, self.ORDER_TYPE_SELL_LIMIT = 2, 3
        self.ORDER_TYPE_BUY_STOP, self.ORDER_TYPE_SELL_STOP = 4, 5
        self.ORDER_TYPE_BUY_STOP_LIMIT, self.ORDER_TYPE_SELL_STOP_LIMIT = 6, 7
        self.TRADE_ACTION_DEAL, self.TRADE_ACTION_PENDING = 1, 5
        self.TRADE_ACTION_SLTP, self.TRADE_ACTION_MODIFY = 6, 2
        self.TRADE_ACTION_REMOVE = 5
        self.ORDER_TIME_GTC = 0
        self.ORDER_FILLING_FOK, self.ORDER_FILLING_IOC = 0, 1
        self.ORDER_FILLING_RETURN = 2
        self.TRADE_RETCODE_DONE = 10009
        self.TRADE_RETCODE_REQUOTE = 10004
        self.TRADE_RETCODE_REJECT = 10006
        self.TRADE_RETCODE_INVALID_VOLUME = 10014
        self.TRADE_RETCODE_NO_MONEY = 10019

    # ------------------------------------------------------------------
    # Estado / conexión
    # ------------------------------------------------------------------
    def initialize(self, **kwargs) -> bool:  # noqa: N802 (API MT5)
        if self.fail_init:
            self._ok = False
            return False
        return self._ok

    def shutdown(self) -> None:
        self._ok = False

    def last_error(self) -> tuple[int, str]:
        if not self._ok:
            return (-1, "Not connected")
        if self.fail_orders:
            return (10014, "Invalid volume")
        return (0, "Success")

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def account_info(self):
        return dict(self._account)

    def symbols_get(self):
        return [types.SimpleNamespace(name=s) for s in self.symbol_names]

    def symbol_info(self, name: str):
        if name not in self.symbol_names:
            return None
        digits = 5 if "JPY" not in name and name != "XAUUSD" else 3 \
            if "JPY" in name else 2
        point = 0.01 if name == "XAUUSD" else 0.00001 if digits == 5 else \
            0.001
        base = 4381.0 if name == "XAUUSD" else 1.00000
        info = {
            "name": name, "digits": digits, "point": point,
            "bid": base, "ask": base + point, "spread": 10,
            "trade_tick_value": 1.0, "trade_tick_size": point,
            "trade_contract_size": 100.0,
            "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
            "trade_mode": 0, "trade_stops_level": 0,
            "description": f"{name} (fake)", "currency_base": "USD",
            "currency_profit": "USD", "session_open": 0, "session_close": 0,
        }
        info.update(self.symbol_overrides.get(name, {}))
        return info

    def positions_get(self, symbol=None):
        if symbol:
            return [p for p in self._positions
                    if p.get("symbol") == symbol]
        return list(self._positions)

    def orders_get(self, symbol=None):
        if symbol:
            return [o for o in self._orders if o.get("symbol") == symbol]
        return list(self._orders)

    def copy_rates_from_pos(self, symbol, timeframe, from_pos, count):
        if symbol not in self.symbol_names:
            return None
        dtype = _RATES_DTYPE
        rows = []
        base_ts = 1789773900
        px = 4380.0 if symbol == "XAUUSD" else 1.0000
        for i in range(int(count)):
            close = px + (i % 5) * 0.01 * (1 if symbol == "XAUUSD" else 0.0001)
            rows.append((base_ts - i * 300, px, max(px, close), min(px, close),
                         close, 100 + i, 5, 0))
            px = close
        return np.array(rows, dtype=dtype)

    def copy_ticks_from_pos(self, symbol, from_pos, count):
        if symbol not in self.symbol_names:
            return None
        dtype = _TICKS_DTYPE
        base = 4381.0 if symbol == "XAUUSD" else 1.0000
        rows = [(1789773900000 + i, base, base + 0.01, base, 1,
                 1789773900000 + i, 2) for i in range(int(count))]
        return np.array(rows, dtype=dtype)

    def history_deals_get(self, date_from, date_to, **kwargs):
        return []

    def history_orders_get(self, date_from, date_to, **kwargs):
        return []

    # ------------------------------------------------------------------
    # Ejecución (NO REAL: solo registra)
    # ------------------------------------------------------------------
    def order_send(self, request: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(dict(request))
        if self.fail_orders:
            return {"retcode": self.TRADE_RETCODE_INVALID_VOLUME,
                    "comment": "invalid volume", "order": 0, "deal": 0,
                    "price": 0.0, "volume": 0.0, "request": dict(request)}
        return {"retcode": self.TRADE_RETCODE_DONE, "comment": "done",
                "order": 700123, "deal": 700456,
                "price": request.get("price", 0.0),
                "volume": request.get("volume", 0.0),
                "request": dict(request)}


def sample_position(**overrides) -> dict[str, Any]:
    pos = {"ticket": 10001, "time": 1789773900, "type": 0, "magic": 0,
           "identifier": 10001, "symbol": "XAUUSD", "volume": 0.1,
           "price_open": 4380.0, "sl": 0.0, "tp": 0.0, "profit": 12.3,
           "comment": "JAYU", "volume_current": 0.1}
    pos.update(overrides)
    return pos


def sample_pending(**overrides) -> dict[str, Any]:
    order = {"ticket": 20001, "time_setup": 1789773900, "time_done": 0,
             "type": 2, "symbol": "XAUUSD", "volume": 0.1,
             "price_open": 4400.0, "sl": 0.0, "tp": 0.0, "magic": 0,
             "comment": "JAYU", "state": 2}
    order.update(overrides)
    return order


class FakeProvider:
    kind = "fake"
    name = "ollama"

    def __init__(self, fail: bool = False, answer: str = FAKE_ANSWER) -> None:
        self.fail = fail
        self.answer = answer
        self.calls: list[dict] = []

    def ping(self) -> bool:
        return not self.fail

    def list_models(self) -> list[str]:
        return ["qwen2.5:0.5b", "qwen2.5:7b-instruct-q4_K_M"]

    def installed_models(self) -> list[str]:
        return self.list_models()

    def chat(self, messages, model, temperature=0.7, max_tokens=None):
        self.calls.append({"model": model, "messages": messages})
        if self.fail:
            raise LLMError("falta de red (fake)", hint="simulado")
        return {
            "content": self.answer,
            "model": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "raw": {},
        }

    def embed(self, texts, model):
        return [[0.1] * 4 for _ in texts]

    def close(self) -> None:
        pass


# ----------------------------------------------------------------------
# Fakes de voz (Fase 2): NEVER tocan micrófono, red ni altavoces.
# ----------------------------------------------------------------------

class FakeTTS:
    """TextToSpeech falso: no sintetiza ni reproduce nada real."""

    def __init__(self, *, installed: bool = True, **cfg) -> None:
        self.installed = installed
        self.engine = cfg.get("engine", "edge")
        self.voice = cfg.get("voice", "es-MX-DaliaNeural")
        self.rate = cfg.get("rate", "+8%")
        self.pitch = cfg.get("pitch", "-2Hz")
        self.volume = cfg.get("volume", "+0%")
        self.spoken: list[str] = []

    def available(self) -> dict:
        if not self.installed:
            return {"installed": False, "engine": self.engine,
                    "voice": self.voice, "reason": "motor falso sin instalar"}
        return {"installed": True, "engine": self.engine,
                "voice": self.voice, "voices_available":
                ["es-ES-ElviraNeural", "es-MX-DaliaNeural"]}

    def speak(self, text: str, **kw) -> dict:
        if not self.installed:
            return {"ok": False, "error": "motor falso sin instalar"}
        self.spoken.append(text)
        return {"ok": True, "engine": self.engine, "voice": self.voice,
                "path": "fake/voice.mp3", "player": {"played": False,
                                                     "reason": "fake"}}


class FakeSTT:
    """SpeechToText falso: devuelve un texto fijo (sin red ni audio)."""

    def __init__(self, *, installed: bool = True, text: str = "hola") -> None:
        self.installed = installed
        self.text = text
        self.calls: list[str] = []

    def available(self) -> dict:
        if not self.installed:
            return {"installed": False, "engine": "faster-whisper",
                    "model": "small",
                    "reason": "motor falso sin instalar"}
        return {"installed": True, "engine": "faster-whisper",
                "model": "small"}

    def transcribe(self, audio_path) -> dict:
        self.calls.append(str(audio_path))
        if not self.installed:
            raise RuntimeError("motor falso sin instalar")
        return {"ok": True, "text": self.text, "language": "es",
                "language_probability": 0.99, "model": "small"}