"""V33.49 crop-funded livestock commissioning.

V33.48 proved that Q3 can be unlocked reliably, but its fixed six-person Q3
crew immediately spent most labour on 24 empty structures while Q1 collapsed
and the farm could not afford animals.  The result was 58.5 median productive
cells but only two animals and ~9.1k median terminal cash.

This revision changes the mechanism rather than another threshold: Q1/Q2 stay
as the cash engine while Q3 commissions only capital-backed livestock capacity.
Two livestock operators are enough before the herd exists; excess livestock
construction is suppressed when empty structures outrun owned/pending animals.
Workers released by that gate fall back to crop districts.  As biological
capital compounds, Q3/Q4 service crews scale in bounded steps.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v48 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator
_parent_livestock = _core._livestock_action


def _roles(lands: int, hand_count: int):
    """Protect the crop cash engine until livestock capital actually exists."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # V48 used six Q3 operators immediately and starved the crop engine.
        # Start with two commissioners; the service routine falls back to q2
        # whenever there is no capital-backed livestock work.
        for i in range(max(1, total - 2), total):
            roles[i] = "livestock3"
    if lands >= 4:
        # Keep Q4 active without sacrificing the funding districts. One Q4
        # crop operator and one livestock operator are sufficient initially.
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 1:
                roles[i] = "q4"
                moved += 1
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 2:
                roles[i] = "livestock4"
                moved += 1
    return roles


_core._roles = _roles
_b._roles = _roles


def _pending_animals(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> int:
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    n = sum(int(shed.get(a, 0) or 0) for a in ("GOOSE", "COW", "SHEEP"))
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        for inv in invs:
            m = _b._m(inv)
            n += sum(int(m.get(a, 0) or 0) for a in ("GOOSE", "COW", "SHEEP"))
    return n


def _livestock_action(obs, farm, idx, p, stats, reserved, district: int):
    """Run husbandry first, but never build a warehouse of empty structures."""
    result = _parent_livestock(obs, farm, idx, p, stats, reserved, district)
    if result is None:
        return None
    action, label = result
    if label not in {"build_coop", "build_pasture"}:
        return result

    q = stats["districts"][district]
    structures = int(q.get("coop", 0) or 0) + int(q.get("pasture", 0) or 0)
    active = int(q.get("animals", 0) or 0)
    pending = _pending_animals(obs, farm)
    day = int(obs.get("day", 0) or 0)

    # Maintain just enough spare slots for the next affordable animal tranche.
    # Early game permits two spares; later one is enough. This converts labour
    # back into crop cash instead of filling Q3 with 24 idle structures.
    spare = 2 if day <= 14 else 1
    if structures >= active + pending + spare:
        return None
    return result


_core._livestock_action = _livestock_action


def _quoted_sales(obs, orders):
    prices = _b._prices(obs)
    return sum(
        int(o[2]) * float(prices.get(o[1], _b.VALUE.get(o[1], 1)) or _b.VALUE.get(o[1], 1))
        for o in orders
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
    )


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if day >= 28:
        return orders[:10], meta

    # Once Q3 exists, biological capital outranks Q4 until the livestock
    # district has a meaningful earning base.  V48's Q4 condition was never
    # reached in the median case, but this guard makes the allocation explicit
    # and prevents a lucky cash spike from buying Q4 before Q3 can fund itself.
    if lands == 3:
        q3 = stats["districts"][3]
        animals = int(q3.get("animals", 0) or 0)
        structures = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        if animals < 6 or structures < 8:
            filtered = [o for o in orders if not (isinstance(o, list) and o and o[0] == "BUY_LAND")]
            if len(filtered) != len(orders):
                meta = dict(meta)
                meta["q4_deferred_v49"] = "q3_not_self_funding"
            orders = filtered

    # Do not let seed working capital disappear after Q3 unlock. Preserve at
    # least one short-cycle packet for the two crop districts whenever current
    # market orders contain only land/livestock/feed spending.
    if lands >= 3 and day <= 22:
        has_seed = any(isinstance(o, list) and o and o[0] == "BUY_SEED" for o in orders)
        if not has_seed:
            prices = _b._prices(obs)
            private = _b._m(obs.get("private"))
            seeds = _b._m(private.get("seeds"))
            q1 = stats["districts"][1]
            q2 = stats["districts"][2]
            idle = int(q1.get("idle", 0) or 0) + int(q2.get("idle", 0) or 0)
            crop = "WHEAT" if day <= 9 else "CARROT"
            have = int(seeds.get(crop, 0) or 0)
            want = max(0, min(24, idle + 4) - have)
            cost = _core.SEED_COST[crop]
            sale_cash = _quoted_sales(obs, orders)
            money = float(farm.get("money", 0) or 0)
            # Keep a 500-coin operating cushion; seed packet is intentionally
            # modest so it cannot block feed or an affordable animal purchase.
            affordable = max(0, int(max(0.0, money + 0.75 * sale_cash - 500.0) // cost))
            buy = min(want, affordable)
            if buy > 0 and len(orders) < 10:
                orders.append(["BUY_SEED", crop, buy])
                meta = dict(meta)
                meta["crop_cash_engine_v49"] = {crop: buy}

    return orders[:10], meta


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
