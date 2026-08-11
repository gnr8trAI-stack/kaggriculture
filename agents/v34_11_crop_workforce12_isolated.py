"""V34.11 isolated protected crop-workforce experiment.

Single economic mutation on top of verified V34.6: keep the 16-cow ceiling,
day-24 livestock purchase window, six-hand livestock service crew, two-land
policy, crop/feed/routing logic and cow economics unchanged, but raise total
hired-hand staffing from V19.2's 7-target/8-ceiling to 11-target/12-ceiling.

Economic rationale: V34.4 showed that assigning more existing hands to livestock
weakens the tail. V34.6 already consumes six late-index hands for livestock,
leaving too little crop capacity. Labour has been measured as cheap in the live
environment, so this experiment adds crop/utility throughput without enlarging
the livestock crew or changing any other capital decision.
"""
from __future__ import annotations
from typing import Any

from agents import v34_6_cow16_window24_isolated as _v346

MIN_HANDS_WITH_COWS = 11
MAX_HANDS_WITH_COWS = 12


def _activate() -> None:
    _v346._activate()
    v19 = _v346._v345._v343._v342._v19
    v19.MIN_HANDS_WITH_COWS = MIN_HANDS_WITH_COWS
    v19.MAX_HANDS_WITH_COWS = MAX_HANDS_WITH_COWS


def reset_state() -> None:
    _v346.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v346.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v346.agent(observation, configuration)


_activate()
