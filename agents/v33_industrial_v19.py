"""V33.19 livestock-compounding industrial allocator.

Independent V33 architecture.  This revision uses the V33.14 district executor
but changes the capital allocator around the strongest measured economic signal:
industrial livestock.  Land is commissioned sequentially, labour is treated at
its measured one-coin cost, Q3 is built as a 12-18 cow production district, Q4
is unlocked only once Q3 is operating, and terminal inventory is liquidated.
V19.2 remains benchmark control only and is not imported.
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
        # Keep both crop engines alive; Q2 receives about half the field crew.
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Industrial Q3 crew.  Keep at least eight field workers outside livestock.
        crew = min(8, max(4, total - 9))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4:
        # Q4 gets a dedicated crop crew without starving Q1/Q2.
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 5:
                roles[i] = "q4"
                moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 27:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        # Scale hard once Q3 exists, but only to capacity that can still repay.
        target = 12 if day <= 14 else 18 if day <= 20 else max(12, active)
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 5))
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
    q1, q2, q3, q4 = (qs[i] for i in (1,2,3,4))
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}

    # Convert output to cash continuously.  From day 26, liquidate all shed stock;
    # no terminal inventory is deliberately retained.
    liquidate = day >= 26
    keep_wheat = 0 if liquidate else max(8, animals * 4)
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = keep_wheat if item == "WHEAT" else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Single shared operating reserve.  Feed solvency rises with herd size; labour
    # itself is cheap in measured mechanics and should not block commissioning.
    reserve = 450 + 70 * animals + (250 if day < 22 else 650)
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    # Sequential land ladder.  Avoid the V35 failure mode: no next land until the
    # previous district is actually operating, but do not wait for near-saturation.
    next_cost = {1:1000, 2:2000, 3:3000}.get(lands, 10**9)
    setup = {1:300, 2:900, 3:900}.get(lands, 0)
    land_ok = False
    if lands == 1:
        land_ok = day <= 6 and productive >= 6 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day <= 10 and q2_prod >= 5 and productive >= 18 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (day <= 15 and q3_prod >= 8 and q3_animals >= 6 and
                   productive >= 35 and money >= reserve + next_cost + setup)
    # Conservative payoff estimate; only positive-horizon expansion is accepted.
    expected = max(0, horizon - 4) * (700 if lands < 2 else 1000 if lands == 2 else 1300)
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi, 2)])
    if lands < 4 and land_ok and roi > 0.5 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable = max(0.0, spendable - next_cost)

    # Cheap labour is front-loaded so unlocked land is commissioned immediately.
    desired = 8 if lands == 1 else 12 if lands == 2 else 18 if lands == 3 else 22
    if day <= 18 and len(hands) < desired and len(orders) < 10:
        add = min(3, desired - len(hands), 10 - len(orders))
        for _ in range(add):
            orders.append(["HIRE"])
            meta["hires"] += 1
        spendable = max(0.0, spendable - add)
    meta["ranked"].append(["labour", float(max(0, horizon * 120 - 1))])

    # Count carried wheat as feed runway, not only shed stock.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target = animals * 5
    if animals and total_wheat < feed_target and day < 27 and len(orders) < 10:
        need = min(40, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 200) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    # Herd is the compounding engine.  Buy only against built pasture and feed-safe
    # working capital, in small batches so land/seed commissioning continues.
    if lands >= 3 and day <= 21 and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        total = animals + in_shed
        target = 12 if day <= 14 else 18
        capacity = max(0, min(pasture - total, target - total))
        cow_roi = (max(0, horizon - 2) * 150 - 400) / 400.0
        meta["ranked"].append(["cow", round(cow_roi, 2)])
        affordable = max(0, int(max(0.0, spendable - 450) // 400))
        buy = min(3, capacity, affordable)
        if buy > 0 and cow_roi > 1.0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * 400

    # Commission owned idle tiles. Q3 reserves most capacity for pasture/feed;
    # Q1/Q2/Q4 are cash crop districts. Stop long-horizon seed capex after day 22.
    if day <= 22:
        need_by: Dict[str, int] = {}
        service_cap = max(20, (len(hands) + 1) * 5)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                pasture_target = 12 if day <= 14 else 18
                idle = min(idle, max(0, int(z.get("unlocked",0) or 0) - 4 - pasture_target))
            take = min(idle, remaining, 24)
            remaining -= take
            # Mature-before-liquidation policy.
            crop = "WHEAT" if q == 3 or day >= 17 else "MELON"
            need_by[crop] = need_by.get(crop, 0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            need = max(0, min(36, raw + 4) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 200) // cost))
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
