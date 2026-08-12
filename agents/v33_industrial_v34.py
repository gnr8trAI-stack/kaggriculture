"""V33.34 herd-first four-district industrial allocator.

Independent V33 lineage. V33.33 proved the physical executor can sustain ~60-75
productive tiles with zero invalids, but four-land games underperformed because
Q4 was bought before Q3's livestock engine had compounded. This revision makes
Q3 commissioning the prerequisite for Q4: build a 12-18 cow herd and matching
pasture first, then unlock Q4 only when the herd is operating and the cash
reserve can fund district commissioning. Batch-clearing remains the realization
policy. V19.2 remains reference control only.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v33 as _v33

_v28 = _v33._v28
_b = _v33._b

# Preserve the proven zero-invalid V33.33 executor/marketing policy.
_base_allocator = _v28._capital_allocator


def _industrial_cow_target(obs, day: int, active: int) -> int:
    """Frontier-shaped herd ladder, gated by remaining horizon rather than demand.

    V33.33 median herd was only six animals while frontier replays showed roughly
    14 median and up to 22. Batch clearing removes the need to cap herd strictly
    to instantaneous milk demand; working-capital/feed gates remain in allocator.
    """
    if day <= 13:
        target = 12
    elif day <= 17:
        target = 16
    elif day <= 20:
        target = 18
    elif day <= 22:
        target = max(active, 14)
    else:
        target = active
    return max(active, target)


def _herd_first_allocator(obs, farm, stats):
    orders, meta = _base_allocator(obs, farm, stats)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if lands != 3:
        return orders, meta

    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    productive = int(stats.get("productive", 0) or 0)
    q3 = stats.get("districts", {}).get(3, {})
    q3_animals = int(q3.get("animals", 0) or 0)
    q3_pasture = int(q3.get("pasture", 0) or 0)
    q3_productive = int(q3.get("productive", 0) or 0)

    # Realized V33.33 evidence: premature Q4 games averaged ~51k versus ~68k for
    # three-land games. Q4 is therefore positive-ROI only after Q3 is genuinely
    # commissioned and enough liquidity remains to staff/seed Q4 immediately.
    q4_ready = (
        day <= 16
        and q3_animals >= 10
        and q3_pasture >= 12
        and q3_productive >= 15
        and productive >= 50
        and money >= 14000
    )
    if not q4_ready:
        filtered = [o for o in orders if not (isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND")]
        if len(filtered) != len(orders):
            meta = dict(meta)
            meta["land"] = 0
            meta["land_cost"] = 0
            meta.setdefault("ranked", []).append(["q4_realized_gate", -1.0])
        return filtered, meta
    meta.setdefault("ranked", []).append(["q4_realized_gate", 1.0])
    return orders, meta


_v28._cow_target = _industrial_cow_target
_v28._capital_allocator = _herd_first_allocator


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
