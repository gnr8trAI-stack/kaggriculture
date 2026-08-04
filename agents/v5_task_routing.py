"""Agent V5: preserve V2 economics and improve unit task routing.

V2 uses strict global task priority before distance, so a unit may cross the farm
for a harvest while ignoring useful nearby maintenance. V5 uses a bounded
priority penalty plus path distance, preserving harvest urgency without making
all lower-priority work globally invisible.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Set, Tuple

from agents.v2_frozen import (
    Position,
    _as_dict,
    _distance_and_first_step,
    _empty_targets,
    _position,
    _sell_orders,
    _task_targets,
)

PRIORITY_WEIGHT = 3


def _assign_unit_v5(
    tiles: Sequence[Sequence[Any]],
    position: Position,
    targets: Sequence[Tuple[int, Position, List[Any]]],
    reserved: Set[Position],
    can_plant: bool,
) -> List[Any]:
    candidates: List[Tuple[int, int, int, Position, List[Any], str]] = []
    for priority, target, task in targets:
        if target in reserved:
            continue
        route = _distance_and_first_step(tiles, position, target)
        if route is None:
            continue
        distance, first = route
        score = priority * PRIORITY_WEIGHT + distance
        candidates.append((score, priority, distance, target, task, first))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3][1], item[3][0]))
        _, _, distance, target, task, first = candidates[0]
        reserved.add(target)
        return task if distance == 0 else [first]

    if can_plant:
        plant_candidates: List[Tuple[int, Position, str]] = []
        for target in _empty_targets(tiles):
            if target in reserved:
                continue
            route = _distance_and_first_step(tiles, position, target)
            if route is not None:
                distance, first = route
                plant_candidates.append((distance, target, first))
        if plant_candidates:
            plant_candidates.sort(key=lambda item: (item[0], item[1][1], item[1][0]))
            distance, target, first = plant_candidates[0]
            reserved.add(target)
            return ["PLANT", "WHEAT"] if distance == 0 else [first]

    return ["PASS"]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _as_dict(observation)
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    if player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    tiles = farm.get("tiles", [])
    raw_hands = list(farm.get("hands", []))
    action: Dict[str, Any] = {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in raw_hands],
        "market": [],
    }
    if not tiles:
        return action

    seeds = int(obs.get("private", {}).get("seeds", {}).get("WHEAT", 0) or 0)
    targets = _task_targets(tiles)
    reserved: Set[Position] = set()
    remaining_seeds = seeds

    units = [("farmer", _position(farm.get("farmer", [0, 0])))]
    units.extend((index, _position(hand)) for index, hand in enumerate(raw_hands))
    for unit, position in units:
        assigned = _assign_unit_v5(tiles, position, targets, reserved, remaining_seeds > 0)
        if unit == "farmer":
            action["farmer"] = assigned
        else:
            action["hands"][unit] = assigned
        if assigned[:1] == ["PLANT"]:
            remaining_seeds -= 1

    day, hour = int(obs.get("day", 0)), int(obs.get("hour", 0))
    liquidate = day >= 29 or (day == 28 and hour >= 18)
    market = _sell_orders(obs, liquidate)
    money = float(farm.get("money", 0) or 0)
    desired_buffer = max(2, 1 + len(raw_hands))
    if not liquidate and seeds < desired_buffer and money >= 10 * (desired_buffer - seeds) and len(market) < 10:
        market.append(["BUY_SEED", "WHEAT", desired_buffer - seeds])
    action["market"] = market[:10]
    return action
