"""V11 adaptive Kaggriculture planner.

This candidate replaces V10's fixed melon policy with:
- live crop economics using current prices, lifecycle and remaining season;
- opponent exposure penalties from the visible farm;
- dynamic planting cutoffs;
- workload-based daily hiring;
- reservation-aware shortest-path task assignment;
- early inventory return and continuous liquidation;
- structured decision telemetry removed by Kaggle when not consumed.

The module is dependency-free and designed to be bundled as a standalone
submission after benchmark promotion.
"""
from collections import Counter, deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0),
)

CROPS = {
    "WHEAT": {"seed": 10, "base": 25, "first": 2, "peak": 4, "yield": 4, "ongoing": False},
    "CARROT": {"seed": 20, "base": 35, "first": 2, "peak": 3, "yield": 3, "ongoing": False},
    "TOMATO": {"seed": 50, "base": 60, "first": 8, "peak": 11, "yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "base": 120, "first": 10, "peak": 16, "yield": 4, "ongoing": True},
    "MELON": {"seed": 80, "base": 250, "first": 10, "peak": 10, "yield": 6, "ongoing": False},
}
SELLABLE = tuple(CROPS) + ("EGG", "MILK", "WOOL", "FERTILIZER")
TOTAL_DAYS = 30
ENDGAME_BUFFER_DAYS = 2
MAX_HANDS = 7
DROP_FROM_HOUR = 8


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
    return day - (day if raw is None else int(raw))


def _inventory_total(inventory: Mapping[str, Any]) -> int:
    return sum(max(0, int(value or 0)) for value in inventory.values())


def _crop_counts(tiles: Sequence[Sequence[Any]]) -> Counter:
    counts: Counter = Counter()
    for row in tiles:
        for tile in row:
            if _kind(tile) == "PLANT" and isinstance(tile, Mapping):
                counts[str(tile.get("crop", "")).upper()] += 1
    return counts


def _remaining_days(day: int, hour: int) -> float:
    return max(0.0, TOTAL_DAYS - day - hour / 24.0)


def _crop_score(
    crop: str,
    price: float,
    own_count: int,
    opponent_count: int,
    remaining_days: float,
    shops: Sequence[str],
) -> float:
    spec = CROPS[crop]
    required = spec["peak"] + ENDGAME_BUFFER_DAYS
    if remaining_days < required:
        return float("-inf")

    gross = price * spec["yield"]
    margin = gross - spec["seed"]
    velocity = margin / max(1.0, spec["peak"])

    # Shared-market crowding. Premium crops receive a stronger penalty because
    # the official curves collapse quickly under gluts.
    crowd = own_count + opponent_count
    premium = 1.8 if crop in {"MELON", "STRAWBERRY"} else 1.0
    crowd_penalty = premium * crowd * max(1.0, spec["base"] * 0.025)

    # Current price already reflects both players' previous sales; reward
    # scarcity and penalize prices materially below equilibrium.
    price_ratio = price / max(1.0, spec["base"])
    market_factor = max(0.15, min(1.6, price_ratio))

    demand_bonus = 0.0
    joined = " ".join(str(x).upper() for x in shops)
    if crop == "WHEAT" and any(x in joined for x in ("BAKERY", "PIZZA", "BRUNCH", "ICE_CREAM")):
        demand_bonus += 8.0
    if crop == "CARROT" and "PET" in joined:
        demand_bonus += 12.0
    if crop == "TOMATO" and ("PIZZA" in joined or "FARMERS" in joined):
        demand_bonus += 10.0
    if crop == "STRAWBERRY" and any(x in joined for x in ("BRUNCH", "ICE_CREAM", "SMOOTHIE", "FARMERS")):
        demand_bonus += 14.0

    return velocity * market_factor + demand_bonus - crowd_penalty


def choose_crop(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Tuple[Optional[str], Dict[str, float]]:
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    opponent = _mapping(farms[1 - player]) if isinstance(farms, list) and len(farms) > 1 else {}
    own_counts = _crop_counts(farm.get("tiles", []))
    opponent_counts = _crop_counts(opponent.get("tiles", []))
    prices = _mapping(_mapping(obs.get("market")).get("prices"))
    shops = list(_mapping(obs.get("town")).get("unlocked_shops", []))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    remaining = _remaining_days(day, hour)

    scores = {
        crop: _crop_score(
            crop,
            float(prices.get(crop, spec["base"]) or spec["base"]),
            own_counts[crop],
            opponent_counts[crop],
            remaining,
            shops,
        )
        for crop, spec in CROPS.items()
    }
    legal = [(score, crop) for crop, score in scores.items() if score != float("-inf")]
    if not legal:
        return None, scores
    legal.sort(reverse=True)
    return legal[0][1], scores


def _shed_cells(board_size: int) -> Tuple[Position, Position, Position, Position]:
    half = board_size // 2
    return ((half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half))


def _return_to_shed(tiles: Sequence[Sequence[Any]], position: Position) -> List[Any]:
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


def _tile_task(tile: Any, day: int) -> Optional[Tuple[int, List[Any]]]:
    kind = _kind(tile)
    if kind == "WEED":
        return 5, ["DIG"]
    if kind != "PLANT" or not isinstance(tile, Mapping):
        return None
    crop = str(tile.get("crop", "")).upper()
    spec = CROPS.get(crop)
    if spec is None:
        return None
    watered = bool(tile.get("watered_today", False))
    danger = int(tile.get("consecutive_unwatered", 0) or 0) >= 1
    yield_units = int(tile.get("yield_units", 0) or 0)
    age = _age(tile, day)
    if not watered and danger:
        return 0, ["WATER"]
    if yield_units > 0 and age >= spec["peak"]:
        return 1, ["HARVEST"]
    if not watered:
        return 2, ["WATER"]
    return None


def _targets(tiles: Sequence[Sequence[Any]], day: int) -> List[Tuple[int, Position, List[Any]]]:
    result: List[Tuple[int, Position, List[Any]]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            task = _tile_task(tile, day)
            if task is not None:
                priority, action = task
                result.append((priority, (x, y), action))
    return result


def _empties(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]


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
        choices.append((priority, distance, target[1], target[0], target, action, first))
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
    crop: str,
) -> List[Any]:
    choices: List[Tuple[int, int, int, Position, str]] = []
    for target in empties:
        if target in reserved:
            continue
        route = _route(tiles, position, target)
        if route is not None:
            distance, first = route
            choices.append((distance, target[1], target[0], target, first))
    if not choices:
        return ["PASS"]
    choices.sort()
    distance, _, _, target, first = choices[0]
    reserved.add(target)
    return ["PLANT", crop] if distance == 0 else [first]


def _target_hands(tiles: Sequence[Sequence[Any]], day: int) -> int:
    planted = 0
    urgent = 0
    for row in tiles:
        for tile in row:
            if _kind(tile) == "PLANT":
                planted += 1
                if isinstance(tile, Mapping) and (
                    not bool(tile.get("watered_today", False))
                    or int(tile.get("yield_units", 0) or 0) > 0
                ):
                    urgent += 1
    # One farmer plus hands. Increase labour only when daily workload justifies it.
    desired_units = max(2, min(MAX_HANDS + 1, 1 + (max(planted, urgent) + 4) // 5))
    return desired_units - 1


def _unit_action(
    tiles: Sequence[Sequence[Any]],
    day: int,
    hour: int,
    position: Position,
    inventory: Mapping[str, Any],
    targets: Sequence[Tuple[int, Position, List[Any]]],
    empties: Sequence[Position],
    reserved: Set[Position],
    crop: Optional[str],
    can_plant: bool,
) -> List[Any]:
    urgent = _best_task(tiles, position, targets, reserved, max_priority=0)
    if urgent is not None:
        return urgent
    load = _inventory_total(inventory)
    if load > 0 and hour >= DROP_FROM_HOUR:
        return _return_to_shed(tiles, position)
    regular = _best_task(tiles, position, targets, reserved)
    if regular is not None:
        return regular
    if load > 0:
        return _return_to_shed(tiles, position)
    if can_plant and crop is not None:
        return _plant_action(tiles, position, empties, reserved, crop)
    return ["PASS"]


def _market_orders(
    obs: Mapping[str, Any],
    farm: Mapping[str, Any],
    crop: Optional[str],
    empty_count: int,
    target_hands: int,
    unit_count: int,
) -> List[List[Any]]:
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seeds = _mapping(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands", []))
    orders: List[List[Any]] = []

    # Sell continuously. For premium goods this intentionally captures the
    # high-price part of the curve before later market gluts.
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])

    liquidate = day >= 28 or (day == 27 and hour >= 18)
    if not liquidate:
        for _ in range(max(0, target_hands - len(hands))):
            if len(orders) >= 9:
                break
            orders.append(["HIRE"])

    if crop is not None and not liquidate and empty_count > 0 and len(orders) < 10:
        spec = CROPS[crop]
        remaining = _remaining_days(day, hour)
        if remaining >= spec["peak"] + ENDGAME_BUFFER_DAYS:
            current = int(seeds.get(crop, 0) or 0)
            desired = min(empty_count, max(8, unit_count * 2))
            buy = max(0, desired - current)
            affordable = max(0, int(money // spec["seed"]))
            buy = min(buy, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
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
        "farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []
    }
    if not isinstance(tiles, list) or not tiles:
        return result

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    crop, scores = choose_crop(obs, farm)
    private = _mapping(obs.get("private"))
    seed_map = _mapping(private.get("seeds"))
    inventories = private.get("inventories", [])
    if not isinstance(inventories, list):
        inventories = []

    targets = _targets(tiles, day)
    empties = _empties(tiles)
    positions = [_position(farm.get("farmer", [0, 0]))] + [_position(hand) for hand in hands]
    target_hands = _target_hands(tiles, day)
    remaining_seeds = int(seed_map.get(crop, 0) or 0) if crop else 0
    reserved: Set[Position] = set()
    assigned: List[List[Any]] = []

    for index, position in enumerate(positions):
        inventory = _mapping(inventories[index]) if index < len(inventories) else {}
        action = _unit_action(
            tiles, day, hour, position, inventory, targets, empties, reserved,
            crop, crop is not None and remaining_seeds > 0,
        )
        if action[:1] == ["PLANT"]:
            remaining_seeds -= 1
        assigned.append(action)

    result["farmer"] = assigned[0]
    result["hands"] = assigned[1:]
    result["market"] = _market_orders(
        obs, farm, crop, len(empties), target_hands, len(positions)
    )
    result["_telemetry"] = {
        "selected_crop": crop,
        "crop_scores": scores,
        "target_hands": target_hands,
        "remaining_days": _remaining_days(day, hour),
    }
    return result
