"""V33.74 Q3 commissioning worker isolation.

Single mechanism over verified V33.66: after the third district opens, reassign
one existing Q1/Q2 crop worker to the Q3 feed/crop role. No land, staffing,
animal, feed-purchase, crop-selection, routing, or market-policy changes.
"""
from __future__ import annotations
from typing import Any, List
from agents import v33_industrial_v66 as _p

_b = _p._b
_parent_roles = _b._roles


def _roles(lands: int, hand_count: int) -> List[str]:
    roles = list(_parent_roles(lands, hand_count))
    if lands >= 3:
        for preferred in ("q2", "q1"):
            for i in range(1, len(roles)):
                if roles[i] == preferred:
                    roles[i] = "feed"
                    return roles
    return roles


_b._roles = _roles
_p._p._p._roles = _roles


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)

# benchmark trigger
