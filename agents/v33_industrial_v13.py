"""V33.13 solvency-first industrial compounder.

Independent four-quadrant V33 architecture.  This revision responds to the
V33.11/V33.12 benchmark failure mode: the mechanics gate was reached (Q3/Q4
operated), but excessive labour/seed capex collapsed cash and workers before the
late-game harvest window.  V33.13 keeps land as productive capital while making
solvency and realized throughput hard constraints on the next expansion.

Measured mechanics incorporated without inheriting V19/V34 code:
- four livestock service workers are sufficient for a 12-cow district;
- pasture/cow staging must precede optional care/harvest work;
- Q4 is purchased only after Q3 is productive and the herd is commissioned;
- staffing is capped by useful district throughput rather than unlocked acreage.

V19.2 remains an external benchmark control only.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set
from agents import v33_industrial_v10 as _v10

_b = _v10._b


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    # Cheap cash/seed bootstrap, one high-value monetizable cycle, then quick cash.
    if day <= 6:
        return "WHEAT"
    if day <= 16:
        return "MELON"
    return "WHEAT"


def _age(tile: Mapping[str, Any], day: int) -> int:
    raw = tile.get("planted_day", day)
    try:
        planted = int(day if raw is None else raw)
    except Exception:
        planted = day
    return max(0, day - planted)


def _tile_tasks(tiles: Any, districts: Set[int], reserved: Set[_b.Position]):
    tasks = []
    if not isinstance(tiles, list) or not tiles:
        return tasks
    day = int(getattr(_b, "_CURRENT_DAY", 0) or 0)
    n = len(tiles)
    maturity = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            p = (x, y)
            if _b._quadrant(n, p) not in districts or p in reserved:
                continue
            kind = _b._kind(tile)
            if kind == "WEED":
                tasks.append((4, p, ["DIG"], "dig"))
                continue
            if kind != "PLANT" or not isinstance(tile, Mapping):
                continue
            crop = str(tile.get("crop", "")).upper()
            watered = bool(tile.get("watered_today", tile.get("watered", False)))
            danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
            yield_units = int(tile.get("yield_units", tile.get("yield", 0)) or 0)
            age = _age(tile, day)
            if not watered and danger and day < 28:
                tasks.append((0, p, ["WATER"], "water_urgent"))
            elif yield_units > 0 and (day >= 26 or age >= maturity.get(crop, 2)):
                tasks.append((1, p, ["HARVEST"], "harvest_crop"))
            elif not watered and day < 26:
                tasks.append((2, p, ["WATER"], "water"))
    return tasks


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3 and hand_count >= 7:
        # Four dedicated service workers is a measured throughput point for 12 cows.
        crew = 4
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4 and hand_count >= 10:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"
                moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 26:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        target = 8 if day < 11 else 12
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 8))

        # Commissioning priority: place carried/shed cows and build pasture before
        # optional livestock care/harvest. Feed survival remains inside helper.
        private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
        inv = _b._inventory(private, idx)
        ps = _b._pastures(farm.get("tiles") or [])
        empty = [pp for pp, t in ps if not t.get("animal")]
        if int(inv.get("COW", 0) or 0) > 0 and empty:
            r = _b._nearest(farm.get("tiles") or [], p, [x for x in empty if x not in reserved])
            if r is not None:
                reserved.add(r[1]); return (["PLACE", "COW"] if r[0] == 0 else [r[2]]), "place_cow"
        if int(shed.get("COW", 0) or 0) > 0 and empty:
            return _b._to_shed(farm.get("tiles") or [], p, ["PICKUP", "COW", 1]), "pickup_cow"
        if len(ps) < pasture_target and active < target:
            goals = _b._empty_targets(farm.get("tiles") or [], {3}, reserved)
            r = _b._nearest(farm.get("tiles") or [], p, goals)
            if r is not None:
                reserved.add(r[1]); return (["BUILD_PASTURE"] if r[0] == 0 else [r[2]]), "build_pasture"

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

    # Cash conversion first. Keep only a two-day feed runway from shed wheat.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 6 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or item in {"MILK","WOOL","FERTILIZER"} or sell >= 2):
            orders.append(["SELL", item, sell]); meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Hard solvency floor. V33.11 reached four lands but then collapsed to <1k cash.
    reserve = 1800 + 180 * len(hands) + 120 * animals
    if day >= 18:
        reserve += 1200
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    # Q2/Q3 are core capital. Q4 requires commissioned Q3 and cash surplus.
    q3 = qs[3]; q4 = qs[4]
    q3_prod = int(q3.get("productive", 0) or 0); q3_animals = int(q3.get("animals", 0) or 0)
    next_cost = 1000
    land_ok = False
    if lands == 1:
        land_ok = day >= 3 and horizon >= 12 and productive >= 10 and money >= reserve + 1500
    elif lands == 2:
        land_ok = day >= 6 and horizon >= 12 and productive >= 24 and money >= reserve + 2200
    elif lands == 3:
        # Do not repeat V33.11's premature fourth-land purchase.
        land_ok = (day >= 11 and horizon >= 10 and q3_prod >= 12 and q3_animals >= 8
                   and productive >= 50 and money >= reserve + 5500)
    roi = (max(0, horizon // 3) * 16 * 70 - 1500) / 1500.0
    meta["ranked"].append(["land", round(roi, 2)])
    if lands < 4 and land_ok and roi > 0 and len(orders) < 10:
        orders.append(["BUY_LAND"]); meta["land"] = 1; spendable = max(0.0, spendable - next_cost)

    # Throughput-sized labour, capped well below V33.11's 16-hand cash burn.
    desired = 5 if lands == 1 else 8 if lands == 2 else 10 if lands == 3 else 12
    if lands >= 3 and animals >= 10:
        desired = max(desired, 11)
    lroi = (horizon * 100 - 500) / 500.0
    meta["ranked"].append(["labour", round(lroi, 2)])
    # Hire at most one per market step and stop structural hiring after day 20.
    if day <= 20 and lroi > 0 and len(hands) < desired and spendable >= 900 and len(orders) < 10:
        orders.append(["HIRE"]); meta["hires"] = 1; spendable -= 500

    # Count carried wheat as feed inventory.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 7
    if animals and total_wheat < feed_target and day < 27 and len(orders) < 10:
        need = min(30, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 350) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy]); meta["feed"] = buy; spendable -= buy * 10

    # Commission Q3 to 12 active cows before discretionary Q4 capex.
    if lands >= 3 and day <= 22 and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0); in_shed = int(shed.get("COW", 0) or 0)
        target = 8 if day < 11 else 12
        total = animals + in_shed
        capacity = max(0, min(pasture - total, target - total))
        croi = (max(0, horizon - 2) * 120 - 400) / 400.0
        meta["ranked"].append(["cow", round(croi, 2)])
        affordable = max(0, int(max(0.0, spendable - 500) // 400))
        buy = min(3, capacity, affordable)
        if buy > 0 and croi > 0:
            orders.append(["BUY_ANIMAL", "COW", buy]); meta["cows"] = buy; spendable -= buy * 400

    # Seed only currently serviceable idle capacity. This prevents the large seed
    # inventory / low cash failure observed in V33.11 and V33.12.
    if not liquidate and day <= 25:
        need_by: Dict[str, int] = {}
        active_q = [1] + ([2] if lands >= 2 else []) + ([3] if lands >= 3 else []) + ([4] if lands >= 4 else [])
        labour_service_cap = max(6, (len(hands) + 1) * 3)
        remaining_cap = labour_service_cap
        for q in active_q:
            if remaining_cap <= 0:
                break
            z = qs[q]; idle = int(z.get("idle", 0) or 0)
            if q == 3:
                pasture_target = 8 if day < 11 else 12
                idle = min(idle, max(0, int(z.get("unlocked", 0) or 0) - 4 - pasture_target))
            idle = min(idle, remaining_cap)
            remaining_cap -= idle
            crop = _crop_for(day, q, obs); need_by[crop] = need_by.get(crop, 0) + idle
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0); need = max(0, min(18, raw + 2) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 400) // cost))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy]); meta["seeds"][crop] = buy; spendable -= buy * cost
    return orders[:10], meta


# Patch independent V33 call sites only.
_b._CURRENT_DAY = 0
_base_agent = _b.agent
_v10._crop_for = _crop_for
_v10._roles = _roles
_v10._unit_action = _unit_action
_v10._capital_allocator = _capital_allocator
_b._crop_for = _crop_for
_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator
_b._tile_tasks = _tile_tasks


def agent(observation: Any, configuration: Any = None):
    obs = _b._obs(observation)
    _b._CURRENT_DAY = int(obs.get("day", 0) or 0)
    return _base_agent(observation, configuration)


def reset_state():
    _b._CURRENT_DAY = 0
    return _b.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _b.get_telemetry(clear=clear)
