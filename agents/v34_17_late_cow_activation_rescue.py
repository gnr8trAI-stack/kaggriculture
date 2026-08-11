"""V34.17 isolated late cow-activation rescue.

Single mutation on verified V34.16. Preserve its two-land policy, V34.13 late
9/10 staffing, 16-cow ceiling/window, six-hand dairy crew, crop/feed/routing,
and late reserve-pasture commissioning. Only when the mature estate already has
>=10 active cows, cash surplus, an empty pasture, and a purchased cow waiting in
the shed does the final hired hand prioritize moving exactly that cow from shed
to pasture ahead of optional service work.

Rationale: V34.16 reached median 12 purchased cows and 12 pastures but still
only 10 active cows. The original livestock routine services harvest/care before
picking a shed cow, while the earlier global placement-priority experiment
regressed. This tests only a late, state-specific activation rescue after the
capacity and cash are already present.
"""
from __future__ import annotations
from typing import Any, List

from agents import v34_16_late_reserve_pasture_isolated as _base

MIN_DAY = 16
MAX_DAY = 24
MIN_ACTIVE_COWS = 10
MIN_CASH = 20000
MAX_WEED_RATIO = 0.15
MAX_DANGER = 1

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


def activation_rescue_triggered() -> bool:
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
    cow_count = v19._cow_count(obs, farm)
    empty_pastures = list(v19._empty_pastures(tiles))
    health = v19._farm_health(farm)
    if not (
        MIN_DAY <= day <= MAX_DAY
        and active >= MIN_ACTIVE_COWS
        and cow_count > active
        and empty_pastures
        and money >= MIN_CASH
        and float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_WEED_RATIO
        and int(health.get("danger", 0) or 0) <= MAX_DANGER
    ):
        return result

    private = v19._m(obs.get("private"))
    shed = v19._m(private.get("shed"))
    inventories = private.get("inventories", [])
    unit_index = len(hands)
    inv = v19._m(inventories[unit_index]) if isinstance(inventories, list) and unit_index < len(inventories) else {}
    position = v19._pos(hands[-1])

    if int(inv.get(v19.ANIMAL, 0) or 0) > 0:
        route = v19._nearest_route(tiles, position, empty_pastures)
        if route is None:
            return result
        _, target, _ = route
        action = v19._route_or_action(tiles, position, target, ["PLACE", v19.ANIMAL])
    else:
        if any(int(v or 0) > 0 for v in inv.values()) or int(shed.get(v19.ANIMAL, 0) or 0) <= 0:
            return result
        action = v19._to_shed_action(tiles, position, ["PICKUP", v19.ANIMAL, 1])

    hand_actions: List[List[Any]] = [list(a) if isinstance(a, list) else ["PASS"] for a in result.get("hands", [])]
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])
    hand_actions[-1] = action
    result["hands"] = hand_actions
    _TRIGGERED = True
    return result
