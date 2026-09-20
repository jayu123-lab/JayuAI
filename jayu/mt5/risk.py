"""PositionSizer — cálculo de lote por riesgo (ANÁLISIS, no ejecuta).

Reglas: riesgo % del equity / balance sobre la distancia al stop-loss,
respetando mínimos/máximos/pasos del broker y límites de config/trading.yaml.
"""

from __future__ import annotations

import math
from typing import Any

from .connector import MT5Connector


class PositionSizer:
    def __init__(self, connector: MT5Connector,
                 trading_conf: dict[str, Any]) -> None:
        self.connector = connector
        self.trading_conf = trading_conf or {}

    @property
    def default_risk_pct(self) -> float:
        risk = self.trading_conf.get("risk", {})
        return float(risk.get("max_position_pct_equity", 2.0))

    def lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        *,
        risk_pct: float | None = None,
    ) -> dict[str, Any]:
        """Volumen sugerido redondeado al paso del broker.

        `risk_pct` nulo -> usa `trading.yaml: risk.max_position_pct_equity`.
        Devuelve resultado estructurado (incluye refinamiento y límites).
        """
        risk_pct = risk_pct if risk_pct is not None else self.default_risk_pct
        info = self.connector.symbol_info(symbol)
        account = self.connector.account_info()

        equity = float(account.get("equity") or account.get("balance") or 0.0)
        risk_amount = equity * risk_pct / 100.0
        distance = abs(entry_price - stop_loss)
        if distance <= 0:
            return _result(symbol, 0.0, risk_amount, equity, distance,
                           error="El SL no puede coincidir con la entrada.")

        tick_value = _num(info.get("trade_tick_value"))
        tick_size = _num(info.get("trade_tick_size"))
        if tick_size and tick_value:
            loss_per_lot = (distance / tick_size) * tick_value
            method = "tick_value/tick_size"
        else:
            # fallback con point y contract size (aproximación)
            point = _num(info.get("point"))
            contract = _num(info.get("trade_contract_size")) or 1.0
            loss_per_lot = (distance / point) * contract
            method = "point*contract_size (aproximado)"

        if loss_per_lot <= 0:
            return _result(symbol, 0.0, risk_amount, equity, distance,
                           error="Imposible calcular pérdida por lote.")

        raw_lot = risk_amount / loss_per_lot

        vol_min = _num(info.get("volume_min"), 0.01)
        vol_max = _num(info.get("volume_max"), 100.0)
        vol_step = _num(info.get("volume_step"), 0.01)

        # redondear hacia abajo al paso del broker
        lot = math.floor(raw_lot / vol_step) * vol_step if vol_step else raw_lot
        lot = max(vol_min, min(lot, vol_max))
        lot = round(lot, 6)

        # comprobar límites de config (máximo nº de posiciones abiertas)
        open_now = len(self.connector.positions(symbol=symbol))
        max_open = int(self.trading_conf.get("risk", {}).get(
            "max_open_positions", 99))
        warnings: list[str] = []
        if open_now >= max_open:
            warnings.append(f"Ya hay {open_now} posiciones en {symbol} "
                            f"(límite {max_open}).")
        constraints = {"risk_pct": risk_pct,
                       "lot_loss_value": round(loss_per_lot, 4),
                       "method": method,
                       "volume_min": vol_min, "volume_max": vol_max,
                       "volume_step": vol_step,
                       "raw_lot": round(raw_lot, 6),
                       "open_positions_now": open_now,
                       "warnings": warnings}
        return _result(symbol, lot, risk_amount, equity, distance,
                       **constraints)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _result(symbol: str, lot: float, risk_amount: float, equity: float,
            distance: float, **extra: Any) -> dict[str, Any]:
    return {"ok": lot > 0 if "error" not in extra else False,
            "symbol": symbol, "suggested_volume": lot,
            "risk_amount_usd": round(risk_amount, 2),
            "equity_usd": round(equity, 2),
            "sl_distance": round(distance, 6), **extra}