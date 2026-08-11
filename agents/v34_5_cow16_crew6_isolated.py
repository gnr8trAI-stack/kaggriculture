"""V34.5 isolated livestock-capacity experiment.

Single economic mutation on top of V34.3: keep the six-hand livestock service
crew and all V19.2 land/crop/feed/routing/market/staffing policy unchanged, but
raise the mature cow ceiling from 12 to 16.

Rationale: V34.3 was stronger than V34.4 overall and already demonstrated that
six livestock hands can activate a median ten cows with some games reaching the
12-cow ceiling. The 8-hand experiment did not materially improve economics, so
service throughput is unlikely to be the dominant constraint. This experiment
therefore isolates whether additional productive livestock capacity has positive
marginal return before changing land, crop, feed, or market policy.
"""
from __future__ import annotations
from typing import Any

from agents import v34_3_cow12_crew6_isolated as _v343

MAX_COW_TARGET = 16
CREW_COUNT = 6


def _activate() -> None:
    _v343.CREW_COUNT = CREW_COUNT
    _v343._v342._v19.MAX_COW_TARGET = MAX_COW_TARGET
    _v343._v342._v19.START_COWS_MAX_DAY = 20
    _v343._activate()
    # _v343._activate() re-applies the 12-cow base, so enforce the isolated
    # capacity mutation last while leaving every other operating parameter intact.
    _v343._v342._v19.MAX_COW_TARGET = MAX_COW_TARGET
    _v343._v342._v19.START_COWS_MAX_DAY = 20


def reset_state() -> None:
    _v343.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v343.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v343.agent(observation, configuration)


_activate()
