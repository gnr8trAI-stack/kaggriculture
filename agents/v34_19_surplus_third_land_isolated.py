"""V34.19 isolated late surplus-funded third-land experiment.

Single economic mutation on verified V34.17: preserve its two-land dairy engine,
12-active-cow rescue, staffing, crop/feed/routing, and livestock service policy.
Only after the dairy estate is fully commissioned (>=12 active cows and >=12
pastures) and strongly cash-surplus funded does the market buy exactly one third
land. No Q4 logic and no special Q3 worker/crop/livestock policy is added here.

Rationale: the earlier V34.9 third-land test bought acreage as soon as 10 cows
were active and reduced median reward, consistent with premature capex. V34.17
now reliably reaches a 12-cow fully active estate. This isolates whether acreage
itself has positive marginal value when purchased from mature surplus rather
than during herd build-out.
"""
from __future__ import annotations
from typing import Any, List, Mapping

from agents import v34_17_late_cow_activation_rescue as _base

MIN_DAY = 18
MAX_DAY = 22
MIN_ACTIVE_COWS = 12
MIN_PASTURES = 12
MIN_CASH = 30000.0
MAX_WEED_RATIO = 0.15
MAX_DANGER = 1

_TRIGGERED = False


def _v19():
    return _base._v19()


def _land_count(tiles: Any) -> int:
    v19 = _v19()
    if not isinstance(tiles, list) or not tiles:
        return 0
    n = len(tiles); h = n // 2; count = 0
    for x0, x1, y0, y1 in ((0,h,0,h),(h,n,0,h),(0,h,h,n),(h,n,h,n)):
        unlocked = False
        for y in range(y0, min(y1, len(tiles))):
            row = tiles[y] if isinstance(tiles[y], list) else []
            for x in range(x0, min(x1, len(row))):
                if v19._kind(row[x]) != "LOCKED":
                    unlocked = True; break
            if unlocked: break
        count += int(unlocked)
    return count


def _eligible(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> bool:
    v19 = _v19(); tiles = farm.get("tiles") or []
    day = int(obs.get("day", 0) or 0); money = float(farm.get("money", 0) or 0)
    if not (MIN_DAY <= day <= MAX_DAY) or money < MIN_CASH or _land_count(tiles) != 2:
        return False
    health = v19._farm_health(farm)
    return (
        len(v19._active_cows(tiles)) >= MIN_ACTIVE_COWS
        and len(v19._pastures(tiles)) >= MIN_PASTURES
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_DANGER
    )


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def third_land_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    global _TRIGGERED
    result = dict(_base.agent(observation, configuration))
    v19 = _v19(); obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0); farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = v19._m(farms[player])
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
    _TRIGGERED = True
    return result
