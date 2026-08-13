"""V33.74: selectively restore Q4 over the strongest V33.66 parent.

V33.66 remains the operating parent. This wrapper reuses V33.28's raw capital
allocator, preserves the proven V33.66 Q3 gate, and permits Q4 only after three
land districts are dense, Q3 is active, cash is ample, and remaining-horizon
payback is positive. V19.2 is benchmark control only.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_v65 = _p._p
_raw_alloc = _v65._parent_alloc


def _capital_allocator(obs, farm, stats):
    orders, meta = _raw_alloc(obs, farm, stats)
    meta = dict(meta)
    lands = max(1, int(stats.get("lands", 1) or 1))
    productive = int(stats.get("productive", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    districts = stats.get("districts") or {}

    if lands == 2:
        q1 = districts.get(1, {})
        q2 = districts.get(2, {})
        q12 = int(q1.get("productive", 0) or 0) + int(q2.get("productive", 0) or 0)
        ready = productive >= 30 and q12 >= 30 and money >= 9000
        if not ready:
            orders = [o for o in orders if not (isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND")]
            meta["v74_q3_block"] = 1
            return orders[:10], meta

    if lands == 3:
        day = int(obs.get("day", 0) or 0)
        q3 = districts.get(3, {})
        q3_prod = int(q3.get("productive", 0) or 0)
        q3_animals = int(q3.get("animals", 0) or 0)
        horizon = max(0, 30 - day)
        expected = max(0, horizon - 3) * 1800
        roi = (expected - 3000 - 1400) / 4400.0
        ready = (day <= 18 and productive >= 54 and q3_prod >= 13 and
                 q3_animals >= 5 and money >= 11000 and roi > 1.0)
        if not ready:
            orders = [o for o in orders if not (isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND")]
            meta["v74_q4_block"] = 1
        else:
            meta["v74_q4_block"] = 0
            meta["v74_q4_roi"] = round(roi, 3)
    return orders[:10], meta


_v65._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
