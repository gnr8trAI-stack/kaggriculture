"""V33.14 sequential commissioning industrial allocator.

Independent V33 architecture on the V33 core (not V19/V32).  This revision is
built from the measured failure of V33.13: a solvency floor that was too hard
prevented structural investment entirely.  V33.14 uses a commissioning state
machine instead: Q2 and Q3 are core growth capital, Q4 is unlocked only after
Q3 is genuinely operating, and every expansion retains a bounded operating
runway rather than hoarding cash.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set
from agents import v33_industrial as _b


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    # Cheap bootstrap, then high-value crop while it still has time to mature,
    # and a short-cycle terminal conversion crop.
    if day <= 5:
        return "WHEAT"
    if day <= 16:
        return "MELON"
    return "WHEAT"


def _age(tile: Mapping[str, Any], day: int) -> int:
    try:
        return max(0, day - int(tile.get("planted_day", day) if tile.get("planted_day", day) is not None else day))
    except Exception:
        return 0


def _tile_tasks(tiles: Any, districts: Set[int], reserved: Set[_b.Position]):
    tasks = []
    if not isinstance(tiles, list) or not tiles:
        return tasks
    day = int(getattr(_b, "_CURRENT_DAY", 0) or 0)
    maturity = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
    n = len(tiles)
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            p = (x, y)
            if _b._quadrant(n, p) not in districts or p in reserved:
                continue
            kind = _b._kind(tile)
            if kind == "WEED":
                tasks.append((3, p, ["DIG"], "dig")); continue
            if kind != "PLANT" or not isinstance(tile, Mapping):
                continue
            crop = str(tile.get("crop", "")).upper()
            watered = bool(tile.get("watered_today", tile.get("watered", False)))
            danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
            yield_units = int(tile.get("yield_units", tile.get("yield", 0)) or 0)
            if yield_units > 0 and (day >= 25 or _age(tile, day) >= maturity.get(crop, 2)):
                tasks.append((0, p, ["HARVEST"], "harvest_crop"))
            elif not watered and danger and day < 28:
                tasks.append((0, p, ["WATER"], "water_urgent"))
            elif not watered and day < 26:
                tasks.append((1, p, ["WATER"], "water"))
    return tasks


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3 and hand_count >= 8:
        # Four livestock workers for the commissioned 8-12 cow Q3 district.
        crew = 4
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4 and hand_count >= 11:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"; moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 26:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        target = 8 if day < 14 else 12
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 8))
        r = _b._livestock_action(obs, farm, idx, p, reserved, target, pasture_target)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, 30 - day)
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); seeds = _b._m(private.get("seeds"))
    inventories = private.get("inventories", [])
    money = float(farm.get("money", 0) or 0); hands = list(farm.get("hands") or [])
    lands = max(1, int(stats.get("lands", 1) or 1)); animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]; productive = int(stats.get("productive", 0) or 0)
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate = day >= 27

    # Convert realized output to cash continuously; preserve only a short feed runway.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 4 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or item in {"MILK","WOOL","FERTILIZER"} or sell >= 2):
            orders.append(["SELL", item, sell]); meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Bounded runway, not a hard hoarding floor.  This protects feed/replanting
    # while still allowing Q2/Q3 to be financed from bootstrap cash.
    reserve = 650 + 70 * len(hands) + 85 * animals
    if day >= 20:
        reserve += 500
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q1, q2, q3, q4 = (qs[i] for i in (1,2,3,4))
    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    # Sequential commissioning. Never buy the next district from a transient
    # sale spike unless the previous district is already doing useful work.
    land_ok = False; next_cost = {1:1000,2:2000,3:3000}.get(lands,10**9)
    setup = {1:600,2:1000,3:1600}.get(lands,0)
    if lands == 1:
        land_ok = day >= 3 and horizon >= 14 and productive >= 10 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day >= 6 and horizon >= 12 and q2_prod >= 10 and productive >= 26 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (day >= 12 and horizon >= 10 and q3_prod >= 10 and q3_animals >= 8
                   and productive >= 48 and money >= reserve + next_cost + setup + 1800)
    cycles = max(0, horizon // 3)
    expected = cycles * (18 if lands < 3 else 16) * (70 if lands < 3 else 95)
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi,2)])
    if lands < 4 and land_ok and roi > 0 and len(orders) < 10:
        orders.append(["BUY_LAND"]); meta["land"] = 1; spendable = max(0.0, spendable - next_cost)

    # Labour follows commissioned throughput. One hire/step prevents capital shocks.
    desired = 5 if lands == 1 else 8 if lands == 2 else 11 if lands == 3 else 14
    if lands >= 3 and animals >= 10:
        desired = max(desired, 12)
    lroi = (horizon * 120 - 500) / 500.0
    meta["ranked"].append(["labour", round(lroi,2)])
    if day <= 21 and len(hands) < desired and lroi > 0 and spendable >= 750 and len(orders) < 10:
        orders.append(["HIRE"]); meta["hires"] = 1; spendable -= 500

    # Feed inventory includes carried wheat.
    total_wheat = int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target = animals * 5
    if animals and total_wheat < feed_target and day < 27 and len(orders) < 10:
        need = min(30, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 250) // 10)); buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"] = buy; spendable -= buy * 10

    # Q3 herd is commissioned in small batches only against already built pasture.
    if lands >= 3 and day <= 22 and len(orders) < 10:
        pasture = int(q3.get("pasture",0) or 0); in_shed = int(shed.get("COW",0) or 0)
        target = 8 if day < 14 else 12
        total = animals + in_shed
        capacity = max(0, min(pasture - total, target - total))
        croi = (max(0,horizon-2) * 120 - 400) / 400.0
        meta["ranked"].append(["cow",round(croi,2)])
        affordable = max(0, int(max(0.0, spendable - 400) // 400)); buy = min(2, capacity, affordable)
        if buy > 0 and croi > 0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"] = buy; spendable -= buy * 400

    # Seed only capacity the current workforce can actually service. Q3 reserves
    # space for pasture; Q4 receives seed only after it has been unlocked.
    if not liquidate and day <= 25:
        need_by: Dict[str,int] = {}
        service_cap = max(8, (len(hands)+1) * 4)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]; idle = int(z.get("idle",0) or 0)
            if q == 3:
                pasture_target = 8 if day < 14 else 12
                idle = min(idle, max(0, int(z.get("unlocked",0) or 0) - 4 - pasture_target))
            take = min(idle, remaining, 22)
            remaining -= take
            crop = _crop_for(day,q,obs); need_by[crop] = need_by.get(crop,0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv:-kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop,0) or 0); need = max(0, min(22, raw + 3) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 300) // cost)); buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop] = buy; spendable -= buy * cost
    return orders[:10], meta


_b._CURRENT_DAY = 0
_base_agent = _b.agent
_b._crop_for = _crop_for
_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator
_b._tile_tasks = _tile_tasks


def agent(observation: Any, configuration: Any = None):
    obs = _b._obs(observation)
    _b._CURRENT_DAY = int(obs.get("day",0) or 0)
    return _base_agent(observation, configuration)


def reset_state():
    _b._CURRENT_DAY = 0
    return _b.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _b.get_telemetry(clear=clear)
