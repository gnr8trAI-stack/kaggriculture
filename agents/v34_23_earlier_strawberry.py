"""V34.23 isolated earlier strawberry-timing experiment.

Single economic mutation on V34.21. Preserve its two-land dairy estate, 16-cow
ceiling/window, six-hand dairy crew, late 9/10 staffing, reserve-pasture and
activation rescue, feed/routing/market behavior and strawberry crop choice.
Only move the mature-estate strawberry specialization gate earlier:

    day >= 12, cows >= 10, cash >= 12k  ->  day >= 10, cows >= 8, cash >= 8k

Rationale: V34.21 is the strongest verified fresh-process V34 result (~69k
median) and strawberry specialization was mildly positive. Frontier replays
show ~40 strawberries during days 14-20, while V34.21 waits for a relatively
late 10-cow/12k gate. This test asks only whether earlier high-value crop
commissioning increases terminal realization without changing land, herd,
labour, service or selling policy.
"""
from __future__ import annotations
from typing import Any

from agents import v34_21_late_strawberry_specialization as _base

# The only mutation in this candidate.
_base.MIN_DAY = 10
_base.MIN_ACTIVE_COWS = 8
_base.MIN_CASH = 8000


def reset_state() -> None:
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def agent(observation: Any, configuration: Any = None):
    # Reassert after reset/import interactions; fresh-process benchmark isolates
    # candidate and controls so this cannot contaminate another module.
    _base.MIN_DAY = 10
    _base.MIN_ACTIVE_COWS = 8
    _base.MIN_CASH = 8000
    return _base.agent(observation, configuration)
