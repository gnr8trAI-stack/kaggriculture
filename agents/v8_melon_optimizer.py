"""V8 competition candidate: melon-first economics with controlled expansion.

The telemetry tournament showed that V7's carrot policy was operationally sound
but economically dominated by long-cycle premium crops. V8 therefore uses
melons as its core crop, expands once after the first harvest window, scales its
daily workforce to unlocked acreage, and stops planting early enough to harvest,
transfer, and sell before the episode ends.

The file is dependency-free and can be submitted standalone.
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
FIRST_YIELD_DAY = 10
MAX_YIELD_DAY = 12
STOP_PLANT_DAY = 16
EXPAND_FROM_DAY = 10
EXPAND_THROUGH_DAY = 14
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
        # Movement through locked cells is legal in the official simulator.
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


def tile_task(tile: Any, day: int) -> Optional[Tuple[int, List[Any]]]:
    """Return a conservative task priority and legal action for a tile."""
    kind = _kind(tile)
    if kind == "WEED":
        return 4, ["DIG"]
    if kind != "PLANT" or not isinstance(tile, Mapping):
        return None

    crop = str(tile.get("crop", "")).upper()
    age = _age(tile, day)
    watered = bool(tile.get("watered_today", False))
    danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
    yield_units = int(tile.get("yield_units", 0) or 0)

    # A crop that will die at the day boundary is the highest-priority task.
    if not watered and danger:
        return 0, ["WATER"]

    if crop == CROP:
        # Wait for maximum-yield maturity, not merely first legal maturity.
        if age >= MAX_YIELD_DAY and yield_units > 0:
            return 1, ["HARVEST"]
        if not watered:
            return 2, ["WATER"]
        return None

    # Safely service any inherited or accidental non-melon crop.
    first_day = {
        "WHEAT": 2,
        "CARROT": 2,
        "TOMATO": 8,
        "STRAWBERRY": 10,
        "MELON": 10,
    }.get(crop, 0)
    if yield_units > 0 and age >= first_day:
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


def _assign(
    tiles: Sequence[Sequence[Any]],
    position: Position,
    targets: Sequence[Tuple[int, Position, List[Any]]],
    empties: Sequence[Position],
    reserved: Set[Position],
    can_plant: bool,
) -> List[Any]:
    candidates: List[Tuple[int, int, int, int, Position, List[Any], str]] = []
    for priority, target, action in targets:
        if target in reserved:
            continue
        route = _route(tiles, position, target)
        if route is None:
            continue
        distance, first = route
        candidates.append(
            (priority, distance, target[1], target[0], target, action, first)
        )

    if candidates:
        candidates.sort()
        _, distance, _, _, target, action, first = candidates[0]
        reserved.add(target)
        return action if distance == 0 else [first]

    if can_plant:
        plant_candidates: List[Tuple[int, int, int, Position, str]] = []
        for target in empties:
            if target in reserved:
                continue
            route = _route(tiles, position, target)
            if route is None:
                continue
            distance, first = route
            plant_candidates.append(
                (distance, target[1], target[0], target, first)
            )
        if plant_candidates:
            plant_candidates.sort()
            distance, _, _, target, first = plant_candidates[0]
            reserved.add(target)
            return ["PLANT", CROP] if distance == 0 else [first]

    return ["PASS"]


def _target_hands(unlocked_count: int, active_tiles: int) -> int:
    # 5 hands + farmer handle the initial 25 tiles. After one expansion,
    # 9 hands + farmer provide enough daily watering and harvest throughput.
    if unlocked_count >= 2 or active_tiles > 25:
        return 9
    return 5


def _market_orders(
    obs: Mapping[str, Any],
    farm: Mapping[str, Any],
    empty_count: int,
    active_tiles: int,
    unit_count: int,
) -> List[List[Any]]:
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seeds = _mapping(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands", []))
    unlocked = list(farm.get("unlocked_quadrants", []))
    liquidate = day >= 29 or (day == 28 and hour >= 18)

    orders: List[List[Any]] = []

    # Continuous selling prevents shed pressure and ensures inventory transferred
    # at the previous day boundary is converted to final reward immediately.
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])

    # Buy exactly one extra quadrant after the first melon harvest window.
    should_expand = (
        not liquidate
        and len(unlocked) == 1
        and EXPAND_FROM_DAY <= day <= EXPAND_THROUGH_DAY
        and money >= 1000
        and len(orders) < 10
    )
    if should_expand:
        orders.append(["BUY_LAND"])

    target_hands = 0 if liquidate else _target_hands(len(unlocked), active_tiles)
    hires_needed = max(0, target_hands - len(hands))
    for _ in range(hires_needed):
        if len(orders) >= 9:
            break
        orders.append(["HIRE"])

    if not liquidate and day <= STOP_PLANT_DAY and empty_count > 0 and len(orders) < 10:
        current_seeds = int(seeds.get(CROP, 0) or 0)
        # Keep enough seeds for roughly two turns of parallel planting, while
        # allowing a newly expanded field to fill quickly.
        desired = min(empty_count, max(12, unit_count * 3))
        buy = max(0, desired - current_seeds)
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
    private = _mapping(obs.get("private"))
    seeds = int(_mapping(private.get("seeds")).get(CROP, 0) or 0)

    targets = _targets(tiles, day)
    empties = _empties(tiles)
    active_tiles = sum(
        1
        for row in tiles
        for tile in row
        if tile is not None and tile != "LOCKED"
    )

    positions = [_position(farm.get("farmer", [0, 0]))] + [
        _position(hand) for hand in hands
    ]
    reserved: Set[Position] = set()
    remaining_seeds = seeds
    assigned: List[List[Any]] = []

    for position in positions:
        can_plant = day <= STOP_PLANT_DAY and remaining_seeds > 0
        unit_action = _assign(
            tiles, position, targets, empties, reserved, can_plant
        )
        if unit_action[:1] == ["PLANT"]:
            remaining_seeds -= 1
        assigned.append(unit_action)

    result["farmer"] = assigned[0]
    result["hands"] = assigned[1:]
    result["market"] = _market_orders(
        obs,
        farm,
        len(empties),
        active_tiles,
        len(positions),
    )
    return result
