"""V34.13 isolated late crop-workforce experiment.

Single economic mutation on top of verified V34.6: retain the 16-cow ceiling,
day-24 livestock window, six-hand livestock crew, two-land policy, crop/feed/
routing logic and all early staffing unchanged. Only after the dairy estate is
already commissioned (>=10 active cows) and strongly cash-funded does the hired-
hand target rise from V19.2's 7/8 envelope to 9/10.

Rationale: V34.11 showed that hiring 11-12 hands from the normal livestock gate
hurts the tail, while V34.12 showed that taking already-paid hands away from the
six-hand dairy crew collapses some games. This isolates the remaining hypothesis:
add only two crop/utility hands, and only after the herd is productive enough to
fund them, so Q1 can retain throughput without weakening dairy service or paying
extra wages during commissioning.
"""
from __future__ import annotations
from typing import Any

from agents import v34_6_cow16_window24_isolated as _v346

BASE_MIN_HANDS = 7
BASE_MAX_HANDS = 8
LATE_MIN_HANDS = 9
LATE_MAX_HANDS = 10
LATE_MIN_DAY = 16
LATE_MIN_ACTIVE_COWS = 10
LATE_MIN_CASH = 18000
MAX_LATE_WEED_RATIO = 0.18
MAX_LATE_DANGER = 2

_LATE_TRIGGERED = False


def _v19():
    return _v346._v345._v343._v342._v19


def _late_crop_hires_ready(observation: Any) -> bool:
    v19 = _v19()
    obs = v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if day < LATE_MIN_DAY or not isinstance(farms, list) or player >= len(farms):
        return False
    farm = v19._m(farms[player])
    money = float(farm.get("money", 0) or 0)
    active = len(v19._active_cows(farm.get("tiles") or []))
    health = v19._farm_health(farm)
    return (
        active >= LATE_MIN_ACTIVE_COWS
        and money >= LATE_MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_LATE_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_LATE_DANGER
    )


def _activate(observation: Any = None) -> None:
    global _LATE_TRIGGERED
    _v346._activate()
    v19 = _v19()
    if observation is not None and _late_crop_hires_ready(observation):
        _LATE_TRIGGERED = True
        v19.MIN_HANDS_WITH_COWS = LATE_MIN_HANDS
        v19.MAX_HANDS_WITH_COWS = LATE_MAX_HANDS
    else:
        v19.MIN_HANDS_WITH_COWS = BASE_MIN_HANDS
        v19.MAX_HANDS_WITH_COWS = BASE_MAX_HANDS


def reset_state() -> None:
    global _LATE_TRIGGERED
    _LATE_TRIGGERED = False
    _v346.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v346.get_telemetry(clear=clear)


def late_hire_triggered() -> bool:
    return bool(_LATE_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    _activate(observation)
    return _v346.agent(observation, configuration)


_activate()
