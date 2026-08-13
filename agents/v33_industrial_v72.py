"""V33.72 Q3 feed-strip parallelism.

Single economic mechanism over V33.66: once Q3 is commissioned and the existing
livestock service crew is intact, reassign one already-paid Q1/Q2 crop worker to
the Q3 feed/crop role.  No new labour, land, animal, seed, market, sale or Q4
policy is introduced.

Rationale: V33.66 is the strongest independent V33 parent (~74k median) but its
three-land estate still carries substantial uncommissioned capacity. V33.70 and
V33.71 proved that Q1/Q2 workers never reach cross-district/early-commissioning
fallbacks. The parent already buys Q3 wheat seed and has a dedicated feed-strip
role; this experiment adds exactly one parallel Q3 crop operator without taking
a livestock-service slot or increasing recurring Fibonacci labour cost.
"""
from __future__ import annotations
from typing import Any, List
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_roles = _v28._roles


def _roles(lands: int, hand_count: int) -> List[str]:
    roles = list(_parent_roles(lands, hand_count))
    if lands < 3 or hand_count < 11:
        return roles

    # Preserve every livestock specialist and the existing feed worker. Move only
    # one crop worker, preferring Q2 so Q1's bootstrap/realization engine remains
    # untouched. This changes labour allocation, not labour quantity.
    for preferred in ("q2", "q1"):
        for i in range(1, len(roles)):
            if roles[i] == preferred:
                roles[i] = "feed"
                return roles
    return roles


# Patch the exact role global used by V33.28's agent path.
_v28._roles = _roles


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
