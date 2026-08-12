"""V33.67 demand-backed herd floor.

Single economic mechanism over V33.66: keep the three-district/Q3 utilization
policy unchanged, but require a minimum 10-cow target only when recurring town
milk demand exists and there is enough season runway. V33.66's median is 73.8k
with median peak 7 animals; its stronger games usually carry 6-7 animals while
the remaining cash ceiling suggests Q3's dairy district is still under-capitalized.
The parent market-aware milk absorption and price guards remain intact.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_v28 = _p._p._p
_parent_cow_target = _v28._cow_target


def _cow_target(obs, day: int, active: int) -> int:
    target = int(_parent_cow_target(obs, day, active) or active)
    demand = int(_v28._daily_demand(obs, "MILK") or 0)
    # Town-center-only demand is too weak to justify forced biological capex.
    # Once at least one milk-consuming shop is effectively present (>=7/day),
    # maintain a 10-head commissioning target while there is enough runway for
    # first yield + multiple milk cycles. Preserve parent late-game freeze.
    if day <= 18 and demand >= 7:
        target = max(target, 10)
    return max(active, target)


# Patch only the target function referenced by V33.28's unit and allocator paths.
_v28._cow_target = _cow_target


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
