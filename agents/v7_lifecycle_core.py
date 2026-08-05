"""Competition candidate V7: correct crop lifecycle and operate the full first field.

This agent fixes the frozen V2 lifecycle defect: one-time crops start with one
potential yield unit, but are not harvestable until their maturity window.
V7 waters crops until their max-yield day, harvests only when mature, clears
weeds, replants carrots, hires inexpensive daily hands, and sells continuously.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)
CROP = "CARROT"
FIRST_YIELD_DAY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
MAX_YIELD_DAY = {"WHEAT": 4, "CARROT": 3, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 12}
ONGOING = {"TOMATO", "STRAWBERRY"}
SELLABLE = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    out: Dict[str, Any] = {}
    for key in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            out[key] = getattr(value, key)
        except Exception:
            pass
    return out


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


def tile_task(tile: Any, day: int) -> Optional[Tuple[int, List[Any]]]:
    if not isinstance(tile, Mapping):
        return None
    kind = str(tile.get("kind", "")).upper()
    if kind == "WEED":
        return 4, ["DIG"]
    if kind != "PLANT":
        return None
    crop = str(tile.get("crop", "")).upper()
    planted_raw = tile.get("planted_day", day)
    planted_day = day if planted_raw is None else int(planted_raw)
    age = day - planted_day
    yield_units = int(tile.get("yield_units", 0) or 0)
    watered = bool(tile.get("watered_today", False))
    danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1

    if crop in ONGOING:
        if yield_units > 0:
            return 0, ["HARVEST"]
        if not watered:
            return (1 if danger else 2), ["WATER"]
        return None

    # One-time crops are harvested only at max-yield maturity. Their initial
    # yield_units=1 is potential yield, not proof that HARVEST is legal.
    if age >= MAX_YIELD_DAY.get(crop, FIRST_YIELD_DAY.get(crop, 0)):
        return 0, ["HARVEST"]
    if not watered:
        return (1 if danger else 2), ["WATER"]
    return None


def _targets(tiles: Sequence[Sequence[Any]], day: int) -> List[Tuple[int, Position, List[Any]]]:
    out: List[Tuple[int, Position, List[Any]]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            task = tile_task(tile, day)
            if task is not None:
                priority, action = task
                out.append((priority, (x, y), action))
    return out


def _empties(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]


def _assign(
    tiles: Sequence[Sequence[Any]], position: Position,
    targets: Sequence[Tuple[int, Position, List[Any]]], empties: Sequence[Position],
    reserved: Set[Position], can_plant: bool,
) -> List[Any]:
    candidates: List[Tuple[int, int, int, int, Position, List[Any], str]] = []
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
        return action if distance == 0 else [first]

    if can_plant:
        plant_candidates: List[Tuple[int, int, int, Position, str]] = []
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
            return ["PLANT", CROP] if distance == 0 else [first]
    return ["PASS"]


def _market_orders(obs: Mapping[str, Any], farm: Mapping[str, Any], empty_count: int, unit_count: int) -> List[List[Any]]:
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seeds = _mapping(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    liquidate = day >= 29 or (day == 28 and hour >= 18)

    orders: List[List[Any]] = []
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])

    # Five hands cost only 12 total per day (1,1,2,3,5) and are the main
    # throughput multiplier for watering and harvesting a 25-tile field.
    target_hands = 0 if liquidate else 5
    current_hands = len(list(farm.get("hands", [])))
    hires_needed = max(0, target_hands - current_hands)
    for _ in range(hires_needed):
        if len(orders) < 9:
            orders.append(["HIRE"])

    if not liquidate and day <= 26 and empty_count > 0 and len(orders) < 10:
        current = int(seeds.get(CROP, 0) or 0)
        desired = min(empty_count, max(12, unit_count * 2))
        buy = max(0, desired - current)
        affordable = max(0, int(money // 20))
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
    action: Dict[str, Any] = {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}
    if not isinstance(tiles, list) or not tiles:
        return action

    day = int(obs.get("day", 0) or 0)
    seeds = int(_mapping(_mapping(obs.get("private")).get("seeds")).get(CROP, 0) or 0)
    targets = _targets(tiles, day)
    empties = _empties(tiles)
    reserved: Set[Position] = set()
    remaining = seeds

    positions = [_position(farm.get("farmer", [0, 0]))] + [_position(hand) for hand in hands]
    assigned: List[List[Any]] = []
    for position in positions:
        can_plant = day <= 26 and remaining > 0
        unit_action = _assign(tiles, position, targets, empties, reserved, can_plant)
        if unit_action[:1] == ["PLANT"]:
            remaining -= 1
        assigned.append(unit_action)

    action["farmer"] = assigned[0]
    action["hands"] = assigned[1:]
    action["market"] = _market_orders(obs, farm, len(empties), len(positions))
    return action
