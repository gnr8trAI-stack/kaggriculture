"""V34.3 isolated livestock-service throughput experiment.

Single economic mutation on top of V34.2: keep the 12-cow mature ceiling and
all V19.2 land/crop/feed/routing/market/staffing policy unchanged, but increase
the dedicated livestock service crew from four hands to six.

Rationale: V34.2 bought a median 12 cows but activated only a median 7 (max 8),
while V34.1's four-hand crew fully activated its eight-cow ceiling. The next
binding constraint is therefore service/placement throughput rather than cow
purchase capacity. This experiment changes only service crew size.
"""
from __future__ import annotations
from typing import Any

from agents import v34_2_cow12_crew4_isolated as _v342

CREW_COUNT = 6


def _activate() -> None:
    _v342.CREW_COUNT = CREW_COUNT
    _v342._activate()


def reset_state() -> None:
    _v342.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v342.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v342.agent(observation, configuration)


_activate()
