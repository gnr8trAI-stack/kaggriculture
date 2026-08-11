"""V33.12 cash-conversion industrial policy.

Independent V33 architecture.  V33.11 proved the four-quadrant mechanics gate:
all 24 benchmark games reached four lands and operated Q3/Q4, but terminal cash
remained trapped in long crop cycles.  This revision keeps the V33.10 allocator
and V33.11 district architecture while shortening harvest-to-cash latency and
forcing earlier terminal monetization.

V19/V32 are not imported or used as architecture parents.
"""
from __future__ import annotations
from typing import Any, Mapping, Set
from agents import v33_industrial_v10 as _v10

_b = _v10._b


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    # Q3 remains the feed district.  Outside Q3 use melon only while a full
    # monetization window remains; late capital goes to quick-turn wheat.
    if district == 3:
        return "WHEAT"
    return "MELON" if day <= 16 else "WHEAT"


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
    # These are cash-conversion thresholds, deliberately shorter than V33.11's
    # nominal full cycle.  The crop probe shows yield_units exists immediately;
    # waiting to nominal maturity stranded too much working capital at terminal.
    harvest_age = {"WHEAT": 2, "CARROT": 2, "TOMATO": 5, "STRAWBERRY": 6, "MELON": 6}
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            p = (x, y)
            if _b._quadrant(n, p) not in districts or p in reserved:
                continue
            kind = _b._kind(tile)
            if kind == "WEED":
                tasks.append((5, p, ["DIG"], "dig"))
                continue
            if kind != "PLANT" or not isinstance(tile, Mapping):
                continue
            crop = str(tile.get("crop", "")).upper()
            watered = bool(tile.get("watered_today", tile.get("watered", False)))
            danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
            yield_units = int(tile.get("yield_units", tile.get("yield", 0)) or 0)
            age = _age(tile, day)
            # Survival first.  From day 23 onward every available yield is cash,
            # giving the labour force a full week to harvest, drop and sell.
            if not watered and danger and day < 27:
                tasks.append((0, p, ["WATER"], "water_urgent"))
            elif yield_units > 0 and (day >= 23 or age >= harvest_age.get(crop, 2)):
                tasks.append((1, p, ["HARVEST"], "harvest_crop"))
            elif not watered and day < 25:
                tasks.append((2, p, ["WATER"], "water"))
    return tasks


_b._CURRENT_DAY = 0
_base_agent = _b.agent


def agent(observation: Any, configuration: Any = None):
    obs = _b._obs(observation)
    _b._CURRENT_DAY = int(obs.get("day", 0) or 0)
    return _base_agent(observation, configuration)


_v10._crop_for = _crop_for
_b._crop_for = _crop_for
_b._tile_tasks = _tile_tasks


def reset_state():
    _b._CURRENT_DAY = 0
    return _b.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _b.get_telemetry(clear=clear)
