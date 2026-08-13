"""V19.4: V19.3 planned third land plus protected post-Q3 commissioning labour.

Single economic mutation from V19.3:
- once the third quadrant is actually unlocked, raise the V19.2 livestock-era
  daily hand target from 7/8 to 10/10 so the newly purchased 25-tile district
  can be commissioned without stealing the existing crop/livestock workforce;
- before Q3, retain the exact V19.2 7/8 hand policy.

No crop mix, cow target, feed policy, land gate, market ordering, or routing
logic is changed. This is an isolated benchmark challenger only.
"""
from __future__ import annotations
from typing import Any, Mapping

from agents import v19_3_third_land as _v193
from agents import v19_2_early_scale8 as _v192
from agents import v19_livestock_compound as _core

PRE_Q3_MIN_HANDS = 7
PRE_Q3_MAX_HANDS = 8
POST_Q3_HANDS = 10


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _land_count(observation: Any) -> int:
    obs = _core._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return 1
    farm = _m(farms[player])
    return max(1, len(list(farm.get("unlocked_quadrants") or ["NW"])))


def reset_state() -> None:
    _core.MIN_HANDS_WITH_COWS = PRE_Q3_MIN_HANDS
    _core.MAX_HANDS_WITH_COWS = PRE_Q3_MAX_HANDS
    _v193.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v193.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    lands = _land_count(observation)
    if lands >= 3:
        _core.MIN_HANDS_WITH_COWS = POST_Q3_HANDS
        _core.MAX_HANDS_WITH_COWS = POST_Q3_HANDS
    else:
        _core.MIN_HANDS_WITH_COWS = PRE_Q3_MIN_HANDS
        _core.MAX_HANDS_WITH_COWS = PRE_Q3_MAX_HANDS
    return _v193.agent(observation, configuration)
