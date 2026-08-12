"""V33.68 demand-qualified third district.

Single economic mechanism over V33.66: keep its utilization/cash Q3 gate and
all crop, staffing, livestock, feed, sale and Q4-suppression behavior unchanged,
but suppress the Q2 -> Q3 land purchase when recurring milk demand has not yet
reached shop-backed levels.

V33.66 is strongly bimodal: the same three-land policy produces ~74k median and
~89k max, but a 44k tail that falls below V19.2. Since Q3 is explicitly the dairy
+ feed district, buying it in town-center-only milk demand is negative expected
value. This candidate tests only that market-demand qualification.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

# V33.66 -> V33.65 -> V33.28.
_v28 = _p._p._p
_parent_alloc = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_alloc(obs, farm, stats)
    meta = dict(meta)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if lands == 2:
        milk_demand = int(_v28._daily_demand(obs, "MILK") or 0)
        # Town center contributes only 1/day. A milk-consuming shop adds 6/day,
        # so >=7/day is the first clearly recurring dairy-demand regime.
        if milk_demand < 7:
            filtered = []
            blocked = 0
            for order in orders:
                if isinstance(order, list) and order and str(order[0]).upper() == "BUY_LAND":
                    blocked += 1
                    continue
                filtered.append(list(order) if isinstance(order, list) else order)
            meta["v68_q3_demand_block"] = blocked
            meta["v68_milk_demand"] = milk_demand
            return filtered[:10], meta
        meta["v68_milk_demand"] = milk_demand
    meta["v68_q3_demand_block"] = 0
    return orders[:10], meta


# Patch the exact allocator consumed by V33.28's agent path while preserving
# V33.66's utilization gate and V33.65's Q4 suppression.
_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_v28._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
