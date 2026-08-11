"""V34.10 isolated terminal-liquidation experiment.

Single economic mutation on top of verified V34.6: preserve herd capacity,
livestock service crew, land/crop/feed/routing/staffing policy unchanged, but
force shed inventory liquidation from day 29 onward.

This tests whether V34.6 strands terminal value in the shed. No earlier market
or production behavior is changed.
"""
from __future__ import annotations
from typing import Any, List

from agents import v34_6_cow16_window24_isolated as _v346

_BASE = _v346.agent
_v19 = _v346._v345._v343._v342._v19
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
LIQUIDATE_DAY = 29


def reset_state() -> None:
    _v346.reset_state()


def reset_telemetry() -> None:
    _v346.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v346.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    result = dict(_BASE(observation, configuration))
    obs = _v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    if day < LIQUIDATE_DAY:
        return result

    private = obs.get("private") or {}
    shed = private.get("shed") or {}
    sales: List[List[Any]] = []
    for product in PRODUCTS:
        qty = int(shed.get(product, 0) or 0)
        if qty > 0:
            sales.append(["SELL", product, qty])
            if len(sales) >= 10:
                break

    if sales:
        # Terminal cash conversion is the only mutation. Suppress all base market
        # purchases on liquidation day so sales cannot be displaced by capex/feed.
        result["market"] = sales
    return result
