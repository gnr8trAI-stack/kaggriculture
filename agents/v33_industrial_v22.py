"""V33.22 delayed-payback industrial expansion.

Independent V33 lineage. V33.21 proved that the crop executor can commission
~40 productive tiles safely, but its Q3 deadline expired before the first major
melon cash cycle arrived. This revision treats Q3/Q4 as remaining-horizon ROI
investments rather than early-game milestones: it preserves Q1/Q2 throughput,
escrows cash once the two-district crop base is commissioned, unlocks Q3 after
realized cash arrives, then funds pasture/cows and only opens Q4 after Q3 is
operating. V19.2 remains benchmark-only.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v20 as _v20

_b = _v20._b
_b.HIRE_COST = 500


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Five Q3 operators are enough to build/feed/care a 10-16 cow herd while
        # leaving the original crop engines staffed.
        crew = min(6, max(4, total // 3))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        fi = total - crew - 1
        if fi >= 1:
            roles[fi] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 4:
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
        target = 10 if day <= 18 else 16 if day <= 24 else max(12, active)
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 6))
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
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[],"escrow":0.0}

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

    # True operating reserve plus explicit next-land escrow once the current
    # district is commissioned. Escrow is not hoarding: it is earmarked capex.
    reserve = 700 + 75 * animals + 80 * len(hands)
    if day >= 23:
        reserve += 400
    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)
    escrow = 0.0
    if lands == 2 and productive >= 28 and q2_prod >= 8 and horizon >= 10:
        escrow = min(2600.0, max(0.0, 2600.0 - max(0.0, money - reserve)))
    elif lands == 3 and q3_prod >= 8 and q3_animals >= 6 and horizon >= 6:
        escrow = min(3400.0, max(0.0, 3400.0 - max(0.0, money - reserve)))
    meta["reserve"] = reserve
    meta["escrow"] = escrow
    spendable = max(0.0, money - reserve - escrow)

    # Sequential land with deadlines aligned to realized crop cashflow.
    next_cost = {1:1000, 2:2000, 3:3000}.get(lands, 10**9)
    setup = {1:500, 2:600, 3:700}.get(lands, 0)
    if lands == 1:
        land_ok = day <= 6 and productive >= 8 and money >= reserve + next_cost + setup
        expected = max(0, horizon - 3) * 700
    elif lands == 2:
        land_ok = day <= 20 and q2_prod >= 10 and productive >= 30 and money >= reserve + next_cost + setup
        expected = max(0, horizon - 2) * 1150
    elif lands == 3:
        land_ok = (day <= 25 and q3_prod >= 8 and q3_animals >= 6 and productive >= 42
                   and money >= reserve + next_cost + setup)
        expected = max(0, horizon - 2) * 1500
    else:
        land_ok = False
        expected = 0
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi, 2)])
    bought_land = False
    if lands < 4 and land_ok and roi > 0 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        bought_land = True
        # Land escrow is consumed by the purchase; setup remains protected by reserve.
        spendable = max(0.0, money - reserve - next_cost)

    # Labour follows commissioned surface. Do not keep hiring while saving for Q3/Q4.
    desired = 4 if lands == 1 else 7 if lands == 2 else 12 if lands == 3 else 16
    if lands >= 3 and q3_animals >= 10:
        desired = max(desired, 13)
    labour_roi = (horizon * 130.0 - _b.HIRE_COST) / _b.HIRE_COST
    meta["ranked"].append(["labour", round(labour_roi, 2)])
    capex_escrow_active = (lands == 2 and productive >= 28 and horizon >= 10) or (lands == 3 and q3_animals >= 6 and horizon >= 6)
    if (not bought_land and not capex_escrow_active and day <= 23 and len(hands) < desired
            and labour_roi > 0 and spendable >= _b.HIRE_COST + 350 and len(orders) < 10):
        orders.append(["HIRE"])
        meta["hires"] = 1
        spendable -= _b.HIRE_COST

    # Feed solvency before cows.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 6
    if animals and total_wheat < feed_target and day < 28 and len(orders) < 10:
        need = min(45, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 300) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    # Q3 herd purchases are capacity-gated and staged after land acquisition.
    if lands >= 3 and day <= 25 and not bought_land and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        total = animals + in_shed
        target = 10 if day <= 18 else 16
        capacity = max(0, min(pasture - total, target - total))
        cow_roi = (max(0, horizon - 1) * 180 - 400) / 400.0
        meta["ranked"].append(["cow", round(cow_roi, 2)])
        affordable = max(0, int(max(0.0, spendable - 500) // 400))
        buy = min(3, capacity, affordable)
        if buy > 0 and cow_roi > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * 400

    # Commission only serviceable idle surface. While land escrow is active,
    # keep existing seed buffers rather than converting all cash into inventory.
    if not liquidate and day <= 25:
        need_by: Dict[str, int] = {}
        service_cap = max(18, (len(hands) + 1) * 5)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                pasture_target = 10 if day <= 18 else 16
                idle = min(idle, max(0, int(z.get("unlocked", 0) or 0) - 4 - pasture_target))
            take = min(idle, remaining, 24)
            remaining -= take
            crop = "WHEAT" if q == 3 or day >= 20 else "MELON"
            need_by[crop] = need_by.get(crop, 0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            buffer = 6 if capex_escrow_active else 24
            need = max(0, min(buffer, raw + 3) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 300) // cost))
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
    return _v20.agent(observation, configuration)


def reset_state():
    return _v20.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool=False):
    return _v20.get_telemetry(clear=clear)
