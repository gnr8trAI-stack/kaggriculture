"""V33.20 high-throughput industrial allocator.

Independent V33 architecture.  Extends the V33 district executor, not V19/V32.
This revision responds to V33.19's stable-but-capped ~26K result by moving the
constraint from conservative capex to throughput: early Q1/Q2 crop cash, fast
Q3 pasture/cow commissioning, Q4 only after the herd is operating, cheap labour
front-loaded to keep owned tiles busy, and terminal conversion only after the
productive base has had time to compound.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v14 as _v14

_b = _v14._b
_b.HIRE_COST = 1


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Industrial Q3 gets enough operators to feed/care/harvest a 20+ cow herd.
        crew = min(10, max(5, total - 11))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        fi = total - crew - 1
        if fi >= 1:
            roles[fi] = "feed"
    if lands >= 4:
        # Preserve Q1/Q2 while giving Q4 a real commissioning crew.
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 6:
                roles[i] = "q4"
                moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 28:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        target = 12 if day <= 11 else 18 if day <= 16 else 22 if day <= 21 else max(16, active)
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 3))
        r = _b._livestock_action(obs, farm, idx, p, reserved, target, pasture_target)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


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

    # Convert output to cash every market step.  Keep only a feed runway until D27.
    liquidate = day >= 27
    keep_wheat = 0 if liquidate else max(12, animals * 6)
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = keep_wheat if item == "WHEAT" else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # One shared reserve; allow growth capital but never spend feed/replant runway.
    reserve = 500 + 80 * animals + (300 if day < 22 else 700)
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    # Sequential land: Q2/Q3 are core; Q4 requires an actually operating Q3 herd.
    next_cost = {1:1000, 2:2000, 3:3000}.get(lands, 10**9)
    setup = {1:250, 2:550, 3:800}.get(lands, 0)
    land_ok = False
    if lands == 1:
        land_ok = day <= 6 and productive >= 6 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day <= 10 and q2_prod >= 5 and productive >= 18 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (day <= 16 and q3_prod >= 10 and q3_animals >= 10 and productive >= 42
                   and money >= reserve + next_cost + setup)
    expected = max(0, horizon - 3) * (850 if lands == 1 else 1250 if lands == 2 else 1700)
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi, 2)])
    if lands < 4 and land_ok and roi > 0.5 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable = max(0.0, spendable - next_cost)

    # Labour is measured cheap.  Throughput, not payroll, is the binding constraint.
    desired = 9 if lands == 1 else 14 if lands == 2 else 22 if lands == 3 else 26
    if day <= 20 and len(hands) < desired and len(orders) < 10:
        add = min(4, desired - len(hands), 10 - len(orders))
        for _ in range(add):
            orders.append(["HIRE"])
            meta["hires"] += 1
        spendable = max(0.0, spendable - add)
    meta["ranked"].append(["labour", float(max(0, horizon * 150 - 1))])

    # Count carried wheat too; feed solvency always precedes new cows/seeds.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 7
    if animals and total_wheat < feed_target and day < 28 and len(orders) < 10:
        need = min(60, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 250) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    # Herd compounding.  Buy only against built pasture and preserve a feed buffer.
    if lands >= 3 and day <= 22 and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        total = animals + in_shed
        target = 12 if day <= 11 else 18 if day <= 16 else 22
        capacity = max(0, min(pasture - total, target - total))
        cow_roi = (max(0, horizon - 2) * 175 - 400) / 400.0
        meta["ranked"].append(["cow", round(cow_roi, 2)])
        affordable = max(0, int(max(0.0, spendable - 500) // 400))
        buy = min(4, capacity, affordable)
        if buy > 0 and cow_roi > 1.0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * 400

    # Commission idle owned tiles aggressively while maturity horizon remains.
    if day <= 23:
        need_by: Dict[str, int] = {}
        service_cap = max(28, (len(hands) + 1) * 6)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                pasture_target = 12 if day <= 11 else 18 if day <= 16 else 22
                idle = min(idle, max(0, int(z.get("unlocked", 0) or 0) - 3 - pasture_target))
            take = min(idle, remaining, 25)
            remaining -= take
            crop = "WHEAT" if q == 3 or day >= 18 else "MELON"
            need_by[crop] = need_by.get(crop, 0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            need = max(0, min(45, raw + 5) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 250) // cost))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                spendable -= buy * cost

    return orders[:10], meta


_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any=None):
    return _v14.agent(observation, configuration)


def reset_state():
    return _v14.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool=False):
    return _v14.get_telemetry(clear=clear)
