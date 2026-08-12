"""V34.21 isolated late strawberry-specialization experiment.

Single economic mutation on verified V34.17. Preserve the 16-cow ceiling/window,
six-hand dairy crew, late 9/10 staffing, reserve-pasture and activation rescue,
two-land policy, feed, routing, market and labour logic. Change only the crop
selection signal after the dairy estate is already commissioned: from day 12,
when >=10 cows are active and the farm is healthy/cash-funded, new crop slots
prefer STRAWBERRY instead of the base adaptive chooser.

Economic rationale: V34.17/V34.20 plateau around 68k median terminal cash despite
12 active cows and >50k median cash by day 25. Public 175k-192k frontier replays
show a sustained ~40-strawberry crop book from roughly days 14-20. This test
isolates whether high-value crop mix, rather than more pasture/land, is the next
binding profit mechanism. Existing crops are not destroyed and all scheduling,
watering, harvest, feed, staffing and market rules remain unchanged.
"""
from __future__ import annotations
from typing import Any

from agents import v34_17_late_cow_activation_rescue as _base

MIN_DAY = 12
MIN_ACTIVE_COWS = 10
MIN_CASH = 12000
MAX_WEED_RATIO = 0.15
MAX_DANGER = 1

_TRIGGERED = False
_v19 = _base._v19()
_v12 = _v19._v15._v12_agent
_v12g = _v12.__globals__
_ORIGINAL_CHOOSE_CROP = _v12g.get("choose_crop")
_CURRENT_OBS = None


def _eligible(observation: Any) -> bool:
    if observation is None:
        return False
    obs = _v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return False
    farm = _v19._m(farms[player])
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    active = len(_v19._active_cows(farm.get("tiles") or []))
    health = _v19._farm_health(farm)
    return (
        day >= MIN_DAY
        and active >= MIN_ACTIVE_COWS
        and money >= MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_DANGER
    )


def _choose_crop(obs, farm):
    global _TRIGGERED
    observation = _CURRENT_OBS if _CURRENT_OBS is not None else obs
    if _eligible(observation):
        _TRIGGERED = True
        return "STRAWBERRY", {"STRAWBERRY": 1.0}
    if callable(_ORIGINAL_CHOOSE_CROP):
        return _ORIGINAL_CHOOSE_CROP(obs, farm)
    return None, {}


def _activate() -> None:
    _v12g["choose_crop"] = _choose_crop


def reset_state() -> None:
    global _TRIGGERED, _CURRENT_OBS
    _TRIGGERED = False
    _CURRENT_OBS = None
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    global _CURRENT_OBS
    _CURRENT_OBS = observation
    _activate()
    try:
        return _base.agent(observation, configuration)
    finally:
        _CURRENT_OBS = None


_activate()
