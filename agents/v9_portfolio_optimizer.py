"""V9 competition optimizer: opponent-aware melon/tomato portfolio.

The V8 benchmark proved that land expansion and nine hands are profitable against
weak opponents but lose consistently when both players flood the shared melon
market. V9 keeps the initial quadrant, uses five hands, and diversifies planting
between melons and tomatoes. The policy is deterministic and dependency-free so
this module can be submitted standalone after parameter selection.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)
SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)
CROP_DATA = {
    "WHEAT": (10, 2, 4, False),
    "CARROT": (20, 2, 3, False),
    "TOMATO": (50, 8, 8, True),
    "STRAWBERRY": (100, 10, 10, True),
    "MELON": (80, 10, 12, False),
}

MELON_SHARE = 60
TARGET_HANDS = 5
MELON_STOP_DAY = 15
TOMATO_STOP_DAY = 18


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


def _neighbours(tiles: Sequence[Sequence[Any]], pos: Position) -> Iterable[Tuple[str, Position]]:
    x, y = pos
    for action, dx, dy in DIRECTIONS:
        nxt = x + dx, y + dy
        if _inside(tiles, nxt):
            yield action, nxt


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
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
    planted = day if raw is None else int(raw)
    return day - planted


def tile_task(tile: Any, day: int) -> Optional[Tuple[int, List[Any]]]:
    kind = _kind(tile)
    if kind == "WEED":
        return 4, ["DIG"]
    if kind != "PLANT" or not isinstance(tile, Mapping):
        return None
    crop = str(tile.get("crop", "")).upper()
    data = CROP_DATA.get(crop)
    if data is None:
        return None
    _, first_day, max_day, ongoing = data
    age = _age(tile, day)
    watered = bool(tile.get("watered_today", False))
    danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
    yield_units = int(tile.get("yield_units", 0) or 0)
    if not watered and danger:
        return 0, ["WATER"]
    harvest_day = first_day if ongoing else max_day
    if yield_units > 0 and age >= harvest_day:
        return 1, ["HARVEST"]
    if not watered:
        return 2, ["WATER"]
    return None


def _targets(tiles: Sequence[Sequence[Any]], day: int):
    result = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            task = tile_task(tile, day)
            if task is not None:
                priority, action = task
                result.append((priority, (x, y), action))
    return result


def _empties(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]


def _crop_counts(tiles: Sequence[Sequence[Any]]) -> Counter:
    counts: Counter = Counter()
    for row in tiles:
        for tile in row:
            if isinstance(tile, Mapping) and _kind(tile) == "PLANT":
                counts[str(tile.get("crop", "")).upper()] += 1
    return counts


def _choose_crop(tiles: Sequence[Sequence[Any]], opponent_tiles: Sequence[Sequence[Any]], day: int) -> Optional[str]:
    own = _crop_counts(tiles)
    opponent = _crop_counts(opponent_tiles)
    total = own["MELON"] + own["TOMATO"]
    opponent_melon = opponent["MELON"]
    target_share = MELON_SHARE
    if opponent_melon >= 12:
        target_share = min(target_share, 40)
    elif opponent_melon >= 6:
        target_share = min(target_share, 50)
    melon_pct = 100 if total == 0 else (100 * own["MELON"] // total)
    if day <= MELON_STOP_DAY and melon_pct < target_share:
        return "MELON"
    if day <= TOMATO_STOP_DAY:
        return "TOMATO"
    if day <= MELON_STOP_DAY:
        return "MELON"
    return None


def _choose_available_crop(
    tiles: Sequence[Sequence[Any]],
    opponent_tiles: Sequence[Sequence[Any]],
    day: int,
    available_seeds: Mapping[str, int],
) -> Optional[str]:
    """Choose the preferred crop, falling back to any legal seeded crop.

    The portfolio target is advisory. A worker must not pass on an empty tile
    merely because the preferred crop has no seed while another permitted crop
    is available.
    """
    preferred = _choose_crop(tiles, opponent_tiles, day)
    if preferred and int(available_seeds.get(preferred, 0) or 0) > 0:
        return preferred
    alternatives = []
    if day <= MELON_STOP_DAY and int(available_seeds.get("MELON", 0) or 0) > 0:
        alternatives.append("MELON")
    if day <= TOMATO_STOP_DAY and int(available_seeds.get("TOMATO", 0) or 0) > 0:
        alternatives.append("TOMATO")
    return alternatives[0] if alternatives else None


def _assign(
    tiles: Sequence[Sequence[Any]], opponent_tiles: Sequence[Sequence[Any]], day: int,
    position: Position, targets, empties: Sequence[Position], reserved: Set[Position],
    available_seeds: Mapping[str, int],
) -> Tuple[List[Any], Optional[str]]:
    candidates = []
    for priority, target, action in targets:
        if target in reserved:
            continue
        route = _route(tiles, position, target)
        if route is not None:
            distance, first = route
            candidates.append((priority, distance, target[1], target[0], target, action, first))
    if candidates:
        candidates.sort()
        _, distance, _, _, target, action, first = candidates[0]
        reserved.add(target)
        return (action if distance == 0 else [first]), None

    crop = _choose_available_crop(tiles, opponent_tiles, day, available_seeds)
    if crop:
        plant_candidates = []
        for target in empties:
            if target in reserved:
                continue
            route = _route(tiles, position, target)
            if route is not None:
                distance, first = route
                plant_candidates.append((distance, target[1], target[0], target, first))
        if plant_candidates:
            plant_candidates.sort()
            distance, _, _, target, first = plant_candidates[0]
            reserved.add(target)
            return (["PLANT", crop] if distance == 0 else [first]), (crop if distance == 0 else None)
    return ["PASS"], None


def _market_orders(obs: Mapping[str, Any], farm: Mapping[str, Any], empty_count: int, unit_count: int) -> List[List[Any]]:
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seeds = _mapping(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands", []))
    liquidate = day >= 29 or (day == 28 and hour >= 18)
    orders: List[List[Any]] = []
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])
    if not liquidate:
        for _ in range(max(0, TARGET_HANDS - len(hands))):
            if len(orders) >= 8:
                break
            orders.append(["HIRE"])
    if not liquidate and empty_count > 0:
        for crop, stop_day, reserve_mult in (
            ("MELON", MELON_STOP_DAY, 2),
            ("TOMATO", TOMATO_STOP_DAY, 2),
        ):
            if day > stop_day or len(orders) >= 10:
                continue
            current = int(seeds.get(crop, 0) or 0)
            desired = min(empty_count, max(8, unit_count * reserve_mult))
            buy = max(0, desired - current)
            seed_cost = CROP_DATA[crop][0]
            affordable = max(0, int(money // seed_cost))
            buy = min(buy, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                money -= buy * seed_cost
    return orders[:10]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = _mapping(farms[player])
    opponent_farm = _mapping(farms[1 - player]) if len(farms) > 1 else {}
    tiles = farm.get("tiles", [])
    opponent_tiles = opponent_farm.get("tiles", [])
    hands = list(farm.get("hands", []))
    result = {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}
    if not isinstance(tiles, list) or not tiles:
        return result
    day = int(obs.get("day", 0) or 0)
    private = _mapping(obs.get("private"))
    seed_map = _mapping(private.get("seeds"))
    remaining = {crop: int(seed_map.get(crop, 0) or 0) for crop in ("MELON", "TOMATO")}
    targets = _targets(tiles, day)
    empties = _empties(tiles)
    positions = [_position(farm.get("farmer", [0, 0]))] + [_position(hand) for hand in hands]
    reserved: Set[Position] = set()
    assigned: List[List[Any]] = []
    for position in positions:
        action, planted = _assign(
            tiles, opponent_tiles, day, position, targets, empties, reserved, remaining
        )
        if planted:
            remaining[planted] -= 1
        assigned.append(action)
    result["farmer"] = assigned[0]
    result["hands"] = assigned[1:]
    result["market"] = _market_orders(obs, farm, len(empties), len(positions))
    return result
