"""V34.0 isolated livestock-scale experiment.

Single economic mutation on top of V19.2: raise the proven 2->4 cow ladder to
4->8 cows while keeping V19.2 land, crop, routing, market-order and feed logic
otherwise unchanged. This isolates whether additional milk capacity can lift the
~50k V19.2 ceiling before changing land or cultivation policy.
"""
from __future__ import annotations
from typing import Any

from agents import v19_2_early_scale8 as _v192

_v19 = _v192._v19


def _activate() -> None:
    # Preserve the V19.2 operating policy; mutate only livestock scale.
    _v19.INITIAL_COW_TARGET = 4
    _v19.MAX_COW_TARGET = 8
    _v19.START_COWS_MAX_DAY = 19
    # Supporting headcount is part of livestock capacity, but no land/crop gate
    # or routing policy is changed in this experiment.
    _v19.MIN_HANDS_WITH_COWS = 8
    _v19.MAX_HANDS_WITH_COWS = 10
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
