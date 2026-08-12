"""V34.27 isolated strawberry-funded third-land experiment.

Single economic mutation on V34.26. Preserve its verified V34.23 dairy estate,
early strawberry specialization, six-hand dairy service, staffing, feed,
routing, reserve-pasture/activation rescue and terminal liquidation. Add exactly
one third-land purchase only after the two-land estate is fully commissioned:
12 active cows, 12 pastures, healthy farm, day 14-17 and >=18k cash.

Rationale: V34.19 showed that late acreage by itself was negative before the
strawberry specialization existed. V34.23 subsequently established a positive
high-value crop signal, and V34.26 adds reliable terminal realization. This test
isolates whether the same one-land expansion now pays when newly opened slots
inherit the proven strawberry chooser, without adding workers, animals, feed or
special Q3 scheduling.
"""
from __future__ import annotations
from typing import Any, Dict, List

from agents import v34_26_terminal_liquidation as _base

_TRIGGERED = False


def _v19():
    # V34.26 -> V34.23 -> V34.21; V34.21 exposes its V19 module as _v19.
    return _base._base._base._v19


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def terminal_liquidation_triggered() -> bool:
    return bool(_base.terminal_liquidation_triggered())


def third_land_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _TRIGGERED
    result = dict(_base.agent(observation, configuration))
    v19 = _v19()
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = v19._m(farms[player])
    tiles = farm.get("tiles") or []
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    if len(unlocked) != 2:
        return result

    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    active = len(v19._active_cows(tiles))
    pastures = len(v19._pastures(tiles))
    health = v19._farm_health(farm)
    eligible = (
        14 <= day <= 17
        and active >= 12
        and pastures >= 12
        and money >= 18000
        and float(health.get("weed_ratio", 0.0) or 0.0) <= 0.15
        and int(health.get("danger", 0) or 0) <= 1
    )
    if not eligible:
        return result

    market: List[List[Any]] = [
        list(o) for o in result.get("market", [])
        if isinstance(o, list) and o
    ]
    if any(str(o[0]).upper() == "BUY_LAND" for o in market):
        _TRIGGERED = True
        return result

    # Preserve feed survival ahead of capex, then commission the third quadrant.
    insert_at = 0
    while insert_at < len(market):
        o = market[insert_at]
        if (str(o[0]).upper() == "BUY_PRODUCT" and len(o) >= 2
                and str(o[1]).upper() == "WHEAT"):
            insert_at += 1
        else:
            break
    market.insert(insert_at, ["BUY_LAND"])
    result["market"] = market[:10]
    _TRIGGERED = True
    return result
