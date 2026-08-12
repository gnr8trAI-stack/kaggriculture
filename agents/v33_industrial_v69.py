"""V33.69 crop-seed commissioning priority.

Single economic mechanism over V33.66: when Q1/Q2 still contain substantial
idle unlocked crop capacity, guarantee a small seed commissioning buffer inside
the ten-order market packet.  V33.66 already has enough land and labour but
peaks near 59 productive tiles while carrying a large idle-capacity signal.
This tests market-order crowding of planting inputs without adding land, labour,
animals, species, or changing worker/service behavior.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_parent_alloc = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_alloc(obs, farm, stats)
    orders = [list(o) if isinstance(o, list) else o for o in orders]
    meta = dict(meta)

    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    money = float(farm.get("money", 0) or 0)
    districts = stats.get("districts") or {}
    q1 = districts.get(1, {})
    q2 = districts.get(2, {})
    idle_q1 = int(q1.get("idle", 0) or 0)
    idle_q2 = int(q2.get("idle", 0) or 0) if lands >= 2 else 0
    idle_crop = idle_q1 + idle_q2

    private = _b._m(obs.get("private"))
    seeds = _b._m(private.get("seeds"))
    injected = 0
    crop = None
    qty = 0

    # Only intervene during the compounding window and only on a well-funded
    # estate.  Six seeds are enough to keep a worker wave busy without creating
    # a V33.39-style reinvestment trough.
    if 2 <= lands and day <= 22 and idle_crop >= 10 and money >= 8000:
        candidates = []
        for q, idle in ((1, idle_q1), (2, idle_q2)):
            if idle <= 0:
                continue
            c = _b._crop_for(day, q, obs)
            have = int(seeds.get(c, 0) or 0)
            target = min(10, max(6, (idle + 1) // 2))
            shortage = max(0, target - have)
            if shortage > 0:
                candidates.append((shortage, idle, c))
        if candidates:
            candidates.sort(reverse=True)
            shortage, _idle, crop = candidates[0]
            cost = int(_b.SEED_COST.get(crop, 10) or 10)
            affordable = max(0, int((money - 6500) // max(1, cost)))
            qty = min(shortage, affordable, 10)
            if qty > 0:
                # Remove an existing same-crop seed order so this is a priority
                # change, not duplicate purchasing. Survival wheat stays first.
                orders = [o for o in orders if not (
                    isinstance(o, list) and len(o) >= 2
                    and str(o[0]).upper() == "BUY_SEED"
                    and str(o[1]).upper() == crop
                )]
                insert_at = 0
                while insert_at < len(orders):
                    o = orders[insert_at]
                    op = str(o[0]).upper() if isinstance(o, list) and o else ""
                    if op == "SELL" or (op == "BUY_PRODUCT" and len(o) >= 2 and str(o[1]).upper() == "WHEAT"):
                        insert_at += 1
                    else:
                        break
                orders.insert(insert_at, ["BUY_SEED", crop, qty])
                orders = orders[:10]
                injected = qty

    meta["v69_seed_priority_qty"] = injected
    meta["v69_seed_priority_crop"] = crop or ""
    meta["v69_idle_crop"] = idle_crop
    return orders[:10], meta


# Patch the allocator consumed by the V33.66 execution chain.  All worker roles,
# livestock servicing, routing, crop scoring and land gates remain unchanged.
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
