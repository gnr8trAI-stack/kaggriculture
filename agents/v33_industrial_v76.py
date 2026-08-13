"""V33.76 early mixed-herd compounding.

Single architectural mechanism over verified V33.66: livestock becomes a first-class
capital engine before Q3. Q1/Q2 may host a small mixed cow/sheep herd from the
opening phase; the same service crew follows those animals after Q3 opens. Land,
crop choice, demand-aware sales, Q3 utilization gate, Q4 suppression and terminal
liquidation remain the V33.66 parent.

This directly tests the elite-replay signal that profitable farms compound crops
and recurring animal output together from the opening days instead of waiting for
a dedicated third district before buying their first animal.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set, Tuple
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_roles = _v28._roles
_parent_unit_action = _v28._unit_action
_parent_allocator = _p._capital_allocator

ANIMAL_COST = {"COW": 400, "SHEEP": 500}


def _animal_positions(tiles: Any):
    out = []
    if not isinstance(tiles, list):
        return out
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if isinstance(tile, Mapping) and _b._kind(tile) == "PASTURE":
                out.append(((x, y), tile, str(tile.get("animal", "")).upper()))
    return out


def _species_counts(tiles: Any) -> Dict[str, int]:
    out = {"COW": 0, "SHEEP": 0}
    for _, _, a in _animal_positions(tiles):
        if a in out:
            out[a] += 1
    return out


def _mixed_targets(day: int, lands: int) -> Tuple[int, int, int]:
    # Conservative reconstruction of the elite opening trajectory.  The third
    # value is total pasture capacity, not an obligation to fill every slot.
    if day <= 4:
        return 3, 1, 4
    if day <= 7:
        return 4, 2, 6
    if day <= 10:
        return 5, 4, 9
    if lands >= 3 and day <= 20:
        return 8, 6, 14
    return 8, 6, 14


def _roles(lands: int, hand_count: int) -> List[str]:
    roles = list(_parent_roles(lands, hand_count))
    total = hand_count + 1
    if lands < 3 and total >= 4:
        # Keep at least three crop operators plus the farmer-side bootstrap path.
        crew = min(3, max(1, total - 4))
        for i in range(total - crew, total):
            if i >= 1:
                roles[i] = "livestock"
    return roles


def _mixed_livestock_action(obs: Mapping[str, Any], farm: Mapping[str, Any], idx: int,
                             p: Tuple[int, int], reserved: Set[Tuple[int, int]],
                             target_cows: int, target_sheep: int, pasture_target: int,
                             lands: int):
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    inv = _b._inventory(private, idx)
    ps = _animal_positions(tiles)
    active = [(pp, t, a) for pp, t, a in ps if a in {"COW", "SHEEP"}]
    empty = [pp for pp, _, a in ps if not a]

    if int(inv.get("WHEAT", 0) or 0) > 0:
        goals = [pp for pp, t, _ in active
                 if not bool(t.get("fed_today", False)) and pp not in reserved]
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["FEED"] if r[0] == 0 else [r[2]]), "v76_feed"

    output = sum(int(v or 0) for k, v in inv.items()
                 if str(k).upper() not in {"WHEAT", "COW", "SHEEP"})
    if output > 0:
        return _b._to_shed(tiles, p, ["DROP"]), "v76_drop_output"

    unfed = [pp for pp, t, _ in active
             if not bool(t.get("fed_today", False)) and pp not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        qty = min(8, int(shed.get("WHEAT", 0) or 0))
        return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", qty]), "v76_pickup_feed"

    for pred, action, label in (
        (lambda t: int(t.get("yield_units", t.get("yield", 0)) or 0) > 0,
         ["HARVEST"], "v76_harvest"),
        (lambda t: not bool(t.get("cared_today", t.get("cared", False))),
         ["CARE"], "v76_care"),
        (lambda t: bool(t.get("fertilizer_available", False)),
         ["COLLECT_FERTILIZER"], "v76_fertilizer"),
    ):
        goals = [pp for pp, t, _ in active if pred(t) and pp not in reserved]
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (action if r[0] == 0 else [r[2]]), label

    # Place purchased livestock before constructing more pasture.
    for animal in ("SHEEP", "COW"):
        if int(inv.get(animal, 0) or 0) > 0 and empty:
            r = _b._nearest(tiles, p, [x for x in empty if x not in reserved])
            if r is not None:
                reserved.add(r[1])
                return (["PLACE", animal] if r[0] == 0 else [r[2]]), "v76_place_" + animal.lower()
    for animal in ("SHEEP", "COW"):
        if int(shed.get(animal, 0) or 0) > 0 and empty:
            return _b._to_shed(tiles, p, ["PICKUP", animal, 1]), "v76_pickup_" + animal.lower()

    counts = _species_counts(tiles)
    if len(ps) < pasture_target and sum(counts.values()) < target_cows + target_sheep:
        # Before Q3, reserve the far edge of current crop districts for pasture;
        # once Q3 opens, all new biological capex is concentrated there.
        districts = {3} if lands >= 3 else ({2} if lands >= 2 else {1})
        goals = _b._empty_targets(tiles, districts, reserved)
        r = _b._nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[1])
            return (["BUILD_PASTURE"] if r[0] == 0 else [r[2]]), "v76_build_pasture"
    return None


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and day <= 27:
        tc, ts, pasture_target = _mixed_targets(day, lands)
        action = _mixed_livestock_action(obs, farm, idx, p, reserved,
                                         tc, ts, pasture_target, lands)
        if action is not None:
            return action
        # Preserve the parent's Q3 feed/crop fallback once livestock is serviced.
        if lands >= 3:
            role = "feed"
    return _parent_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    orders = [list(o) if isinstance(o, list) else o for o in orders]
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    money = float(farm.get("money", 0) or 0)
    tiles = farm.get("tiles") or []
    species = _species_counts(tiles)
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    ps = _animal_positions(tiles)
    tc, ts, _ = _mixed_targets(day, lands)
    shed_counts = {a: int(shed.get(a, 0) or 0) for a in ("COW", "SHEEP")}
    committed = species["COW"] + species["SHEEP"] + shed_counts["COW"] + shed_counts["SHEEP"]
    capacity = max(0, len(ps) - committed)

    # Do not buy biological capex in the same packet as land; let the purchased
    # district settle first and preserve operating runway.
    has_land = any(isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND" for o in orders)
    reserve = 1100 + 70 * committed
    spendable = max(0.0, money - reserve)
    animal_orders = []
    if day <= 20 and capacity > 0 and not has_land:
        # Sheep first when most under target, otherwise cows. Limit to two head
        # per packet to avoid recreating the V33.26 cash-drain failure.
        deficits = [(ts - species["SHEEP"] - shed_counts["SHEEP"], "SHEEP"),
                    (tc - species["COW"] - shed_counts["COW"], "COW")]
        deficits = [(d, a) for d, a in deficits if d > 0]
        deficits.sort(reverse=True)
        remaining = min(2, capacity)
        for deficit, animal in deficits:
            if remaining <= 0:
                break
            cost = ANIMAL_COST[animal]
            affordable = max(0, int(spendable // cost))
            buy = min(deficit, remaining, affordable)
            if buy > 0:
                animal_orders.append(["BUY_ANIMAL", animal, buy])
                spendable -= buy * cost
                remaining -= buy

    if animal_orders:
        # Feed and land retain priority. Insert recurring-capital purchases before
        # discretionary seed orders if market slots are scarce.
        idx = len(orders)
        for i, o in enumerate(orders):
            if isinstance(o, list) and o and str(o[0]).upper() == "BUY_SEED":
                idx = i
                break
        for order in animal_orders:
            if len(orders) >= 10:
                # Make one seed slot available rather than dropping the animal.
                for j in range(len(orders) - 1, -1, -1):
                    o = orders[j]
                    if isinstance(o, list) and o and str(o[0]).upper() == "BUY_SEED":
                        orders.pop(j); break
            if len(orders) < 10:
                orders.insert(min(idx, len(orders)), order); idx += 1
        meta["v76_animal_orders"] = animal_orders
    else:
        meta["v76_animal_orders"] = []
    meta["v76_species"] = species
    return orders[:10], meta


# Patch the exact globals consumed by the V33.28 -> V33.65 -> V33.66 path.
_v28._roles = _roles
_v28._unit_action = _unit_action
_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
