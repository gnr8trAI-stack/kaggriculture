"""V33.65 three-district capital discipline.

Single economic mechanism over V33.28: do not purchase the fourth land district.
V33.64's isolated distribution showed the strongest terminal rewards clustered in
three-land games while four-land games carried most of the catastrophic tail and
large idle capacity.  Keep V33.28's crop, labour, dairy/feed, sales and seed logic
unchanged; suppress only the Q4 BUY_LAND order once three districts are open.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v28 as _p

_b = _p._b
_parent_alloc = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_alloc(obs, farm, stats)
    meta = dict(meta)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if lands >= 3:
        filtered = []
        blocked = 0
        for order in orders:
            if isinstance(order, list) and order and str(order[0]).upper() == "BUY_LAND":
                blocked += 1
                continue
            filtered.append(list(order) if isinstance(order, list) else order)
        meta["v65_q4_block"] = blocked
        return filtered[:10], meta
    meta["v65_q4_block"] = 0
    return orders[:10], meta


_p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
