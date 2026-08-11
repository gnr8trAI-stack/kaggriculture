"""V33.9 cash-disciplined industrial allocator.

Independent V33 architecture. This revision corrects V33.8's main economic
failure: it treated the local HIRE_COST constant as if it changed the engine's
actual hire economics, then over-hired before the crop base could finance the
workforce. V33.9 keeps the four-district plan but stages labour/land/cows only
when operating cashflow can carry the next layer of productive capital.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial as _b


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    if day <= 19:
        return "STRAWBERRY"
    if day <= 23:
        return "MELON"
    return "WHEAT"


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3 and hand_count >= 6:
        livestock_slots = max(2, min(5, hand_count // 3 + 1))
        for i in range(total - livestock_slots, total):
            roles[i] = "livestock"
        roles[max(1, total - livestock_slots - 1)] = "feed"
    if lands >= 4 and hand_count >= 10:
        q4_slots = 3 if hand_count < 14 else 4
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < q4_slots:
                roles[i] = "q4"
                moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 25:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        q3_cells = int(q3.get("unlocked", 0) or 0)
        target = 8 if day < 11 else 12 if day < 15 else 14
        target = max(active, target)
        pasture_target = min(target, max(0, q3_cells - 9))
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
    qs = stats["districts"]
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land": 0, "hires": 0, "cows": 0, "feed": 0,
                            "seeds": {}, "sell_qty": 0, "reserve": 0.0,
                            "ranked": [], "hire_cost_proxy": 500}
    liquidate = day >= 28

    # Realize output continuously so compounding decisions use cash, not inventory.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 5 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (item in {"MILK", "WOOL", "FERTILIZER"} or sell >= 3 or liquidate):
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Near-term solvency only: feed runway + one replant batch + execution buffer.
    reserve = 500 + 70 * animals + 20 * max(0, int(stats.get("idle", 0) or 0))
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    # Land ladder uses observed game costs. Require the existing footprint to be
    # materially productive before taking the next quadrant, but keep frontier-like
    # early timing when ROI is strongly positive.
    next_cost = {1: 1000, 2: 2000, 3: 3000}.get(lands, 10**9)
    earliest = {1: 3, 2: 6, 3: 9}.get(lands, 99)
    min_productive = {1: 14, 2: 28, 3: 42}.get(lands, 10**9)
    productive = int(stats.get("productive", 0) or 0)
    land_setup = {1: 700, 2: 1200, 3: 1700}.get(lands, 0)
    cycles = max(0, horizon // 3)
    land_value = cycles * 16 * 85
    land_roi = (land_value - next_cost - land_setup) / max(1, next_cost + land_setup)
    meta["ranked"].append(["land", round(land_roi, 2)])
    if (lands < 4 and day >= earliest and horizon >= 9 and productive >= min_productive
            and land_roi > 0 and spendable >= next_cost + land_setup and len(orders) < 10):
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable -= next_cost

    # Feed is mandatory and includes carried wheat, not just shed inventory.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 5
    if animals > 0 and total_wheat < feed_target and day < 28 and len(orders) < 10:
        need = min(30, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 150) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    # Workforce follows productive surface and livestock, never the theoretical
    # unlocked area. Stage at most two hires per market turn using the real 500
    # coin economic proxy instead of V33.8's synthetic 1-coin assumption.
    desired = 5
    if lands >= 2:
        desired = max(desired, 7 + max(0, productive - 24) // 10)
    if lands >= 3:
        desired = max(desired, 10 + max(0, animals - 6) // 3)
    if lands >= 4:
        desired = max(desired, 13 + max(0, productive - 50) // 12)
    desired = min(17, desired)
    labour_roi = (horizon * 120 - 500) / 500.0
    meta["ranked"].append(["labour", round(labour_roi, 2)])
    if day <= 25 and labour_roi > 0:
        missing = max(0, desired - len(hands))
        for _ in range(min(2, missing)):
            if spendable < 750 or len(orders) >= 10:
                break
            orders.append(["HIRE"])
            meta["hires"] += 1
            spendable -= 500

    # Q3 milk engine. Pasture is created by dedicated workers; market only buys
    # animals for already-built capacity, in small cashflow-safe batches.
    if lands >= 3 and day <= 23 and len(orders) < 10:
        q3 = qs[3]
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        target = 8 if day < 11 else 12 if day < 15 else 14
        cow_total = animals + in_shed
        capacity = max(0, min(pasture - cow_total, target - cow_total))
        cow_roi = (max(0, horizon - 2) * 110 - 400) / 400.0
        meta["ranked"].append(["cow", round(cow_roi, 2)])
        affordable = max(0, int(max(0.0, spendable - 400) // 400))
        buy = min(3, capacity, affordable)
        if buy > 0 and cow_roi > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * 400

    # Seed only observed idle productive acreage. Frontier is strawberry-heavy in
    # the compounding window, with Q3 reserved for feed wheat and late wheat for
    # short-horizon liquidation.
    if not liquidate and day <= 26:
        need_by_crop: Dict[str, int] = {}
        for q in range(1, 5):
            z = qs[q]
            if int(z.get("unlocked", 0) or 0) <= 4:
                continue
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                target_pasture = 8 if day < 11 else 12 if day < 15 else 14
                crop_capacity = max(0, int(z.get("unlocked", 0) or 0) - 4 - target_pasture)
                idle = min(idle, crop_capacity)
            crop = _crop_for(day, q, obs)
            need_by_crop[crop] = need_by_crop.get(crop, 0) + min(24, idle)
        for crop, raw_need in sorted(need_by_crop.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            target_pool = min(32, max(4, raw_need + 2))
            need = max(0, target_pool - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 100) // cost))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                spendable -= buy * cost

    return orders[:10], meta


_b._crop_for = _crop_for
_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator


def reset_state(): return _b.reset_state()
def reset_telemetry(): return _b.reset_telemetry()
def get_telemetry(clear: bool = False): return _b.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any = None): return _b.agent(observation, configuration)
