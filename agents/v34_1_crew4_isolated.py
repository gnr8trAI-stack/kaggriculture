"""V34.1 isolated livestock-service experiment.

Single economic mutation on top of V34.0: keep the same staged 4->8 cow target,
land policy, crop policy, feed policy and market logic, but increase the active
livestock service crew from V19's fixed two hands to four hands. The prior V34.0
benchmark bought a median 8 cows but activated only a median 4, so this isolates
whether placement/pasture/feed/harvest throughput is the binding constraint.
"""
from __future__ import annotations
from typing import Any, List, Set

from agents import v34_0_cow8_isolated as _v340

_v192 = _v340._v192
_v19 = _v340._v19

CREW_COUNT = 4


def reset_state() -> None:
    _v340.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v340.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    # First execute V34.0 unchanged. Then only replace the last four hand actions
    # with the same V19 livestock worker routine already used by its fixed two-hand
    # crew. No market, target, land, crop, pricing, feed, or routing logic changes.
    result = dict(_v340.agent(observation, configuration))

    obs = _v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = _v19._m(farms[player])
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    if not isinstance(tiles, list) or not tiles or not hands:
        return result

    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    health = _v19._farm_health(farm)
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    cow_count = _v19._cow_count(obs, farm)
    active_count = len(_v19._active_cows(tiles))
    target_cows = _v19._cow_target(day, money, health, len(unlocked), cow_count, active_count)

    if not (active_count or target_cows > 0 or len(_v19._pastures(tiles)) > 0):
        return result

    hand_actions: List[List[Any]] = [
        list(a) if isinstance(a, list) else ["PASS"] for a in result.get("hands", [])
    ]
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])

    crew = min(CREW_COUNT, len(hands))
    first_unit = 1 + len(hands) - crew
    reserved: Set[_v19.Position] = set()
    full_service = float(health.get("weed_ratio", 0.0) or 0.0) <= _v19.MAX_WEED_RATIO_FOR_FULL_SERVICE

    for unit_index in range(first_unit, 1 + len(hands)):
        action, _stage = _v19._livestock_action(
            obs, farm, unit_index, reserved, target_cows, full_service
        )
        if action is not None:
            hand_actions[unit_index - 1] = action

    result["hands"] = hand_actions
    return result
