"""V33.2.1 Cow Unlock.

Single-mechanism experiment on top of V33.2:
remove the inherited V19 four-cow ceiling and the unreliable
`unlocked_quadrants` gate from livestock targeting. Land/crop/market behavior
otherwise remains V33.2/V33/V19.2.

The target ladder follows the measured public-frontier signature: once V33 has
actually expanded beyond one quadrant, build toward 8 cows, then 14 while
there is enough horizon. This module deliberately does not change land timing,
crop choice, pricing or sell policy so the economic effect is attributable.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_2_industrial_frontier as _v332

_v19 = _v332._v33._v192._v19

# The V19 service loop can already build pasture, buy, place, feed, care,
# harvest and return livestock output. Raise only its staffing/capacity ceilings.
_v19.MAX_COW_TARGET = 14
_v19.START_COWS_MAX_DAY = 24
_v19.MIN_HANDS_WITH_COWS = 8
_v19.MAX_HANDS_WITH_COWS = 14
_v19.MIN_CASH_FOR_TWO = 900
_v19.MIN_CASH_FOR_FOUR = 1400


def _frontier_cow_target(
    day: int,
    money: float,
    health: Mapping[str, Any],
    unlocked_count: int,
    cow_count: int,
    active_count: int,
) -> int:
    """Ignore unreliable unlocked_quadrants; use economic health and horizon.

    The caller is reached only from the V19 livestock controller. V33 separately
    owns the actual land expansion logic, so this function must not block growth
    merely because the observation omitted unlocked_quadrants.
    """
    if day > 24 or not _v19._growth_healthy(health):
        return cow_count
    target = cow_count
    if day >= 5 and money >= 900:
        target = max(target, 4)
    if day >= 7 and money >= 1800:
        target = max(target, 8)
    if day >= 10 and money >= 3200:
        target = max(target, 14)
    return min(14, target)


_v19._cow_target = _frontier_cow_target


def reset_state() -> None:
    _v332.reset_state()


def reset_telemetry() -> None:
    _v332.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v332.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    return _v332.agent(observation, configuration)
