"""V34.14 isolated late second-wave staffing experiment.

Single economic mutation on top of V34.13: retain V34.13's dairy estate,
late 9/10 staffing trigger, land/crop/feed/routing policy, cow ceiling/window,
and six-hand livestock service crew. Add only a second late staffing step to
11/12 hands after the estate is mature and strongly cash-surplus funded.

Rationale: V34.13 improved median reward to ~71k with 31/32 paired wins while
avoiding the tail damage seen when 11-12 hands were hired during herd build-out.
This tests whether two more crop/utility hands are profitable only after the
herd is already commissioned and cash has compounded, limiting wage exposure.
"""
from __future__ import annotations
from typing import Any

from agents import v34_13_late_crop_hire10_isolated as _v3413

SECOND_MIN_HANDS = 11
SECOND_MAX_HANDS = 12
SECOND_MIN_DAY = 20
SECOND_MIN_ACTIVE_COWS = 10
SECOND_MIN_CASH = 30000
MAX_SECOND_WEED_RATIO = 0.15
MAX_SECOND_DANGER = 1

_SECOND_TRIGGERED = False


def _v19():
    return _v3413._v19()


def _second_wave_ready(observation: Any) -> bool:
    v19 = _v19()
    obs = v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if day < SECOND_MIN_DAY or not isinstance(farms, list) or player >= len(farms):
        return False
    farm = v19._m(farms[player])
    money = float(farm.get("money", 0) or 0)
    active = len(v19._active_cows(farm.get("tiles") or []))
    health = v19._farm_health(farm)
    return (
        active >= SECOND_MIN_ACTIVE_COWS
        and money >= SECOND_MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_SECOND_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_SECOND_DANGER
    )


def _activate(observation: Any = None) -> None:
    global _SECOND_TRIGGERED
    _v3413._activate(observation)
    v19 = _v19()
    if observation is not None and _second_wave_ready(observation):
        _SECOND_TRIGGERED = True
        v19.MIN_HANDS_WITH_COWS = SECOND_MIN_HANDS
        v19.MAX_HANDS_WITH_COWS = SECOND_MAX_HANDS


def reset_state() -> None:
    global _SECOND_TRIGGERED
    _SECOND_TRIGGERED = False
    _v3413.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v3413.get_telemetry(clear=clear)


def late_hire_triggered() -> bool:
    return _v3413.late_hire_triggered()


def second_wave_triggered() -> bool:
    return bool(_SECOND_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    _activate(observation)
    return _v3413.agent(observation, configuration)


_activate()
