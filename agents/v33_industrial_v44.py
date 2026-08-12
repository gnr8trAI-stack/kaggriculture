"""V33.44 isolated idle-capacity goose overlay.

Single economic mechanism over V33.42: keep its 11-hand three-land labour cap
and the V33.39 cow/sheep/crop engine unchanged, then add at most four geese in
Q3 using only otherwise-empty cells.  Unlike V33.43 this does not replace the
cow/sheep factory, does not change crop roles, and never buys Q4.  Goose capex
is allowed only against already-built coop capacity and a conservative cash
reserve.

Hypothesis: V33.43 proved goose revenue can improve the V33.42 parent, but its
full species replacement displaced productive crop/estate capacity.  A tiny
additive overlay tests whether eggs + fertilizer can monetize genuine idle Q3
capacity without sacrificing the parent engine.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping, Set, Tuple
from agents import v33_industrial_v42 as _p

_v39 = _p._p
_b = _p._b
_parent_allocator = _b._capital_allocator
_parent_livestock = _v39._livestock_action

GOOSE_COST = 300
GOOSE_TARGET = 4
COOP_TARGET = 4
_PEAK = {"geese": 0, "coops": 0, "lands": 0}


def _quadrant(n: int, p: Tuple[int, int]) -> int:
    return _b._quadrant(n, p)


def _goose_state(tiles):
    coops = []; geese = []
    n = len(tiles) if isinstance(tiles, list) else 0
    for y, row in enumerate(tiles if isinstance(tiles, list) else []):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if not isinstance(tile, Mapping) or str(tile.get("kind", "")).upper() != "COOP":
                continue
            q = _quadrant(n, (x, y))
            if q != 3:
                continue
            rec = ((x, y), tile)
            coops.append(rec)
            raw = tile.get("animal")
            typ = ""
            if isinstance(raw, Mapping):
                typ = str(raw.get("type") or raw.get("kind") or raw.get("name") or raw.get("species") or "").upper()
            elif raw:
                typ = str(raw).upper()
            if typ == "GOOSE":
                geese.append(rec)
    return coops, geese


def _nearest(tiles, p, goals):
    best = None
    for g in goals:
        rr = _b._route(tiles, p, g)
        if rr is None:
            continue
        cand = (rr[0], g[1], g[0], g, rr[1])
        if best is None or cand < best:
            best = cand
    return best


def _go(tiles, p, g, action):
    if p == g:
        return action
    rr = _b._route(tiles, p, g)
    return [rr[1]] if rr is not None else ["PASS"]


def _goose_urgent(obs, farm, idx, p, reserved: Set[Tuple[int, int]]):
    """Only survival/yield actions that cannot safely wait behind cow/sheep work."""
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); inv = _b._inventory(private, idx)
    coops, geese = _goose_state(tiles)
    empty = [g for g, t in coops if not t.get("animal")]

    if int(inv.get("GOOSE", 0) or 0) > 0 and empty:
        r = _nearest(tiles, p, [g for g in empty if g not in reserved])
        if r is not None:
            reserved.add(r[3]); return _go(tiles, p, r[3], ["PLACE", "GOOSE"]), "place_goose_overlay"

    if int(inv.get("WHEAT", 0) or 0) > 0:
        goals = [g for g, t in geese if not bool(t.get("fed_today", t.get("fed", False))) and g not in reserved]
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles, p, r[3], ["FEED"]), "feed_goose_overlay"
    unfed = [g for g, t in geese if not bool(t.get("fed_today", t.get("fed", False))) and g not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", min(6, int(shed.get("WHEAT", 0) or 0))]), "pickup_goose_feed_overlay"

    goals = [g for g, t in geese if int(t.get("yield_units", t.get("yield", 0)) or 0) > 0 and g not in reserved]
    r = _nearest(tiles, p, goals)
    if r is not None:
        reserved.add(r[3]); return _go(tiles, p, r[3], ["HARVEST"]), "harvest_goose_overlay"
    return None


def _goose_optional(obs, farm, idx, p, reserved: Set[Tuple[int, int]]):
    day = int(obs.get("day", 0) or 0); hour = int(obs.get("hour", 0) or 0)
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); inv = _b._inventory(private, idx)
    coops, geese = _goose_state(tiles)

    output = sum(int(v or 0) for k, v in inv.items() if str(k).upper() not in {"WHEAT", "GOOSE", "COW", "SHEEP"})
    if output >= 4 or (output > 0 and hour >= 16) or (day >= 27 and output > 0):
        return _b._to_shed(tiles, p, ["DROP"]), "drop_goose_overlay"

    goals = [g for g, t in geese if bool(t.get("fertilizer_available", False)) and g not in reserved]
    r = _nearest(tiles, p, goals)
    if r is not None:
        reserved.add(r[3]); return _go(tiles, p, r[3], ["COLLECT_FERTILIZER"]), "fertilizer_goose_overlay"

    if day <= 25:
        goals = [g for g, t in geese if not bool(t.get("cared_today", t.get("cared", False))) and g not in reserved]
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles, p, r[3], ["CARE"]), "care_goose_overlay"

    empty = [g for g, t in coops if not t.get("animal")]
    if len(geese) < GOOSE_TARGET and int(shed.get("GOOSE", 0) or 0) > 0 and empty:
        return _b._to_shed(tiles, p, ["PICKUP", "GOOSE", 1]), "pickup_goose_overlay"

    # Build only in a genuinely empty Q3 cell, after the parent livestock engine
    # has had first refusal on this worker action.
    if day <= 19 and len(coops) < COOP_TARGET:
        goals = _b._empty_targets(tiles, {3}, reserved)
        r = _nearest(tiles, p, goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles, p, r[3], ["BUILD_COOP"]), "build_coop_overlay"
    return None


def _livestock_action(obs, farm, idx, p, stats, reserved):
    # Goose survival and matured cash yield first, then preserve the parent
    # cow/sheep service ordering, then spend truly idle worker cycles on the overlay.
    r = _goose_urgent(obs, farm, idx, p, reserved)
    if r is not None:
        return r
    r = _parent_livestock(obs, farm, idx, p, stats, reserved)
    if r is not None:
        return r
    return _goose_optional(obs, farm, idx, p, reserved)


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    if not isinstance(meta, dict):
        meta = {}
    else:
        meta = dict(meta)

    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    money = float(farm.get("money", 0) or 0)
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); invs = private.get("inventories", [])
    coops, geese = _goose_state(tiles)
    carried = 0
    if isinstance(invs, list):
        for inv in invs:
            carried += int(_b._m(inv).get("GOOSE", 0) or 0)
    total = len(geese) + int(shed.get("GOOSE", 0) or 0) + carried
    open_capacity = max(0, len(coops) - total)

    # Do not let this experiment open Q4; strip only a parent Q4 land order.
    if lands >= 3:
        orders = [o for o in orders if not (isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND")]
        meta["land"] = 0; meta["land_cost"] = 0

    # Buy only after construction, only while a 4-day first-yield horizon remains,
    # and only with a cash floor large enough to leave the parent engine funded.
    need = max(0, GOOSE_TARGET - total)
    if lands == 3 and day <= 22 and open_capacity > 0 and need > 0 and money >= 6500:
        affordable = max(0, int((money - 5000) // GOOSE_COST))
        buy = min(2, open_capacity, need, affordable)
        if buy > 0:
            if len(orders) >= 10:
                # Goose overlay may displace only optional seed capex, never sale,
                # HIRE, feed, land-to-Q3, or parent cow/sheep orders.
                for i in range(len(orders) - 1, -1, -1):
                    if isinstance(orders[i], list) and orders[i] and str(orders[i][0]).upper() == "BUY_SEED":
                        orders.pop(i); break
            if len(orders) < 10:
                orders.append(["BUY_ANIMAL", "GOOSE", buy])
                meta["overlay_geese"] = buy

    global _PEAK
    _PEAK["geese"] = max(_PEAK["geese"], len(geese))
    _PEAK["coops"] = max(_PEAK["coops"], len(coops))
    _PEAK["lands"] = max(_PEAK["lands"], lands)
    meta["overlay_goose_total"] = total
    meta["overlay_coops"] = len(coops)
    return orders[:10], meta


_v39._livestock_action = _livestock_action
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    global _PEAK
    _PEAK = {"geese": 0, "coops": 0, "lands": 0}
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)


def industrial_peaks():
    return dict(_PEAK)
