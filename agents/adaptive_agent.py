"""Dependency-free Kaggriculture V2 heuristic agent.

The agent uses reservation-aware breadth-first search to service visible farm
assets and coordinate the farmer with hired hands. It deliberately keeps the
economic policy simple until real-environment benchmarks validate the state
schema and movement semantics.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1),
    ("SOUTH", 0, 1),
    ("WEST", -1, 0),
    ("EAST", 1, 0),
)


def _as_dict(observation: Any) -> Dict[str, Any]:
    if isinstance(observation, dict):
        return observation
    result: Dict[str, Any] = {}
    for name in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            result[name] = getattr(observation, name)
        except Exception:
            pass
    return result


def _position(value: Any) -> Position:
    if isinstance(value, Mapping):
        value = value.get("position", value.get("pos", [0, 0]))
    try:
        return int(value[0]), int(value[1])
    except Exception:
        return 0, 0


def _kind(tile: Any) -> Optional[str]:
    if not isinstance(tile, Mapping):
        return None
    value = tile.get("kind", tile.get("type"))
    return str(value).upper() if value is not None else None


def _tile_task(tile: Any) -> Optional[List[Any]]:
    if not isinstance(tile, Mapping):
        return None
    kind = _kind(tile)
    if kind == "PLANT":
        if int(tile.get("yield_units", tile.get("yield", 0)) or 0) > 0:
            return ["HARVEST"]
        if not bool(tile.get("watered_today", tile.get("watered", False))):
            return ["WATER"]
    if kind in ("COOP", "PASTURE") and tile.get("animal"):
        if int(tile.get("yield_units", tile.get("yield", 0)) or 0) > 0:
            return ["HARVEST"]
        if not bool(tile.get("fed_today", tile.get("fed", False))):
            return ["FEED"]
        if not bool(tile.get("cared_today", tile.get("cared", False))):
            return ["CARE"]
        if bool(tile.get("fertilizer_available", False)):
            return ["COLLECT_FERTILIZER"]
    if kind == "WEED":
        return ["DIG"]
    return None


def _priority(tile: Any) -> Optional[int]:
    task = _tile_task(tile)
    if task is None:
        return None
    return {
        "HARVEST": 0,
        "WATER": 1,
        "FEED": 1,
        "CARE": 2,
        "COLLECT_FERTILIZER": 3,
        "DIG": 4,
    }[task[0]]


def _inside(tiles: Sequence[Sequence[Any]], pos: Position) -> bool:
    x, y = pos
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _walkable(tiles: Sequence[Sequence[Any]], pos: Position) -> bool:
    if not _inside(tiles, pos):
        return False
    tile = tiles[pos[1]][pos[0]]
    return tile != "LOCKED" and _kind(tile) != "LOCKED"


def _neighbours(tiles: Sequence[Sequence[Any]], pos: Position) -> Iterable[Tuple[str, Position]]:
    x, y = pos
    for action, dx, dy in DIRECTIONS:
        nxt = x + dx, y + dy
        if _walkable(tiles, nxt):
            yield action, nxt


def _distance_and_first_step(
    tiles: Sequence[Sequence[Any]], start: Position, goal: Position
) -> Optional[Tuple[int, str]]:
    if start == goal:
        return 0, "PASS"
    queue = deque([(start, 0, None)])
    seen = {start}
    while queue:
        pos, distance, first = queue.popleft()
        for action, nxt in _neighbours(tiles, pos):
            if nxt in seen:
                continue
            seen.add(nxt)
            first_action = first or action
            if nxt == goal:
                return distance + 1, first_action
            queue.append((nxt, distance + 1, first_action))
    return None


def _task_targets(tiles: Sequence[Sequence[Any]]) -> List[Tuple[int, Position, List[Any]]]:
    targets: List[Tuple[int, Position, List[Any]]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            priority = _priority(tile)
            task = _tile_task(tile)
            if priority is not None and task is not None:
                targets.append((priority, (x, y), task))
    return targets


def _empty_targets(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile is None
    ]


def _assign_unit(
    tiles: Sequence[Sequence[Any]],
    position: Position,
    targets: Sequence[Tuple[int, Position, List[Any]]],
    reserved: Set[Position],
    can_plant: bool,
) -> List[Any]:
    candidates: List[Tuple[int, int, Position, List[Any], str]] = []
    for priority, target, task in targets:
        if target in reserved:
            continue
        route = _distance_and_first_step(tiles, position, target)
        if route is not None:
            distance, first = route
            candidates.append((priority, distance, target, task, first))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1], item[2][1], item[2][0]))
        _, distance, target, task, first = candidates[0]
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


def _sell_orders(obs: Mapping[str, Any], liquidate: bool) -> List[List[Any]]:
    shed = obs.get("private", {}).get("shed", {})
    orders: List[List[Any]] = []
    for product in PRODUCTS:
        quantity = int(shed.get(product, 0) or 0)
        if quantity > 0 and (liquidate or quantity >= 10):
            orders.append(["SELL", product, quantity])
        if len(orders) == 10:
            break
    return orders


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

    farmer_position = _position(farm.get("farmer", [0, 0]))
    action["farmer"] = _assign_unit(
        tiles, farmer_position, targets, reserved, remaining_seeds > 0
    )
    if action["farmer"][:1] == ["PLANT"]:
        remaining_seeds -= 1

    for index, hand in enumerate(raw_hands):
        hand_position = _position(hand)
        action["hands"][index] = _assign_unit(
            tiles, hand_position, targets, reserved, remaining_seeds > 0
        )
        if action["hands"][index][:1] == ["PLANT"]:
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
