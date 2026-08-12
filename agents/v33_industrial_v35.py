"""V33.35 synchronized melon-batch industrial engine.

Independent V33 architecture, extending V33.34's herd-first capital allocator.
The key economic correction comes from official mechanics plus V33.32 replay
experiments: a watered melon occupies a tile for ten days, yields six units,
and a single SELL order is realized at its pre-impact quote.  V33.28's crop
allocator excluded MELON after bootstrap, so it built 60+ productive tiles but
filled most crop districts with much lower gross-value staples.  V33.35 uses
Q1/Q2/Q4 as synchronized melon factories while ten-day payback remains, keeps
Q3 as feed/livestock, and falls back to short-cycle wheat late enough to fully
liquidate before season end.

V19.2 is not imported and remains benchmark control only.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v34 as _v34

_v28 = _v34._v28
_b = _v34._b


def _industrial_crop_for(day: int, district: int, obs) -> str:
    # Q3 is the feed district.  All crop districts exploit melon's 6*250 gross
    # per ten-day tile cycle while enough horizon remains for harvest + sale.
    if district == 3:
        return "WHEAT"
    if day <= 18:
        return "MELON"
    # Wheat has a short first-yield horizon and is the safest final-cycle sink.
    return "WHEAT"


_v28._crop_for = _industrial_crop_for


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
