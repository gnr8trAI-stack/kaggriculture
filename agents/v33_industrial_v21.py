"""V33.21 cash-realistic staged industrial allocator.

Independent V33 lineage. Fixes V33.20's accounting error where the allocator
mutated HIRE_COST to 1 even though the environment still charged the real hire
price. That made the planner believe labour was essentially free, drained cash,
and prevented even Q2 from unlocking. V33.21 uses real costs, gives land first
claim on growth capital, commissions each district before the next unlock, and
keeps a single shared operating reserve across land/labour/crop/livestock/feed.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v20 as _v20

_b = _v20._b
_b.HIRE_COST = 500


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, 30 - day)
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    seeds = _b._m(private.get("seeds"))
    inventories = private.get("inventories", [])
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = max(1, int(stats.get("lands", 1) or 1))
    animals = int(stats.get("animals", 0) or 0)
    productive = int(stats.get("productive", 0) or 0)
    qs = stats["districts"]
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}

    # Monetize output continuously. Keep only a short feed runway until terminal liquidation.
    liquidate = day >= 27
    keep_wheat = 0 if liquidate else max(10, animals * 5)
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = keep_wheat if item == "WHEAT" else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Shared runway. All discretionary mechanisms spend from this one balance.
    reserve = 900 + 80 * animals + 90 * len(hands)
    if day >= 22:
        reserve += 500
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    # Land has first claim on growth capital. Q2 is bootstrap capital, not a luxury.
    # Q3/Q4 require the previous district to be demonstrably operating.
    next_cost = {1:1000, 2:2000, 3:3000}.get(lands, 10**9)
    setup = {1:700, 2:1100, 3:1500}.get(lands, 0)
    land_ok = False
    if lands == 1:
        land_ok = day <= 4 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day <= 12 and q2_prod >= 10 and productive >= 28 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (day <= 18 and q3_prod >= 10 and q3_animals >= 8 and productive >= 46
                   and money >= reserve + next_cost + setup)
    expected = max(0, horizon - 3) * (700 if lands == 1 else 1050 if lands == 2 else 1450)
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi, 2)])
    bought_land = False
    if lands < 4 and land_ok and roi > 0 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable = max(0.0, spendable - next_cost)
        bought_land = True

    # Workforce follows commissioned surface. Never pretend labour costs 1 coin.
    desired = 4 if lands == 1 else 7 if lands == 2 else 13 if lands == 3 else 17
    if lands >= 3 and q3_animals >= 8:
        desired = max(desired, 14)
    labour_roi = (horizon * 125.0 - _b.HIRE_COST) / _b.HIRE_COST
    meta["ranked"].append(["labour", round(labour_roi, 2)])
    if (not bought_land and day <= 22 and len(hands) < desired and labour_roi > 0
            and spendable >= _b.HIRE_COST + 500 and len(orders) < 10):
        # One hire per market packet is deliberate: no hidden simultaneous capex shock.
        orders.append(["HIRE"])
        meta["hires"] = 1
        spendable -= _b.HIRE_COST

    # Feed solvency before biological expansion.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 6
    if animals and total_wheat < feed_target and day < 28 and len(orders) < 10:
        need = min(50, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 350) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    # Q3 herd. Capacity must physically exist before purchasing cows.
    if lands >= 3 and day <= 23 and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        total = animals + in_shed
        target = 8 if day <= 13 else 14 if day <= 18 else 18
        capacity = max(0, min(pasture - total, target - total))
        cow_roi = (max(0, horizon - 2) * 165 - 400) / 400.0
        meta["ranked"].append(["cow", round(cow_roi, 2)])
        affordable = max(0, int(max(0.0, spendable - 700) // 400))
        buy = min(2, capacity, affordable)
        if buy > 0 and cow_roi > 0.5:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * 400

    # Commission idle owned surface only to the throughput the current labour can service.
    if not liquidate and day <= 24:
        need_by: Dict[str, int] = {}
        service_cap = max(18, (len(hands) + 1) * 4)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                pasture_target = 8 if day <= 13 else 14 if day <= 18 else 18
                idle = min(idle, max(0, int(z.get("unlocked", 0) or 0) - 4 - pasture_target))
            take = min(idle, remaining, 22)
            remaining -= take
            crop = "WHEAT" if q == 3 or day >= 19 else "MELON"
            need_by[crop] = need_by.get(crop, 0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            need = max(0, min(32, raw + 4) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 400) // cost))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                spendable -= buy * cost

    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any=None):
    return _v20.agent(observation, configuration)


def reset_state():
    return _v20.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool=False):
    return _v20.get_telemetry(clear=clear)
