"""V33 Industrial: independent four-quadrant capital allocator.

This agent is a clean architecture break from the V19/V32 lineage.  It owns
land, labour, crop, livestock/feed and operating-reserve decisions directly and
does not import any earlier agent.  V19.2 is retained only as an external
benchmark control.

District plan
-------------
Q1/NW: bootstrap/high-turn crop cash engine.
Q2/NE: second crop engine, unlocked as soon as remaining-horizon ROI is positive.
Q3/SW: livestock + feed district.  Pastures/cows are primary; spare capacity is
       planted to wheat to reduce feed purchases.
Q4/SE: late-scale crop district, unlocked whenever remaining-horizon ROI remains
       positive and serviced by dedicated labour.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
SELLABLE = ("MELON", "STRAWBERRY", "TOMATO", "CARROT", "MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT")
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 40, "STRAWBERRY": 60, "MELON": 80}
VALUE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
         "MILK": 160, "WOOL": 200, "EGG": 50, "FERTILIZER": 100}
CYCLE = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
LAND_COST = 1000
HIRE_COST = 500
COW_COST = 400
GAME_DAYS = 30

_LAST_STEP = -1
_PREV_MONEY: Optional[float] = None
_CUM_REVENUE = 0.0
_CUM_CAPEX = {"land": 0.0, "labour": 0.0, "crop": 0.0, "livestock": 0.0, "feed": 0.0}
_UNLOCK_STEP: Dict[int, int] = {}
_ACTION_COUNTS: Dict[str, int] = {}
_RECORDS: deque = deque(maxlen=8192)


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    out: Dict[str, Any] = {}
    for k in ("player", "step", "day", "hour", "farms", "private", "market", "town"):
        try:
            out[k] = getattr(v, k)
        except Exception:
            pass
    return out


def _kind(t: Any) -> str:
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    if isinstance(t, Mapping):
        return str(t.get("kind", t.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _pos(v: Any) -> Position:
    if isinstance(v, Mapping):
        v = v.get("position", v.get("pos", [0, 0]))
    try:
        return int(v[0]), int(v[1])
    except Exception:
        return (0, 0)


def _inside(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    x, y = p
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _walkable(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    return _inside(tiles, p) and _kind(tiles[p[1]][p[0]]) != "LOCKED"


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
    if start == goal:
        return 0, "PASS"
    q = deque([(start, 0, None)])
    seen = {start}
    while q:
        (x, y), d, first = q.popleft()
        for a, dx, dy in MOVES:
            nxt = (x + dx, y + dy)
            if nxt in seen or not _walkable(tiles, nxt):
                continue
            seen.add(nxt)
            first_action = first or a
            if nxt == goal:
                return d + 1, first_action
            q.append((nxt, d + 1, first_action))
    return None


def _nearest(tiles: Sequence[Sequence[Any]], start: Position, goals: Sequence[Position]):
    best = []
    for g in goals:
        r = _route(tiles, start, g)
        if r is not None:
            best.append((r[0], g[1], g[0], g, r[1]))
    if not best:
        return None
    best.sort()
    d, _, _, g, a = best[0]
    return d, g, a


def _shed_cells(n: int) -> Set[Position]:
    h = n // 2
    return {(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)}


def _quadrant(n: int, p: Position) -> int:
    h = n // 2
    x, y = p
    if x < h and y < h:
        return 1
    if x >= h and y < h:
        return 2
    if x < h and y >= h:
        return 3
    return 4


def _inventory(private: Mapping[str, Any], idx: int) -> Mapping[str, Any]:
    inventories = private.get("inventories", [])
    if isinstance(inventories, list) and idx < len(inventories):
        return _m(inventories[idx])
    return {}


def _inv_total(inv: Mapping[str, Any]) -> int:
    return sum(max(0, int(v or 0)) for v in inv.values())


def _stats(tiles: Any) -> Dict[str, Any]:
    d = {q: {"unlocked": 0, "productive": 0, "idle": 0, "plants": 0, "pasture": 0,
             "animals": 0, "weeds": 0, "crop_counts": {}} for q in range(1, 5)}
    if not isinstance(tiles, list) or not tiles:
        return {"districts": d, "lands": 0, "productive": 0, "idle": 0, "animals": 0}
    n = len(tiles)
    sheds = _shed_cells(n)
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, t in enumerate(row):
            k = _kind(t)
            if k == "LOCKED":
                continue
            q = _quadrant(n, (x, y))
            z = d[q]
            z["unlocked"] += 1
            if k == "EMPTY" and (x, y) not in sheds:
                z["idle"] += 1
            elif k == "WEED":
                z["weeds"] += 1
            if k in {"PLANT", "PASTURE", "COOP"}:
                z["productive"] += 1
            if k == "PLANT":
                z["plants"] += 1
                crop = str(_m(t).get("crop", "")).upper()
                z["crop_counts"][crop] = z["crop_counts"].get(crop, 0) + 1
            if k == "PASTURE":
                z["pasture"] += 1
                if _m(t).get("animal"):
                    z["animals"] += 1
    lands = sum(1 for z in d.values() if int(z["unlocked"]) > 4)
    return {"districts": d, "lands": lands,
            "productive": sum(int(z["productive"]) for z in d.values()),
            "idle": sum(int(z["idle"]) for z in d.values()),
            "animals": sum(int(z["animals"]) for z in d.values())}


def _prices(obs: Mapping[str, Any]) -> Mapping[str, Any]:
    return _m(_m(obs.get("market")).get("prices"))


def _crop_value(obs: Mapping[str, Any], crop: str) -> float:
    return float(_prices(obs).get(crop, VALUE[crop]) or VALUE[crop])


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    horizon = max(1, GAME_DAYS - day)
    if district == 3:
        return "WHEAT"
    candidates = CROPS
    scored = []
    for crop in candidates:
        cycles = max(0.0, horizon / max(1, CYCLE[crop]))
        # gross value per seed-dollar over remaining cycles; bias Q4 to high-value crop.
        score = cycles * _crop_value(obs, crop) / max(1, SEED_COST[crop])
        if district == 4 and crop in {"MELON", "STRAWBERRY"}:
            score *= 1.15
        if day >= 22 and CYCLE[crop] > 4:
            score *= 0.25
        scored.append((score, crop))
    scored.sort(reverse=True)
    return scored[0][1]


def _pastures(tiles: Any):
    out = []
    if not isinstance(tiles, list):
        return out
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, t in enumerate(row):
            if isinstance(t, Mapping) and _kind(t) == "PASTURE":
                out.append(((x, y), t))
    return out


def _to_shed(tiles: Sequence[Sequence[Any]], p: Position, final: List[Any]) -> List[Any]:
    sheds = list(_shed_cells(len(tiles)))
    if p in sheds:
        return final
    r = _nearest(tiles, p, sheds)
    return [r[2]] if r is not None else ["PASS"]


def _tile_tasks(tiles: Any, districts: Set[int], reserved: Set[Position]):
    tasks = []
    n = len(tiles)
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            p = (x, y)
            if _quadrant(n, p) not in districts or p in reserved:
                continue
            k = _kind(t)
            if k == "WEED":
                tasks.append((2, p, ["DIG"], "dig"))
            elif k == "PLANT" and isinstance(t, Mapping):
                if int(t.get("yield_units", t.get("yield", 0)) or 0) > 0:
                    tasks.append((0, p, ["HARVEST"], "harvest_crop"))
                elif not bool(t.get("watered_today", t.get("watered", False))):
                    danger = int(t.get("consecutive_unwatered", 0) or 0)
                    tasks.append((0 if danger >= 1 else 1, p, ["WATER"], "water"))
    return tasks


def _best_task(tiles: Any, p: Position, tasks, reserved: Set[Position]):
    choices = []
    for priority, target, act, label in tasks:
        if target in reserved:
            continue
        r = _route(tiles, p, target)
        if r is not None:
            choices.append((priority, r[0], target[1], target[0], target, act, label, r[1]))
    if not choices:
        return None
    choices.sort()
    _, dist, _, _, target, act, label, first = choices[0]
    reserved.add(target)
    return (act if dist == 0 else [first]), label


def _empty_targets(tiles: Any, districts: Set[int], reserved: Set[Position], q3_pasture_limit: int = 0):
    out = []
    n = len(tiles)
    sheds = _shed_cells(n)
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            p = (x, y)
            if t is None and p not in sheds and p not in reserved and _quadrant(n, p) in districts:
                out.append(p)
    return out


def _livestock_action(obs: Mapping[str, Any], farm: Mapping[str, Any], idx: int, p: Position,
                      reserved: Set[Position], target_cows: int, pasture_target: int):
    tiles = farm.get("tiles") or []
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inv = _inventory(private, idx)
    ps = _pastures(tiles)
    active = [(pp, t) for pp, t in ps if str(t.get("animal", "")).upper() == "COW"]
    empty = [pp for pp, t in ps if not t.get("animal")]

    # Carrying feed has highest survival priority.
    if int(inv.get("WHEAT", 0) or 0) > 0:
        goals = [pp for pp, t in active if not bool(t.get("fed_today", False)) and pp not in reserved]
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["FEED"] if r[0] == 0 else [r[2]]), "feed"

    # Deliver milk/fertilizer immediately enough to monetize and reinvest.
    output = sum(int(v or 0) for k, v in inv.items() if str(k).upper() not in {"WHEAT", "COW"})
    if output > 0:
        return _to_shed(tiles, p, ["DROP"]), "drop_livestock"

    unfed = [pp for pp, t in active if not bool(t.get("fed_today", False)) and pp not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        return _to_shed(tiles, p, ["PICKUP", "WHEAT", min(8, int(shed.get("WHEAT", 0) or 0))]), "pickup_feed"

    # Harvest before care; both precede optional expansion work.
    for predicate, act, label in (
        (lambda t: int(t.get("yield_units", t.get("yield", 0)) or 0) > 0, ["HARVEST"], "harvest_livestock"),
        (lambda t: not bool(t.get("cared_today", t.get("cared", False))), ["CARE"], "care"),
        (lambda t: bool(t.get("fertilizer_available", False)), ["COLLECT_FERTILIZER"], "fertilizer"),
    ):
        goals = [pp for pp, t in active if predicate(t) and pp not in reserved]
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (act if r[0] == 0 else [r[2]]), label

    if int(inv.get("COW", 0) or 0) > 0 and empty:
        r = _nearest(tiles, p, [x for x in empty if x not in reserved])
        if r is not None:
            reserved.add(r[1])
            return (["PLACE", "COW"] if r[0] == 0 else [r[2]]), "place_cow"
    if int(shed.get("COW", 0) or 0) > 0 and empty:
        return _to_shed(tiles, p, ["PICKUP", "COW", 1]), "pickup_cow"

    # Build only the Q3 pasture capacity that has positive remaining-horizon ROI.
    if len(ps) < pasture_target and len(active) < target_cows:
        goals = _empty_targets(tiles, {3}, reserved)
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["BUILD_PASTURE"] if r[0] == 0 else [r[2]]), "build_pasture"
    return None


def _unit_action(obs: Mapping[str, Any], farm: Mapping[str, Any], idx: int, p: Position,
                 stats: Mapping[str, Any], reserved: Set[Position], seed_budget: Dict[str, int], role: str):
    tiles = farm.get("tiles") or []
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    private = _m(obs.get("private"))
    inv = _inventory(private, idx)
    lands = int(stats.get("lands", 0) or 0)
    hands = list(farm.get("hands") or [])

    if role == "livestock" and lands >= 3 and day <= 25:
        q3_cells = int(stats["districts"][3]["unlocked"] or 0)
        target_cows = min(14, max(6, len(hands) // 2 + 3))
        pasture_target = min(max(6, target_cows), max(0, q3_cells - 10))
        result = _livestock_action(obs, farm, idx, p, reserved, target_cows, pasture_target)
        if result is not None:
            return result

    if role == "feed" and lands >= 3:
        districts = {3}
    elif role == "q4" and lands >= 4:
        districts = {4}
    elif role == "q2" and lands >= 2:
        districts = {2}
    else:
        districts = {1}

    task = _best_task(tiles, p, _tile_tasks(tiles, districts, reserved), reserved)
    if task is not None:
        return task

    load = _inv_total(inv)
    if load >= 6 or (load > 0 and hour >= 19):
        return _to_shed(tiles, p, ["DROP"]), "drop_crop"

    if day <= 26:
        choices = []
        for g in _empty_targets(tiles, districts, reserved):
            crop = _crop_for(day, _quadrant(len(tiles), g), obs)
            if seed_budget.get(crop, 0) <= 0:
                continue
            r = _route(tiles, p, g)
            if r is not None:
                choices.append((r[0], g[1], g[0], g, crop, r[1]))
        if choices:
            choices.sort()
            dist, _, _, target, crop, first = choices[0]
            reserved.add(target)
            if dist == 0:
                seed_budget[crop] -= 1
                return ["PLANT", crop], "plant_" + crop.lower()
            return [first], "move_to_plant"

    if load > 0:
        return _to_shed(tiles, p, ["DROP"]), "drop_crop"
    return ["PASS"], "idle"


def _capital_allocator(obs: Mapping[str, Any], farm: Mapping[str, Any], stats: Mapping[str, Any]):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, GAME_DAYS - day)
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    seeds = _m(private.get("seeds"))
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = int(stats.get("lands", 0) or 0)
    animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]
    liquidate = day >= 28
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land": 0, "hires": 0, "cows": 0, "feed": 0, "seeds": {},
                            "sell_qty": 0, "reserve": 0.0, "ranked": []}

    # Revenue first: realized cash is immediately available for compounding.
    for item in SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 3 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or sell >= 2):
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Reserve only near-term operating obligations, not an arbitrary large cash pile.
    reserve = 450 + 55 * len(hands) + 90 * animals
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    # Land ROI: low capex, many productive cells.  Unlock while >= ~1 full crop cycle remains.
    if lands < 4 and horizon >= 8:
        q_value = 18 * max(1, horizon // 4) * 40.0
        roi = (q_value - LAND_COST) / LAND_COST
        meta["ranked"].append(["land", round(roi, 2)])
        if roi > 0 and spendable >= LAND_COST + 350 and len(orders) < 10:
            orders.append(["BUY_LAND"])
            meta["land"] = 1
            spendable -= LAND_COST

    # Labour scales with owned productive surface.  Capacity is deliberately front-loaded.
    owned_work_cells = max(0, sum(int(z["unlocked"]) for z in qs.values()) - 4)
    desired_hands = min(18, max(4, (owned_work_cells + 3) // 4))
    if lands >= 2:
        desired_hands = max(desired_hands, 7)
    if lands >= 3:
        desired_hands = max(desired_hands, 11)
    if lands >= 4:
        desired_hands = max(desired_hands, 15)
    labour_roi = (horizon * 120.0 - HIRE_COST) / HIRE_COST
    meta["ranked"].append(["labour", round(labour_roi, 2)])
    if labour_roi > 0:
        for _ in range(min(3, max(0, desired_hands - len(hands)))):
            if spendable < HIRE_COST + 250 or len(orders) >= 10:
                break
            orders.append(["HIRE"])
            meta["hires"] += 1
            spendable -= HIRE_COST

    # Q3 cows.  Buy only against built pasture capacity and while several milk cycles remain.
    q3 = qs[3]
    pastures = int(q3["pasture"] or 0)
    cow_in_shed = int(shed.get("COW", 0) or 0)
    cow_total = animals + cow_in_shed
    cow_roi = (max(0, horizon - 2) * 90.0 - COW_COST) / COW_COST
    meta["ranked"].append(["cow", round(cow_roi, 2)])
    if lands >= 3 and horizon >= 5 and cow_roi > 0 and pastures > cow_total and len(orders) < 10:
        target = min(14, max(6, len(hands) // 2 + 3))
        capacity = max(0, min(pastures - cow_total, target - cow_total))
        affordable = max(0, int(max(0.0, spendable - 250) // COW_COST))
        buy = min(3, capacity, affordable)
        if buy > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            spendable -= buy * COW_COST

    # Feed buffer is a survival obligation; Q3 wheat production gradually replaces these buys.
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_need = max(0, animals * 3 - wheat)
    if feed_need > 0 and len(orders) < 10 and spendable >= 100:
        buy = min(feed_need, max(0, int((spendable - 100) // 25)))
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 25

    # Seed working capital by district; include Q3 wheat so feed is increasingly internalized.
    if not liquidate and day <= 26:
        crop_need: Dict[str, int] = {}
        active_districts = [1]
        if lands >= 2:
            active_districts.append(2)
        if lands >= 3:
            active_districts.append(3)
        if lands >= 4:
            active_districts.append(4)
        for q in active_districts:
            idle = int(qs[q]["idle"] or 0)
            if q == 3:
                # Reserve part of Q3 for pasture; plant only the feed strip.
                pasture_target = min(14, max(6, len(hands) // 2 + 3))
                idle = max(0, min(idle, max(0, int(qs[q]["unlocked"]) - 4 - pasture_target)))
            crop = _crop_for(day, q, obs)
            crop_need[crop] = crop_need.get(crop, 0) + idle
        for crop, raw_need in sorted(crop_need.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            need = max(0, min(36, raw_need + 5 - have))
            affordable = max(0, int(max(0.0, spendable - 100) // SEED_COST[crop]))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                spendable -= buy * SEED_COST[crop]

    return orders[:10], meta


def _roles(lands: int, hand_count: int) -> List[str]:
    # index 0 is farmer; returned list covers farmer + hands.
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 3 == 1 else "q1"
    if lands >= 3:
        # Roughly 40% of hired workforce is dedicated livestock, one feed worker.
        livestock_slots = max(2, hand_count * 2 // 5)
        for i in range(max(1, total - livestock_slots), total):
            roles[i] = "livestock"
        if hand_count >= 5:
            roles[max(1, total - livestock_slots - 1)] = "feed"
    if lands >= 4 and hand_count >= 8:
        q4_slots = max(2, hand_count // 4)
        assigned = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and assigned < q4_slots:
                roles[i] = "q4"
                assigned += 1
    return roles


def reset_state() -> None:
    global _LAST_STEP, _PREV_MONEY, _CUM_REVENUE, _CUM_CAPEX, _UNLOCK_STEP, _ACTION_COUNTS
    _LAST_STEP = -1
    _PREV_MONEY = None
    _CUM_REVENUE = 0.0
    _CUM_CAPEX = {"land": 0.0, "labour": 0.0, "crop": 0.0, "livestock": 0.0, "feed": 0.0}
    _UNLOCK_STEP = {}
    _ACTION_COUNTS = {}
    _RECORDS.clear()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _LAST_STEP, _PREV_MONEY, _CUM_REVENUE, _CUM_CAPEX, _UNLOCK_STEP, _ACTION_COUNTS
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = _m(farms[player])
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    out = {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}
    if not isinstance(tiles, list) or not tiles:
        return out

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    stats = _stats(tiles)
    lands = int(stats["lands"] or 0)
    for q, z in stats["districts"].items():
        if int(z["unlocked"] or 0) > 4 and q not in _UNLOCK_STEP:
            _UNLOCK_STEP[q] = step

    private = _m(obs.get("private"))
    raw_seeds = _m(private.get("seeds"))
    seed_budget = {c: int(raw_seeds.get(c, 0) or 0) for c in CROPS}
    reserved: Set[Position] = set()
    units = [_pos(farm.get("farmer", [0, 0]))] + [_pos(h) for h in hands]
    roles = _roles(lands, len(hands))
    labels: List[str] = []
    for idx, p in enumerate(units):
        action, label = _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, roles[idx])
        labels.append(label)
        _ACTION_COUNTS[label] = _ACTION_COUNTS.get(label, 0) + 1
        if idx == 0:
            out["farmer"] = action
        else:
            out["hands"][idx - 1] = action

    market, meta = _capital_allocator(obs, farm, stats)
    out["market"] = market
    if meta.get("land"):
        _CUM_CAPEX["land"] += LAND_COST
    _CUM_CAPEX["labour"] += HIRE_COST * int(meta.get("hires", 0) or 0)
    _CUM_CAPEX["livestock"] += COW_COST * int(meta.get("cows", 0) or 0)
    _CUM_CAPEX["feed"] += 25 * int(meta.get("feed", 0) or 0)
    _CUM_CAPEX["crop"] += sum(SEED_COST.get(c, 0) * int(q) for c, q in meta.get("seeds", {}).items())

    money = float(farm.get("money", 0) or 0)
    if _PREV_MONEY is not None and money > _PREV_MONEY:
        _CUM_REVENUE += money - _PREV_MONEY
    _PREV_MONEY = money
    total_capex = sum(_CUM_CAPEX.values())
    productive = int(stats["productive"] or 0)
    idle = int(stats["idle"] or 0)
    reinvest = total_capex / max(1.0, total_capex + _CUM_REVENUE)
    utilization = productive / max(1, productive + idle)

    _RECORDS.append({
        "step": step, "day": day, "hour": hour, "money": money,
        "estimated_net_worth": money + productive * 100 + int(stats["animals"]) * COW_COST,
        "lands": lands, "land_unlock_steps": dict(_UNLOCK_STEP),
        "productive": productive, "idle": idle, "utilization": utilization,
        "hands": len(hands), "animals": int(stats["animals"] or 0),
        "q1": dict(stats["districts"][1]), "q2": dict(stats["districts"][2]),
        "q3": dict(stats["districts"][3]), "q4": dict(stats["districts"][4]),
        "roles": list(roles), "unit_actions": labels, "action_counts": dict(_ACTION_COUNTS),
        "market_actions": [list(x) for x in market], "allocator": meta,
        "cumulative_capex": dict(_CUM_CAPEX), "cumulative_revenue_proxy": _CUM_REVENUE,
        "reinvestment_ratio": reinvest,
    })
    return out
