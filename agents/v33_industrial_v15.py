"""V33.15 recurring-yield monetization probe.

Independent V33 architecture.  V33.14 commissioned Q3 reliably but its
maturity guard left already-available crop yield sitting on tiles, suppressing
cash recycling.  V33.15 changes only crop service semantics: any positive
`yield_units` is harvested immediately, while urgent watering retains priority
when no yield is available.  Capital allocation and sequential commissioning
remain V33.14 so the economic effect is isolated.
"""
from __future__ import annotations
from typing import Any, Mapping, Set
from agents import v33_industrial_v14 as _v14

_b = _v14._b


def _tile_tasks(tiles: Any, districts: Set[_b.Position], reserved: Set[_b.Position]):
    tasks = []
    if not isinstance(tiles, list) or not tiles:
        return tasks
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
                tasks.append((3, p, ["DIG"], "dig"))
                continue
            if kind != "PLANT" or not isinstance(tile, Mapping):
                continue
            yield_units = int(tile.get("yield_units", tile.get("yield", 0)) or 0)
            watered = bool(tile.get("watered_today", tile.get("watered", False)))
            danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
            if yield_units > 0:
                tasks.append((0, p, ["HARVEST"], "harvest_crop"))
            elif not watered and danger:
                tasks.append((1, p, ["WATER"], "water_urgent"))
            elif not watered:
                tasks.append((2, p, ["WATER"], "water"))
    return tasks


_b._tile_tasks = _tile_tasks


def agent(observation: Any, configuration: Any = None):
    return _v14.agent(observation, configuration)


def reset_state():
    return _v14.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v14.get_telemetry(clear=clear)
