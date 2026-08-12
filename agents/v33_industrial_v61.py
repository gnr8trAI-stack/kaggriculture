"""V33.61 surplus-gated elastic labour.

V33.60 demonstrated that labour demand was real but funding it from gross idle
surface destroyed the cash engine: 24/24 valid yet median reward collapsed from
V33.59's ~45.9k to ~5.2k, with median day-2 cash only 5. V61 therefore changes
one mechanism only: hiring policy.

Everything else is V33.59 unchanged. Additional workers are bought only from
realized operating surplus after a hard cash/feed reserve, one at a time, and
only while owned idle surface is large enough to justify another operator.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v59 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _quoted_sales(obs, orders):
    prices = _b._prices(obs)
    total = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = str(o[1]).upper()
            total += int(o[2]) * float(prices.get(item, _b.VALUE.get(item, 1)) or _b.VALUE.get(item, 1))
    return total


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    idle = int(stats.get("idle", 0) or 0)
    animals = int(stats.get("animals", 0) or 0)
    hands = len(list(farm.get("hands") or []))
    money = float(farm.get("money", 0) or 0)

    clean = [list(o) for o in orders if isinstance(o, list) and o]
    realizable = money + 0.90 * _quoted_sales(obs, clean)

    # Operating floor preserves seed/feed/land commissioning cash. The floor
    # rises with animals because every extra worker must not compete with feed.
    reserve = 900 + 70 * animals
    target = {1: 6, 2: 8, 3: 11, 4: 14}.get(lands, 14)

    # One mechanism only: modest elastic labour funded from true surplus.
    # Do not hire before the base crop engine has matured or during liquidation.
    can_hire = (
        6 <= day <= 23
        and idle >= 18
        and hands < target
        and realizable >= reserve + 1200
        and not any(o and o[0] == "BUY_LAND" for o in clean)
        and len(clean) < 10
    )
    if can_hire:
        clean.append(["HIRE"])

    meta["elastic_labour_v61"] = {
        "lands": lands,
        "hands": hands,
        "target": target,
        "idle": idle,
        "animals": animals,
        "realizable": round(realizable, 1),
        "reserve": reserve,
        "hired": 1 if can_hire else 0,
    }
    return clean[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
