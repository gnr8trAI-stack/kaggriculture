"""V34.12 isolated dynamic livestock-crew experiment.

Single economic mutation on top of V34.10/V34.6: preserve the 16-cow ceiling,
day-24 purchase window, terminal liquidation, land/crop/feed/market/staffing
policy, and six-hand livestock crew while the herd is being commissioned; once
10 cows are active, return two hands to the inherited crop scheduler by reducing
the livestock crew to four.

Rationale: V34.6 reaches a median 10 active cows but the user replay and issue
telemetry show crop capacity retiring while six of at most eight hands remain
permanently dedicated to livestock. Hiring 11-12 hands was strongly negative in
V34.11, so this tests workload reallocation without adding wage cost.
"""
from __future__ import annotations
from typing import Any

from agents import v34_10_terminal_liquidation_isolated as _base

COMMISSION_CREW = 6
MATURE_CREW = 4
MATURE_ACTIVE_COWS = 10


def _active_cows(observation: Any) -> int:
    obs = _base._v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return 0
    farm = farms[player] if isinstance(farms[player], dict) else {}
    return len(_base._v19._active_cows(farm.get("tiles") or []))


def _set_crew(count: int) -> None:
    # V34.6 -> V34.5 -> V34.3.  V34.5._activate() copies its CREW_COUNT into
    # V34.3 before every decision, so mutate V34.5's exposed knob only.
    _base._v346._v345.CREW_COUNT = count


def reset_state() -> None:
    _set_crew(COMMISSION_CREW)
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    active = _active_cows(observation)
    _set_crew(MATURE_CREW if active >= MATURE_ACTIVE_COWS else COMMISSION_CREW)
    return _base.agent(observation, configuration)
