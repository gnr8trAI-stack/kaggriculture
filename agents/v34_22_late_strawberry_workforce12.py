"""V34.22 isolated late strawberry-workforce experiment.

Single economic mutation on V34.21. Preserve its two-land dairy estate, 16-cow
ceiling/window, six-hand livestock crew, reserve-pasture/activation rescue,
late strawberry crop selection, feed, routing and market policy. Only after the
same mature-estate gate used by V34.21 is reached, raise V34.13's late staffing
envelope from 9/10 to 11/12 hands.

Rationale: V34.21 is the strongest fresh 24-game result in the current V34 line
(~69.1k median, 0 invalid) and shows high-value crop mix is mildly positive, but
six dairy hands leave only four crop/utility hands at the 10-hand ceiling. The
frontier evidence sustains a much larger strawberry book. V34.11 proved that
12 hands hired at the normal livestock gate is too early; this experiment pays
for two extra crop hands only after >=10 active cows, >=12k cash and healthy
conditions, isolating late realization capacity rather than early wage drag.
"""
from __future__ import annotations
from typing import Any

from agents import v34_21_late_strawberry_specialization as _base
from agents import v34_13_late_crop_hire10_isolated as _staff

LATE_MIN_HANDS = 11
LATE_MAX_HANDS = 12
_TRIGGERED = False


def _eligible(observation: Any) -> bool:
    return bool(_base._eligible(observation))


def _activate(observation: Any = None) -> None:
    global _TRIGGERED
    # V34.13 owns the late staffing constants and applies them each step.
    # Change only that late envelope; all eligibility/crop/livestock logic stays
    # in the verified parent chain.
    if observation is not None and _eligible(observation):
        _TRIGGERED = True
        _staff.LATE_MIN_HANDS = LATE_MIN_HANDS
        _staff.LATE_MAX_HANDS = LATE_MAX_HANDS
    else:
        _staff.LATE_MIN_HANDS = 9
        _staff.LATE_MAX_HANDS = 10


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _staff.LATE_MIN_HANDS = 9
    _staff.LATE_MAX_HANDS = 10
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def workforce12_triggered() -> bool:
    return bool(_TRIGGERED)


def strawberry_triggered() -> bool:
    return _base.strawberry_triggered()


def agent(observation: Any, configuration: Any = None):
    _activate(observation)
    return _base.agent(observation, configuration)
