"""V33.75 milk-supported herd floor.

Single mechanism over verified V33.66: when three districts are already open and
milk economics remain healthy, raise only the Q3 cow target floor from the
observed ~6-active regime to 8. Land, labour roles, crop policy, feed reserve,
market pacing, Q4 suppression, and Q3 commissioning gates remain V33.66.

Rationale: V33.66 is the current robust parent (~76k median) but peaks at only
6 animals while retaining material Q3 idle capacity. Earlier isolated livestock
experiments showed that moving from 4 to 8 serviced cows improved terminal
reward, so this tests whether the current three-district architecture can turn
that spare Q3 capacity into additional recurring milk cash without adding land.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_v28 = _p._p._p
_parent_cow_target = _v28._cow_target
_b = _v28._b


def _cow_target(obs, day: int, active: int) -> int:
    target = int(_parent_cow_target(obs, day, active) or active)
    # Preserve the parent's demand/price logic; add only a conservative floor
    # while there is enough production runway and milk is not deeply glutted.
    if day <= 20:
        price = float(_b._prices(obs).get("MILK", 160) or 160)
        demand = int(_v28._daily_demand(obs, "MILK") or 0)
        if price >= 120 and demand >= 7:
            target = max(target, 8)
    return max(active, min(16, target))


_v28._cow_target = _cow_target


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
