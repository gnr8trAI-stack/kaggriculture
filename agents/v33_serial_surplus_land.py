"""V33: V19.2 plus serial surplus-funded expansion into quadrants 3 and 4.

Single-mechanism experiment. Keep V19.2 unchanged for the first unlock and all
crop/livestock/labour logic. Once two quadrants are already unlocked, permit
additional land purchases only while substantial cash surplus and enough game
horizon remain. The purpose is to test whether V19.2's ~50k ceiling is caused by
artificially stopping after the second quadrant.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping

from agents import v19_2_early_scale8 as _v192

_RECORDS = []
_LAST_STEP = -1


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def reset_state() -> None:
    global _LAST_STEP
    _LAST_STEP = -1
    _RECORDS.clear()
    _v192.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _LAST_STEP
    obs = _v192._v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return _v192.agent(observation, configuration)

    farm = _m(farms[player])
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    money = float(farm.get("money", 0) or 0)
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    health = _v192._v19._farm_health(farm)

    # Base V19.2 owns the first expansion and all operating decisions.
    result = dict(_v192.agent(observation, configuration))
    market = [list(o) for o in result.get("market", []) if isinstance(o, list)]

    serial_expand = False
    threshold = None
    if len(unlocked) == 2:
        # Third quadrant: only from strong operating surplus, with ample horizon.
        threshold = 26000
        serial_expand = (
            13 <= day <= 20
            and money >= threshold
            and int(health.get("weeds", 0) or 0) <= 4
            and int(health.get("danger", 0) or 0) <= 2
        )
    elif len(unlocked) == 3:
        # Fourth quadrant: require an even larger surplus so prior districts are
        # already self-funding before the final scale step.
        threshold = 36000
        serial_expand = (
            15 <= day <= 22
            and money >= threshold
            and int(health.get("weeds", 0) or 0) <= 5
            and int(health.get("danger", 0) or 0) <= 2
        )

    if serial_expand and not any(o[:1] == ["BUY_LAND"] for o in market):
        market = [["BUY_LAND"]] + market
        market = market[:10]
        result["market"] = market

    _RECORDS.append({
        "step": step,
        "day": day,
        "hour": hour,
        "money": money,
        "unlocked_count": len(unlocked),
        "serial_expand": serial_expand,
        "serial_threshold": threshold,
        "health": dict(health),
    })
    return result
