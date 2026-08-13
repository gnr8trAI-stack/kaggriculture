"""V33.20 mixed-herd compounding industrial allocator.

Independent V33 architecture. This revision follows the strongest replay signal:
elite farms compound crops and livestock together instead of allowing livestock to
starve the crop engine. Q1 remains a feed/cash factory, Q2 is a strawberry cash
district, Q3 is a mixed cow/sheep livestock district with dedicated feed labour,
and Q4 is commissioned only after Q3 is profitable and the remaining horizon can
repay it. V19.2 remains benchmark control only and is not imported.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set, Tuple
from agents import v33_industrial_v14 as _v14

_b = _v14._b
ANIMAL_COST = {"COW": 400, "SHEEP": 500}
TARGET_COWS = 8
TARGET_SHEEP = 6


def _animal_positions(tiles: Any):
    out = []
    if not isinstance(tiles, list):
        return out
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, t in enumerate(row):
            if isinstance(t, Mapping) and _b._kind(t) == "PASTURE":
                out.append(((x, y), t, str(t.get("animal", "")).upper()))
    return out


def _species_counts(tiles: Any) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0}
    for _, _, animal in _animal_positions(tiles):
        if animal in counts:
            counts[animal] += 1
    return counts


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    if district in {2, 4}:
        return "STRAWBERRY" if day <= 17 else "WHEAT"
    if day <= 4:
        return "WHEAT"
    if day <= 15:
        return "MELON"
    return "WHEAT"


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 3 else "q1"
    if lands >= 3:
        crew = min(5, max(3, total - 7))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"
                moved += 1
    return roles


def _mixed_livestock_action(obs: Mapping[str, Any], farm: Mapping[str, Any], idx: int,
                            p: Tuple[int, int], reserved: Set[Tuple[int, int]],
                            target_cows: int, target_sheep: int, pasture_target: int):
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    inv = _b._inventory(private, idx)
    ps = _animal_positions(tiles)
    active = [(pp, t, a) for pp, t, a in ps if a in {"COW", "SHEEP"}]
    empty = [pp for pp, t, a in ps if not a]

    if int(inv.get("WHEAT", 0) or 0) > 0:
        goals = [pp for pp, t, _ in active if not bool(t.get("fed_today", False)) and pp not in reserved]
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["FEED"] if r[0] == 0 else [r[2]]), "feed"

    output = sum(int(v or 0) for k, v in inv.items()
                 if str(k).upper() not in {"WHEAT", "COW", "SHEEP"})
    if output > 0:
        return _b._to_shed(tiles, p, ["DROP"]), "drop_livestock"

    unfed = [pp for pp, t, _ in active if not bool(t.get("fed_today", False)) and pp not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", min(8, int(shed.get("WHEAT", 0) or 0))]), "pickup_feed"

    for predicate, act, label in (
        (lambda t: int(t.get("yield_units", t.get("yield", 0)) or 0) > 0, ["HARVEST"], "harvest_livestock"),
        (lambda t: not bool(t.get("cared_today", t.get("cared", False))), ["CARE"], "care"),
        (lambda t: bool(t.get("fertilizer_available", False)), ["COLLECT_FERTILIZER"], "fertilizer"),
    ):
        goals = [pp for pp, t, _ in active if predicate(t) and pp not in reserved]
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (act if r[0] == 0 else [r[2]]), label

    for animal in ("SHEEP", "COW"):
        if int(inv.get(animal, 0) or 0) > 0 and empty:
            r = _b._nearest(tiles, p, [x for x in empty if x not in reserved])
            if r is not None:
                reserved.add(r[1])
                return (["PLACE", animal] if r[0] == 0 else [r[2]]), "place_" + animal.lower()
    for animal in ("SHEEP", "COW"):
        if int(shed.get(animal, 0) or 0) > 0 and empty:
            return _b._to_shed(tiles, p, ["PICKUP", animal, 1]), "pickup_" + animal.lower()

    counts = _species_counts(tiles)
    if len(ps) < pasture_target and sum(counts.values()) < target_cows + target_sheep:
        goals = _b._empty_targets(tiles, {3}, reserved)
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["BUILD_PASTURE"] if r[0] == 0 else [r[2]]), "build_pasture"
    return None


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 27:
        q3 = stats["districts"][3]
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(14, max(0, q3_cells - 5))
        r = _mixed_livestock_action(obs, farm, idx, p, reserved,
                                    TARGET_COWS, TARGET_SHEEP, pasture_target)
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
    productive = int(stats.get("productive", 0) or 0)
    qs = stats["districts"]
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))
    species = _species_counts(farm.get("tiles") or [])
    cows, sheep = species["COW"], species["SHEEP"]
    animals = cows + sheep
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land": 0, "hires": 0, "cows": 0, "sheep": 0,
                            "feed": 0, "seeds": {}, "sell_qty": 0,
                            "reserve": 0.0, "ranked": [], "species": species}

    liquidate = day >= 27
    keep_wheat = 0 if liquidate else max(10, animals * 4)
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = keep_wheat if item == "WHEAT" else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or item in {"MILK", "WOOL", "FERTILIZER"} or sell >= 2):
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    reserve = 400 + 60 * len(hands) + 95 * animals
    if day >= 22:
        reserve += 500
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q2_prod = int(q2.get("productive", 0) or 0)
    q3_prod = int(q3.get("productive", 0) or 0)
    q3_animals = int(q3.get("animals", 0) or 0)

    next_cost = {1: 1000, 2: 2000, 3: 4000}.get(lands, 10**9)
    setup = {1: 500, 2: 1400, 3: 2200}.get(lands, 0)
    land_ok = False
    if lands == 1:
        land_ok = 4 <= day <= 8 and productive >= 8 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = 7 <= day <= 12 and q2_prod >= 8 and productive >= 20 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (11 <= day <= 17 and q3_prod >= 12 and q3_animals >= 8 and
                   productive >= 38 and money >= reserve + next_cost + setup + 3000)
    expected_daily = 1100 if lands == 1 else 1700 if lands == 2 else 2100
    expected = max(0, horizon - 4) * expected_daily
    roi = (expected - next_cost - setup) / max(1, next_cost + setup)
    meta["ranked"].append(["land", round(roi, 2)])
    if lands < 4 and land_ok and roi > 1.0 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable = max(0.0, spendable - next_cost)

    desired = 4
    if day >= 5:
        desired = 6
    if lands >= 2 and day >= 7:
        desired = 10
    if lands >= 3 and day >= 9:
        desired = 12
    if lands >= 4:
        desired = 14
    if day <= 18 and len(hands) < desired and spendable >= 100 and len(orders) < 10:
        add = min(2, desired - len(hands), 10 - len(orders))
        for _ in range(add):
            orders.append(["HIRE"])
            meta["hires"] += 1

    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in inventories)
    feed_target = animals * 5
    if animals and total_wheat < feed_target and day < 27 and len(orders) < 10:
        need = min(50, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, spendable - 250) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            spendable -= buy * 10

    if lands >= 3 and day <= 20 and len(orders) < 10:
        pasture = int(q3.get("pasture", 0) or 0)
        shed_cows = int(shed.get("COW", 0) or 0)
        shed_sheep = int(shed.get("SHEEP", 0) or 0)
        capacity = max(0, pasture - animals - shed_cows - shed_sheep)
        deficits = [(TARGET_SHEEP - sheep - shed_sheep, "SHEEP"),
                    (TARGET_COWS - cows - shed_cows, "COW")]
        deficits = [(d, a) for d, a in deficits if d > 0]
        deficits.sort(reverse=True)
        for deficit, animal in deficits:
            if capacity <= 0 or len(orders) >= 10:
                break
            cost = ANIMAL_COST[animal]
            daily = 150 if animal == "COW" else 135
            aroi = (max(0, horizon - 3) * daily - cost) / cost
            meta["ranked"].append([animal.lower(), round(aroi, 2)])
            affordable = max(0, int(max(0.0, spendable - 500) // cost))
            buy = min(2, deficit, capacity, affordable)
            if buy > 0 and aroi > 1.0:
                orders.append(["BUY_ANIMAL", animal, buy])
                meta[animal.lower() + "s"] = buy
                spendable -= buy * cost
                capacity -= buy

    if day <= 22:
        need_by: Dict[str, int] = {}
        service_cap = max(18, (len(hands) + 1) * 5)
        remaining = service_cap
        for q in range(1, lands + 1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                idle = min(idle, max(0, int(z.get("unlocked", 0) or 0) - 5 - 14))
            take = min(idle, remaining, 24)
            remaining -= take
            crop = _crop_for(day, q, obs)
            need_by[crop] = need_by.get(crop, 0) + take
        for crop, raw in sorted(need_by.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            need = max(0, min(32, raw + 4) - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, spendable - 250) // cost))
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


def agent(observation: Any, configuration: Any = None):
    return _v14.agent(observation, configuration)


def reset_state():
    return _v14.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v14.get_telemetry(clear=clear)
