"""V34.20 isolated earlier reserve-pasture gate.

Single economic mutation on verified V34.17: preserve the 16-cow ceiling/window,
six-hand dairy crew, late 9/10 staffing, two-land policy, activation rescue,
crop/feed/routing and all market logic. Change only the V34.16 reserve-pasture
activation threshold from >=10 active cows to >=8 active cows. Day/cash/health
gates and the two-pasture forward buffer remain unchanged.

Rationale: V34.17 reliably reaches 12 active cows but the pipeline commissions
new pasture capacity only after ten cows are already active. Since animal buys
are restricted to already-built empty pastures, late structure creation can be
the pacing item. This test advances only that capacity signal without adding
land, workers, animals, feed, or changing service priorities.
"""
from __future__ import annotations
from typing import Any

from agents import v34_17_late_cow_activation_rescue as _base

RESERVE_MIN_ACTIVE_COWS = 8


def _activate() -> None:
    _base._base.MIN_ACTIVE_COWS = RESERVE_MIN_ACTIVE_COWS


def reset_state() -> None:
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def reserve8_triggered() -> bool:
    return bool(_base._base.reserve_pasture_triggered())


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _base.agent(observation, configuration)


_activate()
