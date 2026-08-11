"""V34.16 isolated late reserve-pasture experiment.

Single economic mutation on verified V34.13. Keep its cow ceiling/window,
six-hand dairy crew, two-land policy, feed, crop routing, normal market logic and
late 9/10 staffing unchanged. Once >=10 cows are active and the estate is cash-
surplus and healthy, temporarily use only the final hired hand to commission up
to two spare pastures ahead of normal optional service work.

Rationale: V34.13 repeatedly buys a median 12 cows but activates only 10 while
ending near 11 pastures. Extra feed and extra late headcount both regressed, and
reducing the six-hand dairy crew was catastrophic. This test isolates whether a
small late structure-capacity buffer is the remaining activation bottleneck,
without buying extra animals, land, feed or labour.
"""
from __future__ import annotations
from typing import Any, List

from agents import v34_13_late_crop_hire10_isolated as _base

MIN_DAY = 16
MAX_DAY = 23
MIN_ACTIVE_COWS = 10
MIN_CASH = 20000
MAX_WEED_RATIO = 0.15
MAX_DANGER = 1
RESERVE_PASTURES = 2

_TRIGGERED = False


def _v19():
    return _base._v19()


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def reserve_pasture_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None):
    global _TRIGGERED
    result = dict(_base.agent(observation, configuration))
    v19 = _v19()
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = v19._m(farms[player])
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    if not isinstance(tiles, list) or not tiles or not hands:
        return result

    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    active = len(v19._active_cows(tiles))
    pastures = len(v19._pastures(tiles))
    health = v19._farm_health(farm)
    cow_count = v19._cow_count(obs, farm)
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    target = v19._cow_target(day, money, health, len(unlocked), cow_count, active)

    if not (
        MIN_DAY <= day <= MAX_DAY
        and active >= MIN_ACTIVE_COWS
        and money >= MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_DANGER
        and pastures < min(target, active + RESERVE_PASTURES)
    ):
        return result

    # Never interrupt a hand that is carrying anything: feed, cow placement and
    # harvested output all remain strictly ahead of this experimental structure.
    private = v19._m(obs.get("private"))
    inventories = private.get("inventories", [])
    unit_index = len(hands)  # last hired hand; inventories include farmer at 0
    inv = v19._m(inventories[unit_index]) if isinstance(inventories, list) and unit_index < len(inventories) else {}
    if any(int(v or 0) > 0 for v in inv.values()):
        return result

    positions = [v19._pos(farm.get("farmer", [0, 0]))] + [v19._pos(h) for h in hands]
    if unit_index >= len(positions):
        return result
    position = positions[unit_index]
    candidates = list(v19._outside_nw_empty(tiles))
    route = v19._nearest_route(tiles, position, candidates)
    if route is None:
        return result
    _, target_pos, _ = route
    action = v19._route_or_action(tiles, position, target_pos, ["BUILD_PASTURE"])

    hand_actions: List[List[Any]] = [
        list(a) if isinstance(a, list) else ["PASS"] for a in result.get("hands", [])
    ]
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])
    hand_actions[unit_index - 1] = action
    result["hands"] = hand_actions
    _TRIGGERED = True
    return result
