"""V32.4: V19.2 plus one late surplus-funded land unlock.

Single-mechanism experiment: preserve V19.2's crop, livestock, feed, labour and
market logic, but remove the historical NW-productive saturation gate that
prevented the second quadrant from ever being purchased in isolated tests.
Expansion is deliberately late and cash-rich so the $1,000 land purchase cannot
starve the proven V19.2 operating engine.
"""
from __future__ import annotations
from typing import Any

from agents import v19_2_early_scale8 as _v192

_v19 = _v192._v19


def _activate() -> None:
    # Preserve every V19.2 behaviour except the first-land gate.
    _v19.EXPAND_MIN_DAY = 12
    _v19.EXPAND_MAX_DAY = 22
    _v19.MIN_PEAK_NW_PRODUCTIVE = 0
    _v19.MIN_CASH_TO_EXPAND = 20000
    _v19.FORCE_ADAPTIVE_DAY = 16
    _v19.MIN_HANDS_WITH_COWS = 7
    _v19.MAX_HANDS_WITH_COWS = 8
    _v19._inject_market_orders = _v192._inject_market_orders


def reset_state() -> None:
    _v192.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v192.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v19.agent(observation, configuration)


_activate()
