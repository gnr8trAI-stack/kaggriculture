"""V34.4 isolated livestock-service throughput experiment.

Single economic mutation on top of V34.3: keep the 12-cow mature ceiling and
all V19.2 land/crop/feed/routing/market/staffing policy unchanged, but increase
the dedicated livestock service crew from six hands to eight.

Rationale: V34.3 reached median peak cow count 12 and median active cows 10,
with some games reaching 12 active cows. This suggests remaining upside is in
placement/feed/care/harvest throughput. This experiment changes only service
crew size to test whether fuller activation lifts terminal wealth without
changing cow capacity or any market/land/crop economics.
"""
from __future__ import annotations
from typing import Any

from agents import v34_3_cow12_crew6_isolated as _v343

CREW_COUNT = 8


def _activate() -> None:
    _v343.CREW_COUNT = CREW_COUNT
    _v343._activate()


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
