"""V19.3: V19.2 plus one planned, solvency-gated third-land purchase.

Single economic mutation from the live V19.2 control:
- V19/V19.2 hard-code expansion to ``len(unlocked)==1`` and therefore can
  never buy a third quadrant.
- V19.3 leaves crop choice, livestock, labour, feed, service and the first
  expansion untouched, but allows exactly one additional BUY_LAND once Q2 is
  operating and the bank can fund the $2,000 land plus an operating reserve.

This is an isolated challenger, not a promoted Kaggle submission.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping

from agents import v19_2_early_scale8 as _base
from agents import v19_livestock_compound as _core

Q3_LAND_COST = 2000
Q3_OPERATING_RESERVE = 3500
Q3_MIN_DAY = 10
Q3_MAX_DAY = 16
Q3_MIN_ACTIVE_COWS = 2
Q3_MAX_WEEDS = 8
Q3_MAX_DANGER = 4

_RECORDS = deque(maxlen=4096)
_LAST_STEP = -1


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(v: Any) -> Dict[str, Any]:
    return _core._obs(v)


def _kind(tile: Any) -> str:
    return _core._kind(tile)


def _quadrant_stats(tiles: Any) -> Dict[str, Dict[str, int]]:
    out = {q: {"productive": 0, "animals": 0, "empty": 0} for q in ("NW", "NE", "SW", "SE")}
    if not isinstance(tiles, list) or not tiles:
        return out
    half = len(tiles) // 2
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            q = ("NW" if y < half and x < half else
                 "NE" if y < half and x >= half else
                 "SW" if y >= half and x < half else "SE")
            k = _kind(tile)
            if k == "EMPTY":
                out[q]["empty"] += 1
            if k in {"PLANT", "COOP", "PASTURE"}:
                out[q]["productive"] += 1
            if isinstance(tile, Mapping) and k in {"COOP", "PASTURE"} and tile.get("animal"):
                out[q]["animals"] += 1
    return out


def reset_state() -> None:
    global _LAST_STEP
    _LAST_STEP = -1
    _RECORDS.clear()
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any = None):
    global _LAST_STEP
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return _base.agent(observation, configuration)

    farm = _m(farms[player])
    tiles = farm.get("tiles") or []
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    result = dict(_base.agent(observation, configuration))
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    money = float(farm.get("money", 0) or 0)
    health = _core._farm_health(farm)
    active_cows = len(_core._active_cows(tiles))

    q3_eligible = (
        len(unlocked) == 2
        and Q3_MIN_DAY <= day <= Q3_MAX_DAY
        and active_cows >= Q3_MIN_ACTIVE_COWS
        and money >= Q3_LAND_COST + Q3_OPERATING_RESERVE
        and int(health.get("weeds", 0) or 0) <= Q3_MAX_WEEDS
        and int(health.get("danger", 0) or 0) <= Q3_MAX_DANGER
    )

    market: List[List[Any]] = [
        list(o) for o in result.get("market", []) if isinstance(o, list) and o
    ]
    injected = False
    if q3_eligible and not any(str(o[0]).upper() == "BUY_LAND" for o in market):
        idx = 0
        while idx < len(market):
            o = market[idx]
            if (str(o[0]).upper() == "BUY_PRODUCT" and len(o) >= 2
                    and str(o[1]).upper() == "WHEAT"):
                idx += 1
                continue
            break
        market.insert(idx, ["BUY_LAND"])
        market = market[:10]
        result["market"] = market
        injected = True

    q = _quadrant_stats(tiles)
    productive = int(health.get("productive", 0) or 0)
    unlocked_tiles = int(health.get("unlocked", 0) or 0)
    animals = sum(v["animals"] for v in q.values())
    _RECORDS.append({
        "step": step, "day": day, "hour": hour, "money": money,
        "lands": len(unlocked), "hands": len(list(farm.get("hands") or [])),
        "animals": animals, "productive": productive,
        "idle": max(0, unlocked_tiles - productive),
        "q3": dict(q["SW"]), "q4": dict(q["SE"]),
        "active_cows": active_cows, "q3_eligible": q3_eligible,
        "q3_land_injected": injected,
    })
    return result
