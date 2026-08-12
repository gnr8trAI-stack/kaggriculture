"""V33.38 canonical animal-state decoding.

Single-mechanism revision over V33.37. Preserve all crop, land, labour, Q3
capacity, mixed-livestock targets, and capital policy. Fix only livestock state
interpretation: Kaggriculture may expose tile['animal'] as a nested mapping
rather than a bare species string, with feed/care/yield/fertilizer fields nested
inside that object. V33.37 treated only bare strings as COW/SHEEP, so existing
animals could become invisible to service and allocator logic.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial_v37 as _p

_b = _p._b


def _animal_record(tile: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = tile.get("animal")
    if isinstance(raw, Mapping):
        merged = dict(tile)
        merged.update(raw)
        return merged
    return tile


def _animal_type(tile: Mapping[str, Any]) -> str:
    raw = tile.get("animal")
    if isinstance(raw, Mapping):
        for k in ("type", "kind", "name", "animal_type", "species"):
            v = raw.get(k)
            if v:
                return str(v).upper()
    elif raw:
        return str(raw).upper()
    for k in ("animal_type", "species"):
        v = tile.get(k)
        if v:
            return str(v).upper()
    return ""


def _animal_counts(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0}
    for row in farm.get("tiles") or []:
        if not isinstance(row, list):
            continue
        for tile in row:
            if not isinstance(tile, Mapping):
                continue
            a = _animal_type(tile)
            if a in counts:
                counts[a] += 1
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    for a in counts:
        counts[a] += int(shed.get(a, 0) or 0)
    inventories = private.get("inventories", [])
    if isinstance(inventories, list):
        for inv in inventories:
            m = _b._m(inv)
            for a in counts:
                counts[a] += int(m.get(a, 0) or 0)
    return counts


def _livestock_action(obs, farm, idx, p, stats, reserved):
    day = int(obs.get("day", 0) or 0); hour = int(obs.get("hour", 0) or 0)
    tiles = farm.get("tiles") or []; private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); inv = _b._inventory(private, idx)
    q3 = _p._q3_pastures(tiles)
    active = []
    empty = []
    for g, t in q3:
        a = _animal_type(t)
        if a in {"COW", "SHEEP"}:
            active.append((g, t, _animal_record(t)))
        elif not t.get("animal"):
            empty.append(g)

    for a in ("COW", "SHEEP"):
        if int(inv.get(a, 0) or 0) > 0 and empty:
            g = _p._nearest(tiles, p, [x for x in empty if x not in reserved])
            if g is not None:
                reserved.add(g); return _p._go(tiles, p, g, ["PLACE", a]), "place_" + a.lower()

    if int(inv.get("WHEAT", 0) or 0) > 0:
        g = _p._nearest(tiles, p, [g for g, t, a in active if not bool(a.get("fed_today", a.get("fed", False))) and g not in reserved])
        if g is not None:
            reserved.add(g); return _p._go(tiles, p, g, ["FEED"]), "feed"

    unfed = [g for g, t, a in active if not bool(a.get("fed_today", a.get("fed", False))) and g not in reserved]
    if unfed and int(shed.get("WHEAT", 0) or 0) > 0:
        return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", min(10, int(shed.get("WHEAT", 0) or 0))]), "pickup_feed"

    g = _p._nearest(tiles, p, [g for g, t, a in active if bool(a.get("fertilizer_available", False)) and g not in reserved])
    if g is not None:
        reserved.add(g); return _p._go(tiles, p, g, ["COLLECT_FERTILIZER"]), "collect_fertilizer"

    g = _p._nearest(tiles, p, [g for g, t, a in active if int(a.get("yield_units", a.get("yield", 0)) or 0) > 0 and g not in reserved])
    if g is not None:
        reserved.add(g); return _p._go(tiles, p, g, ["HARVEST"]), "harvest_livestock"

    g = _p._nearest(tiles, p, [g for g, t, a in active if not bool(a.get("cared_today", a.get("cared", False))) and g not in reserved])
    if g is not None:
        reserved.add(g); return _p._go(tiles, p, g, ["CARE"]), "care"

    output = sum(int(v or 0) for k, v in inv.items() if str(k).upper() not in {"WHEAT", "COW", "SHEEP"})
    if output >= 5 or (output > 0 and hour >= 17):
        return _b._to_shed(tiles, p, ["DROP"]), "drop_livestock"

    counts = _animal_counts(obs, farm)
    for a, target in (("COW", _p.COW_TARGET), ("SHEEP", _p.SHEEP_TARGET)):
        if counts[a] < target and int(shed.get(a, 0) or 0) > 0 and empty:
            return _b._to_shed(tiles, p, ["PICKUP", a, 1]), "pickup_" + a.lower()

    if day <= 17 and len(q3) < _p.PASTURE_TARGET:
        g = _p._nearest(tiles, p, [x for x in _b._empty_targets(tiles, {3}, reserved)])
        if g is not None:
            reserved.add(g); return _p._go(tiles, p, g, ["BUILD_PASTURE"]), "build_pasture"

    if output > 0:
        return _b._to_shed(tiles, p, ["DROP"]), "drop_livestock"
    return None


# Patch V33.37 module globals in place; its unit-action and capital-allocator
# functions resolve these names dynamically from that module's namespace.
_p._animal_counts = _animal_counts
_p._livestock_action = _livestock_action
_b._unit_action = _p._unit_action
_b._capital_allocator = _p._capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)

def reset_state():
    return _p.reset_state()

def reset_telemetry():
    return reset_state()

def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
