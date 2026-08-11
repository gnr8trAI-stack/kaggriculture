"""V34.15 isolated late feed-buffer experiment.

Single economic mutation on top of verified V34.13: retain the 16-cow ceiling,
day-24 livestock window, six-hand livestock crew, two-land/crop/routing policy,
and late 9/10 staffing trigger. Once the dairy estate is already commissioned
(day >=16, >=10 active cows, cash >=18000, healthy farm), raise only the shed
wheat reserve from 2 to 3 units per active cow.

Rationale: V34.13 is the strongest robust two-land candidate so far (median ~71k).
It operates around 10 active cows and 11 pastures. A larger late feed reserve is
an isolated test of whether milk/care throughput is being clipped by feed
availability after herd commissioning, without changing land, herd capacity,
crew allocation or wages.
"""
from __future__ import annotations
from typing import Any

from agents import v34_13_late_crop_hire10_isolated as _v3413

BASE_FEED_BUFFER_PER_COW = 2
LATE_FEED_BUFFER_PER_COW = 3
LATE_MIN_DAY = 16
LATE_MIN_ACTIVE_COWS = 10
LATE_MIN_CASH = 18000
MAX_LATE_WEED_RATIO = 0.18
MAX_LATE_DANGER = 2

_LATE_FEED_TRIGGERED = False


def _v19():
    return _v3413._v19()


def _late_feed_ready(observation: Any) -> bool:
    v19 = _v19()
    obs = v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if day < LATE_MIN_DAY or not isinstance(farms, list) or player >= len(farms):
        return False
    farm = v19._m(farms[player])
    active = len(v19._active_cows(farm.get("tiles") or []))
    money = float(farm.get("money", 0) or 0)
    health = v19._farm_health(farm)
    return (
        active >= LATE_MIN_ACTIVE_COWS
        and money >= LATE_MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_LATE_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_LATE_DANGER
    )


def _activate(observation: Any = None) -> None:
    global _LATE_FEED_TRIGGERED
    _v3413._activate(observation)
    v19 = _v19()
    if observation is not None and _late_feed_ready(observation):
        _LATE_FEED_TRIGGERED = True
        v19.FEED_BUFFER_PER_COW = LATE_FEED_BUFFER_PER_COW
    else:
        v19.FEED_BUFFER_PER_COW = BASE_FEED_BUFFER_PER_COW


def reset_state() -> None:
    global _LATE_FEED_TRIGGERED
    _LATE_FEED_TRIGGERED = False
    _v3413.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v3413.get_telemetry(clear=clear)


def late_hire_triggered() -> bool:
    return _v3413.late_hire_triggered()


def late_feed_triggered() -> bool:
    return bool(_LATE_FEED_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    _activate(observation)
    return _v3413.agent(observation, configuration)


_activate()
