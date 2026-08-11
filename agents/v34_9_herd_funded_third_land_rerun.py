"""V34.9 repaired isolated herd-funded third-land experiment.

Single economic mechanism on top of the verified V34.6 lineage: once the two-land
dairy estate is actually saturated (>=10 active cows and >=10 pastures), reinvest
surplus cash into exactly one third land purchase while enough runway remains to
commission it. Herd ceiling, six-hand livestock crew, crop/feed/routing logic,
and livestock purchase window remain V34.6 unchanged.

This is the dependency-correct rerun of the unexecuted V34.8 mechanism. V34.8's
benchmark was invalid in all games because its branch omitted the V34.6 dependency;
no economic conclusion is drawn from that failed run.
"""
from __future__ import annotations
from typing import Any, List, Mapping

from agents import v34_6_cow16_window24_isolated as _v346

_v19 = _v346._v345._v343._v342._v19
_BASE = _v346.agent

THIRD_LAND_MIN_DAY = 10
THIRD_LAND_MAX_DAY = 19
THIRD_LAND_MIN_ACTIVE_COWS = 10
THIRD_LAND_MIN_PASTURES = 10
THIRD_LAND_MIN_CASH = 5200.0


def _land_count(tiles: Any) -> int:
    if not isinstance(tiles, list) or not tiles:
        return 0
    n = len(tiles)
    h = n // 2
    count = 0
    for x0, x1, y0, y1 in ((0,h,0,h),(h,n,0,h),(0,h,h,n),(h,n,h,n)):
        unlocked = False
        for y in range(y0, min(y1, len(tiles))):
            row = tiles[y] if isinstance(tiles[y], list) else []
            for x in range(x0, min(x1, len(row))):
                if _v19._kind(row[x]) != "LOCKED":
                    unlocked = True
                    break
            if unlocked:
                break
        count += int(unlocked)
    return count


def _eligible(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> bool:
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    tiles = farm.get("tiles") or []
    if not (THIRD_LAND_MIN_DAY <= day <= THIRD_LAND_MAX_DAY):
        return False
    if money < THIRD_LAND_MIN_CASH or _land_count(tiles) != 2:
        return False
    health = _v19._farm_health(farm)
    if float(health.get("weed_ratio", 0.0) or 0.0) > 0.18:
        return False
    if int(health.get("danger", 0) or 0) > 2:
        return False
    if len(_v19._active_cows(tiles)) < THIRD_LAND_MIN_ACTIVE_COWS:
        return False
    if len(_v19._pastures(tiles)) < THIRD_LAND_MIN_PASTURES:
        return False
    return True


def reset_state() -> None:
    _v346.reset_state()


def reset_telemetry() -> None:
    _v346.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v346.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    result = dict(_BASE(observation, configuration))
    obs = _v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = _v19._m(farms[player])
    if not _eligible(obs, farm):
        return result

    market: List[List[Any]] = []
    already_land = False
    for raw in result.get("market", []) or []:
        if not isinstance(raw, list) or not raw:
            continue
        op = str(raw[0]).upper()
        if op == "BUY_LAND":
            if already_land:
                continue
            already_land = True
        market.append(list(raw))
    if not already_land:
        market.insert(0, ["BUY_LAND"])
    result["market"] = market[:10]
    return result
