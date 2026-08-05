"""V10 competition candidate: age-10 melons with mid-day liquidation.

Official Kaggriculture mechanics make two facts decisive:
- An unfertilized, daily-watered melon reaches its yield cap at age 10.
- Melon's glut curve is extremely steep, so selling before the opponent's
  end-of-day inventory transfer captures substantially better prices.

V10 keeps one 5x5 quadrant, hires five hands daily, harvests melons at age 10,
routes loaded units back to the shed during the day, and continuously sells
shed inventory. The module is dependency-free and submission-safe.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1),
    ("SOUTH", 0, 1),
    ("WEST", -1, 0),
    ("EAST", 1, 0),
)

CROP = "MELON"
SEED_COST = 80
MAX_YIELD_DAY = 10
STOP_PLANT_DAY = 18
TARGET_HANDS = 5
DROP_INVENTORY_AT = 1
DROP_FROM_HOUR = 10
SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: Dict[str, Any] = {}
    for key in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            result[key] = getattr(value, key)
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


def _inside(tiles: Sequence[Sequence[Any]], pos: Position) -> bool:
    x, y = pos
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _neighbours(
    tiles: Sequence[Sequence[Any]], pos: Position
) -> Iterable[Tuple[str, Position]]:
    x, y = pos
    for action, dx, dy in DIRECTIONS:
        nxt = x + dx, y + dy
        if _inside(tiles, nxt):
            yield action, nxt


def _route(
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


def _kind(tile: Any) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, Mapping):
        return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _age(tile: Mapping[str, Any], day: int) -> int:
    raw = tile.get("planted_day", day)
    planted_day = day if raw is None else int(raw)
    return day - planted_day


def _inventory_total(inventory: Mapping[str, Any]) -> int:
    return sum(max(0, int(value or 0)) for value in inventory.values())


def _shed_cells(board_size: int) -> Tuple[Position, Position, Position, Position]:
    half = board_size // 2
    return (
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    )


def _return_to_shed(
    tiles: Sequence[Sequence[Any]], position: Position
) -> List[Any]:
    cells = _shed_cells(len(tiles))
    if position in cells:
        return ["DROP"]
    choices: List[Tuple[int, int, int, str]] = []
    for target in cells:
        route = _route(tiles, position, target)
        if route is not None:
            distance, first = route
            choices.append((distance, target[1], target[0], first))
    if not choices:
        return ["PASS"]
    choices.sort()
    return [choices[0][3]]


def tile_task(tile: Any, day: int) -> Optional[Tuple[int, List[Any]]]:
    """Return task priority and legal action for an occupied tile."""
    kind = _kind(tile)
    if kind == "WEED":
        return 4, ["DIG"]
    if kind != "PLANT" or not isinstance(tile, Mapping):
        return None

    crop = str(tile.get("crop", "")).upper()
    watered = bool(tile.get("watered_today", False))
    danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
    yield_units = int(tile.get("yield_units", 0) or 0)
    age = _age(tile, day)

    # Prevent overnight loss before any economic task.
    if not watered and danger:
        return 0, ["WATER"]

    if crop == CROP:
        if yield_units > 0 and age >= MAX_YIELD_DAY:
            return 1, ["HARVEST"]
        if not watered:
            return 2, ["WATER"]
        return None

    first_yield = {
        "WHEAT": 2,
        "CARROT": 2,
        "TOMATO": 8,
        "STRAWBERRY": 10,
    }.get(crop, 0)
    if yield_units > 0 and age >= first_yield:
        return 1, ["HARVEST"]
    if not watered:
        return 2, ["WATER"]
    return None


def _targets(
    tiles: Sequence[Sequence[Any]], day: int
) -> List[Tuple[int, Position, List[Any]]]:
    result: List[Tuple[int, Position, List[Any]]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            task = tile_task(tile, day)
            if task is not None:
                priority, action = task
                result.append((priority, (x, y), action))
    return result


def _empties(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile is None
    ]


def _best_task(
    tiles: Sequence[Sequence[Any]],
    position: Position,
    targets: Sequence[Tuple[int, Position, List[Any]]],
    reserved: Set[Position],
    max_priority: Optional[int] = None,
) -> Optional[List[Any]]:
    choices: List[Tuple[int, int, int, int, Position, List[Any], str]] = []
    for priority, target, action in targets:
        if target in reserved or (max_priority is not None and priority > max_priority):
            continue
        route = _route(tiles, position, target)
        if route is None:
            continue
        distance, first = route
        choices.append(
            (priority, distance, target[1], target[0], target, action, first)
        )
    if not choices:
        return None
    choices.sort()
    _, distance, _, _, target, action, first = choices[0]
    reserved.add(target)
    return action if distance == 0 else [first]


def _plant_action(
    tiles: Sequence[Sequence[Any]],
    position: Position,
    empties: Sequence[Position],
    reserved: Set[Position],
) -> List[Any]:
    choices: List[Tuple[int, int, int, Position, str]] = []
    for target in empties:
        if target in reserved:
            continue
        route = _route(tiles, position, target)
        if route is None:
            continue
        distance, first = route
        choices.append((distance, target[1], target[0], target, first))
    if not choices:
        return ["PASS"]
    choices.sort()
    distance, _, _, target, first = choices[0]
    reserved.add(target)
    return ["PLANT", CROP] if distance == 0 else [first]


def _unit_action(
    tiles: Sequence[Sequence[Any]],
    day: int,
    hour: int,
    position: Position,
    inventory: Mapping[str, Any],
    targets: Sequence[Tuple[int, Position, List[Any]]],
    empties: Sequence[Position],
    reserved: Set[Position],
    can_plant: bool,
) -> List[Any]:
    # At-risk watering always outranks logistics.
    urgent = _best_task(tiles, position, targets, reserved, max_priority=0)
    if urgent is not None:
        return urgent

    load = _inventory_total(inventory)
    if load >= DROP_INVENTORY_AT and hour >= DROP_FROM_HOUR:
        return _return_to_shed(tiles, position)

    regular = _best_task(tiles, position, targets, reserved)
    if regular is not None:
        return regular

    if load > 0:
        return _return_to_shed(tiles, position)

    if can_plant:
        return _plant_action(tiles, position, empties, reserved)

    return ["PASS"]


def _market_orders(
    obs: Mapping[str, Any],
    farm: Mapping[str, Any],
    empty_count: int,
    unit_count: int,
) -> List[List[Any]]:
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seeds = _mapping(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands", []))
    liquidate = day >= 29 or (day == 28 and hour >= 12)

    orders: List[List[Any]] = []
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])

    if not liquidate:
        for _ in range(max(0, TARGET_HANDS - len(hands))):
            if len(orders) >= 9:
                break
            orders.append(["HIRE"])

    if not liquidate and day <= STOP_PLANT_DAY and empty_count > 0 and len(orders) < 10:
        current = int(seeds.get(CROP, 0) or 0)
        desired = min(empty_count, max(12, unit_count * 3))
        buy = max(0, desired - current)
        affordable = max(0, int(money // SEED_COST))
        buy = min(buy, affordable)
        if buy > 0:
            orders.append(["BUY_SEED", CROP, buy])

    return orders[:10]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = _mapping(farms[player])
    tiles = farm.get("tiles", [])
    hands = list(farm.get("hands", []))
    result: Dict[str, Any] = {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in hands],
        "market": [],
    }
    if not isinstance(tiles, list) or not tiles:
        return result

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    private = _mapping(obs.get("private"))
    seed_count = int(_mapping(private.get("seeds")).get(CROP, 0) or 0)
    inventories = private.get("inventories", [])
    if not isinstance(inventories, list):
        inventories = []

    targets = _targets(tiles, day)
    empties = _empties(tiles)
    positions = [_position(farm.get("farmer", [0, 0]))] + [
        _position(hand) for hand in hands
    ]

    reserved: Set[Position] = set()
    remaining_seeds = seed_count
    assigned: List[List[Any]] = []

    for index, position in enumerate(positions):
        inventory = _mapping(inventories[index]) if index < len(inventories) else {}
        can_plant = day <= STOP_PLANT_DAY and remaining_seeds > 0
        action = _unit_action(
            tiles,
            day,
            hour,
            position,
            inventory,
            targets,
            empties,
            reserved,
            can_plant,
        )
        if action[:1] == ["PLANT"]:
            remaining_seeds -= 1
        assigned.append(action)

    result["farmer"] = assigned[0]
    result["hands"] = assigned[1:]
    result["market"] = _market_orders(
        obs, farm, len(empties), len(positions)
    )
    return result
