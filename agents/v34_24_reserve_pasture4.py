"""V34.24 isolated reserve-pasture-depth experiment.

Single economic mutation on V34.23. Preserve its two-land policy, 16-cow
ceiling/window, six-hand dairy crew, staffing, activation rescue, crop/feed/
routing/market behavior, and strawberry specialization. Change only late spare
pasture capacity from two reserves to four.

Economic rationale: V34.23 reaches a median 12 active cows while the inherited
herd ceiling remains 16. Late third-land experiments regressed, so the cheapest
way to test whether the remaining four purchased/target cows can become
productive is to create four additional pasture slots inside the already-owned
two-land estate. No extra cows, land, feed, labour, or crop policy are added.
"""
from __future__ import annotations
from typing import Any

from agents import v34_23_earlier_strawberry as _base

# Single mutation: allow four reserve pasture slots rather than the parent's two.
_RESERVE_MODULE = _base._base._base


def _activate() -> None:
    _RESERVE_MODULE.RESERVE_PASTURES = 4


def reset_state() -> None:
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def agent(observation: Any, configuration: Any = None):
    # Reassert after reset/import interactions. Benchmarks run each agent/game in
    # a fresh subprocess so this mutation cannot contaminate controls.
    _activate()
    return _base.agent(observation, configuration)


_activate()
