"""V33.40 isolated capital-realization brake.

Single mechanism over V33.39: once day 18 begins, stop discretionary expansion
capex (land, hires, new animals and seeds). Existing productive capacity continues
to harvest, service livestock, sell output and buy survival wheat. This directly
tests the V33.39 D20 cash trough without changing districts, crop portfolio,
service routing, mixed-species targets or terminal liquidation behavior.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v39 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    day = int(obs.get("day", 0) or 0)
    if day < 18:
        return orders, meta

    kept = []
    blocked = {"BUY_LAND", "HIRE", "BUY_ANIMAL", "BUY_SEED"}
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = str(order[0]).upper()
        if op in blocked:
            continue
        # Survival wheat remains allowed. SELL orders remain allowed.
        kept.append(order)

    if isinstance(meta, dict):
        meta = dict(meta)
        meta["capital_brake_day18"] = True
        meta["land"] = 0
        meta["hires"] = 0
        meta["cows"] = 0
        meta["sheep"] = 0
        meta["seeds"] = {}
    return kept[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)

# benchmark trigger: V33.40 isolated capital brake
