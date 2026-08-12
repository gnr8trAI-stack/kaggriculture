"""V33.41 isolated labour-preserving realization brake.

Single mechanism over V33.40: restore recurring HIRE orders after day 18 while
keeping the realization brake on new land, animals and seed capex. Existing
productive capacity remains staffed and serviced; only expansion capital is
frozen. This tests whether V33.40 failed specifically because HIRE is recurring
operating labour rather than one-time capex.
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
    blocked = {"BUY_LAND", "BUY_ANIMAL", "BUY_SEED"}
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = str(order[0]).upper()
        if op in blocked:
            continue
        # HIRE, SELL and survival wheat remain operationally necessary.
        kept.append(order)

    if isinstance(meta, dict):
        meta = dict(meta)
        meta["realization_brake_day18"] = True
        meta["land"] = 0
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

# benchmark trigger: V33.41 labour-preserving realization brake
