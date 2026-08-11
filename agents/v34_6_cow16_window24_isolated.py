"""V34.6 isolated livestock-window experiment.

Single economic mutation on top of V34.5: keep the 16-cow mature ceiling, six-hand
livestock service crew, and all V19.2 land/crop/feed/routing/market/staffing policy
unchanged, but extend the new-cow purchase/start window from day 20 through day 24.

Rationale: V34.5 materially improved reward versus V19.2 but still bought a median
12 cows, activated a median 10, never reached 16 active cows, and built a median
11 pastures. The raised capacity therefore remained unused. This experiment tests
whether the binding constraint is simply the temporal purchase gate rather than
service crew size or nominal herd capacity.
"""
from __future__ import annotations
from typing import Any

from agents import v34_5_cow16_crew6_isolated as _v345

START_COWS_MAX_DAY = 24


def _activate() -> None:
    _v345._activate()
    _v345._v343._v342._v19.START_COWS_MAX_DAY = START_COWS_MAX_DAY


def reset_state() -> None:
    _v345.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v345.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v345.agent(observation, configuration)


_activate()
