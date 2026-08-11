"""V34.2 isolated livestock-capacity experiment.

Single economic mutation on top of V34.1: keep the four-hand livestock service
crew, V19.2 land/crop/feed/routing/market policy, and staffing limits unchanged,
but raise the mature cow ceiling from 8 to 12. V34.1 independently verified
that four service hands can activate a median eight cows and materially improve
reward, so this test isolates whether the next binding constraint is simply
insufficient productive livestock capacity rather than service throughput.
"""
from __future__ import annotations
from typing import Any, List, Set

from agents import v19_2_early_scale8 as _v192

_v19 = _v192._v19
CREW_COUNT = 4


def _activate() -> None:
    # V34.1 operating shape, changing only mature livestock capacity 8 -> 12.
    _v19.INITIAL_COW_TARGET = 4
    _v19.MAX_COW_TARGET = 12
    _v19.START_COWS_MAX_DAY = 19
    _v19.MIN_HANDS_WITH_COWS = 8
    _v19.MAX_HANDS_WITH_COWS = 10
    _v19._inject_market_orders = _v192._inject_market_orders


def reset_state() -> None:
    _v192.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v192.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    result = dict(_v19.agent(observation, configuration))

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


_activate()
