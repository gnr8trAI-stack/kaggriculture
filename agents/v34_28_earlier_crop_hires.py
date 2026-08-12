"""V34.28 isolated earlier late-crop-hire timing experiment.

Single economic mutation on verified V34.26: preserve its two-land dairy estate,
16-cow ceiling/window, six-hand livestock service, reserve-pasture/activation
rescue, early strawberry specialization, feed/routing/market behavior and
terminal liquidation. Keep the proven V34.13 late staffing target at 9/10 hands,
its >=10 active-cow, >=18k cash and health gates unchanged; only move the
minimum day for those already-funded extra crop/utility hires from day 16 to 14.

Rationale: V34.26/V34.27 peak at only ~30 productive tiles across two unlocked
quadrants while the dairy estate is already mature. V34.13 established that
9/10 late staffing is robust, whereas 11/12 staffing and reducing the six-hand
dairy crew regressed. This isolates whether the same proven two extra crop hands
arrive too late to compound strawberry/crop throughput.
"""
from __future__ import annotations
from typing import Any

from agents import v34_26_terminal_liquidation as _base

# V34.26 -> V34.23 -> V34.21 -> V34.17 -> V34.16 -> V34.13
_late = _base._base._base._base._base._base
ORIGINAL_LATE_MIN_DAY = 16
CANDIDATE_LATE_MIN_DAY = 14


def _activate() -> None:
    # This is the only candidate mutation. Fresh-process benchmarking keeps the
    # candidate isolated from V34.26 and V19.2 controls.
    _late.LATE_MIN_DAY = CANDIDATE_LATE_MIN_DAY


def reset_state() -> None:
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def earlier_hire_triggered() -> bool:
    return bool(_late.late_hire_triggered())


def terminal_liquidation_triggered() -> bool:
    return bool(_base.terminal_liquidation_triggered())


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _base.agent(observation, configuration)


_activate()
