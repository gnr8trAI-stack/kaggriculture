"""V34.25 isolated strawberry cash-floor experiment.

Single economic mutation on V34.23. Preserve its two-land dairy estate, herd,
six-hand dairy service, late staffing, reserve-pasture/activation rescue,
feed/routing/market logic and early strawberry specialization. Change only the
crop-selection guard for *new* strawberry slots: once the estate reaches the
middle/late game, strawberry specialization remains active only while cash is
on a healthy trajectory. If cash falls below the day-band floor, new crop slots
fall back to V34.23's inherited adaptive crop chooser.

Rationale: V34.24 proved extra pasture depth is behaviorally neutral, while the
V34.23 low-tail games still reached 12 active cows and strawberry mode but had
cash around 26-27k at day 20 and only 29-33k at day 25. This tests whether
avoiding additional long-cycle strawberry commitments during a cash drawdown
improves terminal realization without changing land, animals, labour, feed,
routing, existing crops, harvest, or selling behavior.
"""
from __future__ import annotations
from typing import Any

from agents import v34_23_earlier_strawberry as _base

_strawberry = _base._base  # agents.v34_21_late_strawberry_specialization
_ORIGINAL_ELIGIBLE = _strawberry._eligible
_GUARD_FALLBACK = False


def _cash_floor(day: int) -> float:
    if day <= 15:
        return 0.0
    if day <= 18:
        return 18000.0
    if day <= 21:
        return 28000.0
    return 40000.0


def _guarded_eligible(observation: Any) -> bool:
    global _GUARD_FALLBACK
    if not _ORIGINAL_ELIGIBLE(observation):
        return False
    v19 = _strawberry._v19
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return False
    farm = v19._m(farms[player])
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    floor = _cash_floor(day)
    if floor and money < floor:
        _GUARD_FALLBACK = True
        return False
    return True


def _activate() -> None:
    _strawberry._eligible = _guarded_eligible


def reset_state() -> None:
    global _GUARD_FALLBACK
    _GUARD_FALLBACK = False
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def cash_guard_fallback_triggered() -> bool:
    return bool(_GUARD_FALLBACK)


def agent(observation: Any, configuration: Any = None):
    # V34.23 reasserts its timing thresholds on every call. Reassert only this
    # candidate's eligibility guard afterward/around delegation; no other base
    # state or policy is changed.
    _activate()
    try:
        return _base.agent(observation, configuration)
    finally:
        _activate()


_activate()
