"""V33.60 labour-saturated four-quadrant throughput engine.

V33.59 proved reliable four-land commissioning (24/24 DONE) but plateaued at
~46k median with only 11 peak hands, ~57 peak productive assets and ~60 idle
owned tiles. Engine probes show day-worker hiring is extremely cheap at the
margin (first hires cost 1,1,2,...), so V60 treats labour as throughput capacity
rather than scarce capex.

Mechanism change:
* scale day labour aggressively with owned land / idle productive surface;
* assign explicit Q3/Q4 crop crews in addition to livestock crews;
* preserve V59's proven Q3/Q4 and dairy allocator, but keep enough operators to
  commission and service all four districts concurrently;
* never let cheap labour consume the feed/operating reserve.

This remains the independent V33 architecture; V19/V32 are reference controls.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v59 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator


def _roles(lands: int, hand_count: int):
    """Persistent district crews sized for full-surface utilization."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands == 1:
        return roles
    # Start balanced Q1/Q2 crop crews.
    for i in range(1, total):
        roles[i] = "q2" if i & 1 else "q1"
    if lands >= 3:
        # Eight dedicated Q3 livestock operators; six explicit Q3 crop operators
        # when labour is available. Livestock workers fall back to crop work when
        # service queues are empty via the proven V45 executor.
        start = max(1, total - 8)
        for i in range(start, total):
            roles[i] = "livestock3"
        crop_slots = [i for i in range(1, start) if roles[i] in {"q1","q2"}]
        for i in crop_slots[-6:]:
            roles[i] = "q3"
    if lands >= 4:
        # Rebalance the tail into eight Q4 livestock operators and create six
        # Q4 crop operators. With the V60 labour target this still leaves
        # substantial Q1/Q2 crews operating the cash engine.
        livestock3 = [i for i,r in enumerate(roles) if r == "livestock3"]
        for i in livestock3[-4:]:
            roles[i] = "livestock4"
        free = [i for i in range(1,total) if roles[i] in {"q1","q2","q3"}]
        for i in free[-6:]:
            roles[i] = "q4"
    return roles


_core._roles = _roles
_b._roles = _roles


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    idle = int(stats.get("idle", 0) or 0)
    productive = int(stats.get("productive", 0) or 0)
    hands = len(list(farm.get("hands") or []))
    animals = int(stats.get("animals", 0) or 0)

    # Cheap day-labour is the missing throughput multiplier in V59. Target enough
    # operators to keep roughly 3-4 owned tiles per worker while reserving animal
    # service capacity. Targets are intentionally land-shaped, not fixed constants.
    land_floor = {1: 7, 2: 14, 3: 24, 4: 32}.get(lands, 32)
    utilization_need = min(36, max(land_floor, (productive + idle + 3) // 4))
    animal_need = min(12, (animals + 2) // 3)
    target_hands = min(36, max(land_floor, utilization_need + animal_need))

    # Late game stops staffing growth; convert output instead.
    if day >= 25:
        target_hands = hands

    # Existing HIRE orders count toward the target. Add a bounded burst; the
    # Fibonacci hire curve is still tiny relative to idle-tile opportunity cost.
    clean = [list(o) for o in orders if isinstance(o, list) and o]
    already = sum(1 for o in clean if o[0] == "HIRE")
    gap = max(0, target_hands - hands - already)
    burst = min(6, gap, max(0, 10 - len(clean)))
    if burst:
        # Keep SELL / feed / land / animal capex ahead of labour. Hires are added
        # only into unused market slots so operating orders are never displaced.
        clean.extend([["HIRE"] for _ in range(burst)])

    meta["labour_saturation_v60"] = {
        "lands": lands,
        "hands": hands,
        "target": target_hands,
        "added": burst,
        "productive": productive,
        "idle": idle,
        "animals": animals,
        "tiles_per_worker_proxy": round((productive + idle) / max(1, hands + 1), 2),
    }
    return clean[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
