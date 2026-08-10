"""V32.3: minimal V19.2-plus challenger.

Preserves V19.2's live-proven cash engine and changes only late, surplus-funded
livestock scaling. No new land logic, no new crop planner, no reserve rewrite.
"""
from __future__ import annotations
from typing import Any, Mapping

from agents import v19_2_early_scale8 as _v192

_v19 = _v192._v19
_BASE_COW_TARGET = _v19._cow_target


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _cow_target_v323(day: int, money: float, health: Mapping[str, Any], unlocked_count: int,
                     cow_count: int, active_count: int) -> int:
    """Keep V19.2's 2->4 curve; permit 5->6 only from genuine surplus."""
    base = _BASE_COW_TARGET(day, money, health, unlocked_count, cow_count, active_count)
    if unlocked_count < 2 or day < 12 or day > 21:
        return base
    if not _v19._growth_healthy(health):
        return base
    # First incremental cow requires a clear surplus beyond V19.2's operating range.
    target = base
    if active_count >= 4 and money >= 6500:
        target = max(target, 5)
    # Sixth cow only after the fifth is actually active and cash has rebuilt.
    if active_count >= 5 and money >= 9000:
        target = max(target, 6)
    return min(6, target)


def _activate() -> None:
    # Reassert V19.2's known-good scale constants because sibling imports can mutate globals.
    _v19.EXPAND_MIN_DAY = 8
    _v19.EXPAND_MAX_DAY = 18
    _v19.MIN_PEAK_NW_PRODUCTIVE = 18
    _v19.MIN_CASH_TO_EXPAND = 3000
    _v19.FORCE_ADAPTIVE_DAY = 16
    _v19.MIN_HANDS_WITH_COWS = 7
    _v19.MAX_HANDS_WITH_COWS = 8
    _v19._inject_market_orders = _v192._inject_market_orders
    _v19._cow_target = _cow_target_v323


def reset_state() -> None:
    _v192.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool=False):
    return _v192.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any=None):
    _activate()
    return _v19.agent(observation, configuration)


_activate()
