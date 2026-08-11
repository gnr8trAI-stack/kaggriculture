"""V34 single-mechanism experiment: hard terminal shed liquidation on V19.2.

Economic hypothesis: terminal reward is cash, so sellable inventory stranded in the
shed on the final half-day should be converted to cash. All V19.2 crop, land,
livestock, labour, feed and routing behavior is unchanged before day 29 hour 12.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Mapping

from agents import v19_2_early_scale8 as _v192

SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)
_RECORDS = deque(maxlen=4096)
_LAST_STEP = -1


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    return {
        k: getattr(v, k)
        for k in ("player", "step", "day", "hour", "farms", "private")
        if hasattr(v, k)
    }


def reset_state() -> None:
    global _LAST_STEP
    _LAST_STEP = -1
    _RECORDS.clear()
    _v192.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any = None):
    global _LAST_STEP
    obs = _obs(observation)
    step = int(obs.get("step", 0) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    result = dict(_v192.agent(observation, configuration))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    liquidation = day == 29 and hour >= 12

    sold_value_units = 0
    if liquidation:
        orders = []
        for item in SELLABLE:
            qty = max(0, int(shed.get(item, 0) or 0))
            if qty > 0 and len(orders) < 10:
                orders.append(["SELL", item, qty])
                sold_value_units += qty
        result["market"] = orders

    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    money = 0.0
    if isinstance(farms, list) and player < len(farms):
        money = float(_m(farms[player]).get("money", 0) or 0)
    shed_sellable = sum(max(0, int(shed.get(item, 0) or 0)) for item in SELLABLE)
    _RECORDS.append({
        "step": step, "day": day, "hour": hour, "money": money,
        "liquidation": liquidation, "shed_sellable_units": shed_sellable,
        "liquidation_units_ordered": sold_value_units,
    })
    return result
