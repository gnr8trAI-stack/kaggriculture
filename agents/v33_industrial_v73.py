"""V33.73 utilization-gated Q4 recommissioning.

Independent industrial mechanism over V33.66: restore the fourth district only
when the three-land estate is already dense, staffed, profitable and Q3 itself is
commissioned. V33.28 showed Q4 can add physical scale but buying it too early
created a catastrophic idle-capacity tail. V33.66 established a much stronger
three-district parent (~80k median) with D20 productive density around 57/72.

This candidate therefore treats Q4 as a remaining-horizon capital allocation,
not a fixed milestone: buy only with strong three-district utilization, positive
cash coverage, serviced livestock and enough remaining days to amortize the
4,000 land cost plus commissioning reserve. Existing V33.28 role logic already
moves three crop workers into Q4 after unlock, so no new labour mechanism is
introduced here.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_alloc = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_alloc(obs, farm, stats)
    orders = [list(o) if isinstance(o, list) else o for o in orders]
    meta = dict(meta)

    lands = max(1, int(stats.get("lands", 1) or 1))
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    productive = int(stats.get("productive", 0) or 0)
    idle = int(stats.get("idle", 0) or 0)
    animals = int(stats.get("animals", 0) or 0)
    hands = len(list(farm.get("hands") or []))
    districts = stats.get("districts") or {}
    q3 = districts.get(3, {}) or {}
    q3_productive = int(q3.get("productive", 0) or 0)
    q3_idle = int(q3.get("idle", 0) or 0)
    q3_pasture = int(q3.get("pasture", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    # Q4 costs 4,000 at the three-land state. Require enough remaining horizon
    # for at least two useful crop cycles and enough liquidity to commission Q4
    # without starving feed/replant/operating reserve.
    remaining = max(0, 30 - day)
    q4_cost = 4000
    commission_reserve = 6500
    utilization = productive / max(1, productive + idle)
    estimated_daily_surplus = productive * 42.0 + animals * 125.0
    projected_incremental = max(0, remaining - 3) * min(3200.0, estimated_daily_surplus * 0.48)
    q4_roi = (projected_incremental - q4_cost) / q4_cost

    ready = (
        lands == 3
        and 15 <= day <= 18
        and productive >= 54
        and utilization >= 0.72
        and money >= q4_cost + commission_reserve
        and hands >= 11
        and animals >= 6
        and q3_productive >= 13
        and q3_idle <= 11
        and q3_pasture >= 6
        and q3_animals >= 4
        and q4_roi >= 1.25
    )

    has_land = any(isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND" for o in orders)
    if ready and not has_land and len(orders) < 10:
        # Keep survival feed orders ahead of capex; insert Q4 before discretionary
        # hires/seeds so land commissioning begins while the horizon is valuable.
        insert_at = 0
        while insert_at < len(orders):
            o = orders[insert_at]
            if isinstance(o, list) and len(o) >= 2 and str(o[0]).upper() in {"SELL", "BUY_PRODUCT"}:
                insert_at += 1
            else:
                break
        orders.insert(insert_at, ["BUY_LAND"])
        meta["v73_q4_buy"] = 1
    else:
        meta["v73_q4_buy"] = 0
    meta["v73_q4_ready"] = int(ready)
    meta["v73_q4_roi"] = round(q4_roi, 3)
    meta["v73_utilization"] = round(utilization, 3)
    return orders[:10], meta


# Patch the allocator used by the V33.28 execution path beneath V33.66.
_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
