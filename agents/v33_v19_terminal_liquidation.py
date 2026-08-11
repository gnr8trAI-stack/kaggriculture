"""V33.30: pure V19.2 + terminal shed liquidation only.

Single-mechanism experiment. The production, land, crop, livestock, staffing,
feed, seed, movement and market logic is exactly V19.2. The sole addition is a
late D29 shed liquidation pass so inventory that otherwise has zero terminal
value is converted to cash before episode end.

This module is benchmarked in a fresh subprocess for every game to prevent the
V19.2/V19 shared-module monkey patches from contaminating paired controls.
"""
from __future__ import annotations

from typing import Any, List, Mapping

from agents import v19_2_early_scale8 as _base

VERSION = "33.30.0-v19-terminal-liquidation"
LIQUIDATION_DAY = 29
LIQUIDATION_HOUR = 18


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _liquidation_orders(observation: Any, base_market: Any) -> List[List[Any]]:
    obs = _base._v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)

    clean: List[List[Any]] = []
    if isinstance(base_market, list):
        for raw in base_market:
            if isinstance(raw, list) and raw:
                clean.append(list(raw))

    if day < LIQUIDATION_DAY or (day == LIQUIDATION_DAY and hour < LIQUIDATION_HOUR):
        return clean[:10]

    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))

    # On the terminal evening capex and replenishment have no payback runway.
    # Keep any existing SELL_PRODUCT orders, discard buys/hires/land/animals,
    # then drain every positive shed item. Repeated hourly calls naturally sell
    # residual stock if the market cannot clear the whole shed in one action.
    out: List[List[Any]] = []
    already = set()
    for order in clean:
        op = str(order[0]).upper()
        if op != "SELL_PRODUCT" or len(order) < 2:
            continue
        item = str(order[1]).upper()
        out.append(order)
        already.add(item)
        if len(out) >= 10:
            return out[:10]

    for item, raw_qty in shed.items():
        item_u = str(item).upper()
        if item_u in already:
            continue
        try:
            qty = int(raw_qty or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        out.append(["SELL_PRODUCT", item_u, qty])
        already.add(item_u)
        if len(out) >= 10:
            break
    return out[:10]


def reset_state() -> None:
    _base.reset_state()


def reset_telemetry() -> None:
    _base.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    result = dict(_base.agent(observation, configuration))
    result["market"] = _liquidation_orders(observation, result.get("market", []))
    return result
