"""V34.18 isolated reserve-pasture window extension.

Single mutation on verified V34.17: keep the two-land policy, late 9/10 staffing,
16-cow target/window, six-hand dairy crew, V34.16 reserve-pasture logic and
V34.17 cow-activation rescue unchanged, except allow reserve-pasture
commissioning through day 27 instead of day 23.

Economic rationale: V34.17 robustly activates all 12 purchased cows, but median
peak pasture capacity remains 12 despite a 16-cow ceiling. The reserve builder
stops on day 23, exactly when the herd is only finishing activation. Extending
that one structure-capacity window tests whether late pasture headroom is the
next bottleneck without changing land, cow buying, feed, wages, routing or crop
policy.
"""
from __future__ import annotations
from typing import Any

from agents import v34_17_late_cow_activation_rescue as _base

RESERVE_MAX_DAY = 27
_TRIGGERED = False


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def reserve_window_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    global _TRIGGERED
    # V34.16 owns the reserve-pasture gate two levels below V34.17.
    reserve = _base._base
    old = reserve.MAX_DAY
    reserve.MAX_DAY = RESERVE_MAX_DAY
    try:
        result = _base.agent(observation, configuration)
    finally:
        reserve.MAX_DAY = old

    v19 = _base._v19()
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if isinstance(farms, list) and player < len(farms):
        farm = v19._m(farms[player])
        day = int(obs.get("day", 0) or 0)
        active = len(v19._active_cows(farm.get("tiles") or []))
        if day >= 24 and active >= 10 and reserve.reserve_pasture_triggered():
            _TRIGGERED = True
    return result
