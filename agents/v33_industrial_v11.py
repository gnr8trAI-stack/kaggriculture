"""V33.11 maturity-aware industrial compounder.

Independent V33 architecture. This revision fixes a core economic defect in the
V33 dispatcher: crops were harvested whenever any yield appeared, which destroys
the multi-day yield compounding that makes high-value crops profitable. V33.11
keeps V33.10's land/labour/livestock capital allocator but restores crop-specific
maturity harvesting and a melon-heavy cash engine outside the Q3 feed district.

V19/V32 are not imported or used as architecture parents.
"""
from __future__ import annotations
from typing import Any, Mapping, Set
from agents import v33_industrial_v10 as _v10

_b = _v10._b


def _age(tile: Mapping[str, Any], day: int) -> int:
    raw = tile.get("planted_day", day)
    planted = day if raw is None else int(raw)
    return max(0, day - planted)


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    # Q3 is the feed district. Q1/Q2/Q4 use the proven high-value melon cycle
    # while a complete ten-day cycle still fits; late planting switches to wheat.
    if district == 3:
        return "WHEAT"
    if day <= 18:
        return "MELON"
    return "WHEAT"


def _tile_tasks(tiles: Any, districts: Set[int], reserved: Set[_b.Position]):
    tasks = []
    if not isinstance(tiles, list) or not tiles:
        return tasks
    day = int(getattr(_b, "_CURRENT_DAY", 0) or 0)
    n = len(tiles)
    first_yield = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
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
            # Survival always wins. Mature harvest comes next, then routine water.
            if not watered and danger:
                tasks.append((0, p, ["WATER"], "water_urgent"))
            elif yield_units > 0 and (day >= 28 or age >= first_yield.get(crop, 0)):
                tasks.append((1, p, ["HARVEST"], "harvest_crop"))
            elif not watered:
                tasks.append((2, p, ["WATER"], "water"))
    return tasks


# Base task evaluation needs the current game day. Keep this tiny state in the
# independent base module so the original district router can remain unchanged.
_b._CURRENT_DAY = 0
_base_agent = _b.agent


def agent(observation: Any, configuration: Any = None):
    obs = _b._obs(observation)
    _b._CURRENT_DAY = int(obs.get("day", 0) or 0)
    return _base_agent(observation, configuration)


# Patch both lexical/global call sites used by V33.10 and the base dispatcher.
_v10._crop_for = _crop_for
_b._crop_for = _crop_for
_b._tile_tasks = _tile_tasks


def reset_state():
    _b._CURRENT_DAY = 0
    return _b.reset_state()


def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool = False): return _b.get_telemetry(clear=clear)
