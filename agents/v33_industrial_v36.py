"""V33.36 mixed-market industrial portfolio.

Independent V33 architecture.  Uses the V33 four-district executor/capital
framework, but Q3 is a replay-derived mixed livestock factory (8 cows + 6
sheep), not a single-product cow monoculture.  This spreads premium output
across milk and wool while monetizing the robust fertilizer by-product from
all animals.  Q4 is admitted only after Q3 is substantially commissioned and
cash can fund the fourth district without consuming the operating reserve.

V19.2 is benchmark control only and is not imported by this agent.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Tuple
from agents import v33_industrial_v33 as _v33

_v28 = _v33._v28
_b = _v33._b
_base_allocator = _v28._capital_allocator
_base_unit_action = _v28._unit_action

COW_TARGET = 8
SHEEP_TARGET = 6
PASTURE_TARGET = COW_TARGET + SHEEP_TARGET
ANIMAL_COST = {"COW": 400, "SHEEP": 500}


def _animal_counts(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0}
    tiles = farm.get("tiles") or []
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if not isinstance(tile, Mapping):
                continue
            a = str(tile.get("animal", "") or "").upper()
            if a in counts:
                counts[a] += 1
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    inventories = private.get("inventories", [])
    for a in counts:
        counts[a] += int(shed.get(a, 0) or 0)
    if isinstance(inventories, list):
        for inv in inventories:
            m = _b._m(inv)
            for a in counts:
                counts[a] += int(m.get(a, 0) or 0)
    return counts


def _q3_structures(tiles):
    out = []
    n = len(tiles) if isinstance(tiles, list) else 0
    h = n // 2
    if not n:
        return out
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if not (x < h and y >= h) or not isinstance(tile, Mapping):
                continue
            if str(tile.get("kind", "")).upper() == "PASTURE":
                out.append(((x, y), tile))
    return out


def _go(tiles, p, target, action):
    if p == target:
        return action
    rr = _b._route(tiles, p, target)
    return [rr[1]] if rr is not None else ["PASS"]


def _nearest(tiles, p, poss):
    choices = []
    for g in poss:
        rr = _b._route(tiles, p, g)
        if rr is not None:
            choices.append((rr[0], g[1], g[0], g))
    if not choices:
        return None
    choices.sort()
    return choices[0][3]


def _mixed_livestock_action(obs, farm, idx, p, stats, reserved):
    day = int(obs.get("day", 0) or 0); hour = int(obs.get("hour", 0) or 0)
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    inv = _b._inventory(private, idx)
    q3 = _q3_structures(tiles)
    active = [(g,t) for g,t in q3 if str(t.get("animal", "") or "").upper() in {"COW","SHEEP"}]
    empty = [g for g,t in q3 if not t.get("animal")]

    # Animals already carried are placed before any other work so purchased
    # biological capital begins its yield clock immediately.
    for a in ("COW", "SHEEP"):
        if int(inv.get(a, 0) or 0) > 0 and empty:
            g = _nearest(tiles, p, [x for x in empty if x not in reserved])
            if g is not None:
                reserved.add(g); return _go(tiles, p, g, ["PLACE", a]), "place_" + a.lower()

    # Survival is absolute priority. One wheat feeds one animal; workers carry
    # a useful batch to reduce shed round-trips.
    if int(inv.get("WHEAT", 0) or 0) > 0:
        poss = [g for g,t in active if not bool(t.get("fed_today", False)) and g not in reserved]
        g = _nearest(tiles, p, poss)
        if g is not None:
            reserved.add(g); return _go(tiles, p, g, ["FEED"]), "feed"

    output = sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","COW","SHEEP"})
    if output >= 6 or (output > 0 and hour >= 17):
        return _b._to_shed(tiles, p, ["DROP"]), "drop_livestock_output"

    unfed = [g for g,t in active if not bool(t.get("fed_today", False)) and g not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", min(8, int(shed.get("WHEAT", 0) or 0))]), "pickup_feed"

    # Harvest before care so yield caps never block the next production tick.
    poss = [g for g,t in active if int(t.get("yield_units", 0) or 0) > 0 and g not in reserved]
    g = _nearest(tiles, p, poss)
    if g is not None:
        reserved.add(g); return _go(tiles, p, g, ["HARVEST"]), "harvest_livestock"

    poss = [g for g,t in active if not bool(t.get("cared_today", False)) and g not in reserved]
    g = _nearest(tiles, p, poss)
    if g is not None:
        reserved.add(g); return _go(tiles, p, g, ["CARE"]), "care_livestock"

    # Fertilizer is deliberately serviced: every surviving animal makes one
    # unit/day and its market absorbs supply far better than milk/wool gluts.
    poss = [g for g,t in active if bool(t.get("fertilizer_available", False)) and g not in reserved]
    g = _nearest(tiles, p, poss)
    if g is not None:
        reserved.add(g); return _go(tiles, p, g, ["COLLECT_FERTILIZER"]), "collect_fertilizer"

    counts = _animal_counts(obs, farm)
    for a,target in (("COW", COW_TARGET), ("SHEEP", SHEEP_TARGET)):
        if counts[a] < target and int(shed.get(a, 0) or 0) > 0 and empty:
            return _b._to_shed(tiles, p, ["PICKUP", a, 1]), "pickup_" + a.lower()

    if day <= 17 and len(q3) < PASTURE_TARGET:
        candidates = [g for g in _b._empty_targets(tiles, {3}, reserved)]
        g = _nearest(tiles, p, candidates)
        if g is not None:
            reserved.add(g); return _go(tiles, p, g, ["BUILD_PASTURE"]), "build_pasture"

    if output > 0:
        return _b._to_shed(tiles, p, ["DROP"]), "drop_livestock_output"
    return None


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    if role == "livestock" and int(stats.get("lands", 0) or 0) >= 3:
        r = _mixed_livestock_action(obs, farm, idx, p, stats, reserved)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _mixed_allocator(obs, farm, stats):
    orders, meta = _base_allocator(obs, farm, stats)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30-day)
    money = float(farm.get("money", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    productive = int(stats.get("productive", 0) or 0)
    q3 = stats.get("districts", {}).get(3, {})
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    counts = _animal_counts(obs, farm)

    # This allocator owns biological purchases and the Q4 admission decision.
    clean = [o for o in orders if not (isinstance(o,list) and o and str(o[0]).upper() == "BUY_ANIMAL")]

    if lands == 3:
        q3a = int(q3.get("animals", 0) or 0); q3p = int(q3.get("pasture", 0) or 0)
        q3prod = int(q3.get("productive", 0) or 0)
        q4_ok = day <= 16 and horizon >= 14 and q3a >= 12 and q3p >= 14 and q3prod >= 14 and productive >= 50 and money >= 16000
        if not q4_ok:
            clean = [o for o in clean if not (isinstance(o,list) and o and str(o[0]).upper() == "BUY_LAND")]
            meta = dict(meta); meta["land"] = 0; meta["land_cost"] = 0
            meta.setdefault("ranked", []).append(["q4_mixed_roi_gate", -1.0])
        else:
            meta.setdefault("ranked", []).append(["q4_mixed_roi_gate", 1.0])

    # Buy only against built empty Q3 pastures, preserving a feed/seed reserve.
    if lands >= 3 and day <= 18 and len(clean) < 10:
        q3_struct = _q3_structures(farm.get("tiles") or [])
        empty_slots = sum(1 for _,t in q3_struct if not t.get("animal"))
        if empty_slots > 0:
            prices = _b._prices(obs)
            reserve = 1000 + int(stats.get("animals",0) or 0) * 140
            spend = max(0.0, money-reserve)
            # Existing orders can spend cash too; discount discretionary budget
            # conservatively rather than double-counting the bank balance.
            if any(o and o[0] == "BUY_LAND" for o in clean): spend -= 4000 if lands==3 else (2000 if lands==2 else 1000)
            deficits = {"COW": max(0, COW_TARGET-counts["COW"]), "SHEEP": max(0, SHEEP_TARGET-counts["SHEEP"])}
            # Prefer whichever premium market currently has the stronger quote;
            # replay targets cap the final mix at 8 cows / 6 sheep.
            scored = sorted(((float(prices.get("MILK" if a=="COW" else "WOOL", 1) or 1) / (160 if a=="COW" else 200), a) for a in deficits), reverse=True)
            slots = empty_slots
            for _,a in scored:
                if slots <= 0 or len(clean) >= 10: break
                need = min(deficits[a], slots); cost = ANIMAL_COST[a]
                affordable = max(0, int(max(0.0, spend)//cost)); buy = min(need, affordable, 4)
                if buy > 0:
                    clean.append(["BUY_ANIMAL", a, buy]); spend -= buy*cost; slots -= buy
                    meta.setdefault("mixed_animals", {})[a] = buy

    meta = dict(meta)
    meta["cow_total"] = counts["COW"]; meta["sheep_total"] = counts["SHEEP"]
    meta["mixed_target"] = [COW_TARGET, SHEEP_TARGET]
    return clean[:10], meta


_v28._unit_action = _unit_action
_v28._capital_allocator = _mixed_allocator


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
