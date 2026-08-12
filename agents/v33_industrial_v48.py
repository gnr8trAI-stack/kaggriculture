"""V33.48 wage-disciplined four-quadrant industrial allocator.

V33.47 demonstrated 47 productive cells but stalled at two districts with a
12-hand payroll and no livestock.  This revision attacks that economic failure:
labour is treated as capital with a payback hurdle, so Q1/Q2 bootstrap uses a
lean crew, Q3 adds service labour only after land exists, and Q4 adds labour
only after Q3 is commissioned.  Land remains senior to discretionary crop and
animal capex when remaining-horizon payback is positive.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v47 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _quoted_sales(obs, orders):
    prices = _b._prices(obs)
    value = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            value += int(o[2]) * float(prices.get(o[1], _b.VALUE.get(o[1], 1)) or _b.VALUE.get(o[1], 1))
    return value


def _land_count(stats):
    return max(1, int(stats.get("lands", 1) or 1))


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    lands = _land_count(stats)
    hands = len(farm.get("hands") or [])

    # Payroll is a compounding liability.  V33.47's 12-hand Q2 crew consumed
    # the very cash packet required to open Q3.  Preserve throughput with a
    # lean bootstrap and only buy service capacity after the productive asset
    # it will operate actually exists.
    desired = 6 if lands <= 2 else 9 if lands == 3 else 11
    if day >= 24:
        desired = min(desired, 9)
    if day >= 28:
        desired = min(desired, 7)

    if any(isinstance(o, list) and o and o[0] == "HIRE" for o in orders):
        allowed = max(0, desired - hands)
        kept = []
        for o in orders:
            if isinstance(o, list) and o and o[0] == "HIRE":
                if allowed <= 0:
                    continue
                allowed -= 1
            kept.append(o)
        orders = kept[:10]
        meta = dict(meta)
        meta["labour_target_v48"] = desired
        meta["labour_discipline"] = "asset_backed"

    if day >= 28 or hour <= 2 or lands >= 4:
        return orders[:10], meta
    if any(isinstance(o, list) and o and o[0] == "BUY_LAND" for o in orders):
        return orders[:10], meta

    money = float(farm.get("money", 0) or 0)
    realizable = money + 0.88 * _quoted_sales(obs, orders)
    horizon = max(0, 30 - day)
    buy = False
    cost = 0

    # Q3 is the livestock/feed factory.  Once the first Q1/Q2 crop packet can
    # fund it with a small operating buffer, land outranks another seed cycle.
    if lands == 2 and 3 <= day <= 16 and horizon >= 12 and realizable >= 2200:
        buy, cost = True, 2000
    elif lands == 3:
        q3 = stats["districts"][3]
        commissioned = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        animals = int(q3.get("animals", 0) or 0)
        # Q4 only after Q3 is real productive capital, not merely unlocked land.
        if day <= 15 and horizon >= 15 and commissioned >= 6 and animals >= 2 and realizable >= 4300:
            buy, cost = True, 4000

    if not buy:
        return orders[:10], meta

    # Preserve sales that fund the purchase, cancel competing discretionary
    # capex in this packet, then buy land.  This prevents double-spending cash.
    funding = [o for o in orders if isinstance(o, list) and o and o[0] == "SELL"]
    funding.append(["BUY_LAND"])
    meta = dict(meta)
    meta["land"] = 1
    meta["land_cost"] = cost
    meta["reinvestment"] = "senior_land_v48"
    meta["land_realizable_cash"] = round(realizable, 2)
    return funding[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)


def industrial_peaks():
    return _p.industrial_peaks()
