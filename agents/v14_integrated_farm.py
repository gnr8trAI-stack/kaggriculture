"""V14 integrated Kaggriculture candidate.

Preserves V10 through the first melon harvest, switches to V12 only on confirmed
market stress, and adds conservative land/livestock investment. One animal is
managed at a time so crop execution is not overwhelmed by daily feed logistics.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import time

from agents.v10_market_front_runner import agent as v10_agent
from agents.v12_agent import agent as v12_agent

Position = Tuple[int, int]
TELEMETRY_SCHEMA_VERSION = "v14.0"
_RECORDS = deque(maxlen=2048)
_MODE = "v10"
_LAST_STEP = -1
_ANIMAL_PLAN: Optional[str] = None

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "product": "WOOL"},
}
MOVES = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0))


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {k: getattr(value, k) for k in ("player", "step", "day", "hour", "farms", "market", "town", "private") if hasattr(value, k)}


def _pos(value: Any) -> Position:
    if isinstance(value, Mapping):
        value = value.get("position", value.get("pos", [0, 0]))
    try:
        return int(value[0]), int(value[1])
    except Exception:
        return 0, 0


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[str]:
    if start == goal:
        return "PASS"
    q = deque([(start, None)])
    seen = {start}
    while q:
        (x, y), first = q.popleft()
        for action, dx, dy in MOVES:
            nxt = (x + dx, y + dy)
            nx, ny = nxt
            if nxt in seen or ny < 0 or ny >= len(tiles) or nx < 0 or nx >= len(tiles[ny]):
                continue
            if nxt == goal:
                return first or action
            seen.add(nxt)
            q.append((nxt, first or action))
    return None


def _shed_cells(size: int) -> Tuple[Position, ...]:
    h = size // 2
    return ((h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h))


def _route_to_shed(tiles: Sequence[Sequence[Any]], start: Position) -> List[Any]:
    cells = _shed_cells(len(tiles))
    if start in cells:
        return ["PASS"]
    choices = [(abs(start[0]-x)+abs(start[1]-y), (x, y)) for x, y in cells]
    choices.sort()
    action = _route(tiles, start, choices[0][1])
    return [action or "PASS"]


def _crop_counts(tiles: Any) -> Counter:
    result: Counter = Counter()
    if not isinstance(tiles, list):
        return result
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if isinstance(tile, Mapping) and str(tile.get("kind", tile.get("type", ""))).upper() == "PLANT":
                result[str(tile.get("crop", "")).upper()] += 1
    return result


def _structures(tiles: Any):
    result = []
    if not isinstance(tiles, list):
        return result
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, Mapping) and str(tile.get("kind", "")).upper() in ("COOP", "PASTURE"):
                result.append(((x, y), tile))
    return result


def _regime(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Dict[str, Any]:
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    opponent = _m(farms[1-player]) if isinstance(farms, list) and len(farms) > 1 else {}
    own_melons = int(_crop_counts(farm.get("tiles", [])).get("MELON", 0))
    opponent_melons = int(_crop_counts(opponent.get("tiles", [])).get("MELON", 0))
    market = _m(obs.get("market"))
    prices = _m(market.get("prices"))
    inventory = _m(market.get("inventory"))
    melon_price = float(prices.get("MELON", 250) or 250)
    melon_inventory = float(inventory.get("MELON", 10000) or 10000)
    signals = {
        "opponent_concentration": opponent_melons >= 16,
        "price_stress": melon_price <= 170,
        "inventory_stress": melon_inventory >= 10080,
        "visible_capacity_stress": (own_melons + opponent_melons) * 6 >= 240,
    }
    return {
        "own_melons": own_melons,
        "opponent_melons": opponent_melons,
        "melon_price": melon_price,
        "melon_inventory": melon_inventory,
        "risk_score": sum(bool(v) for v in signals.values()),
        "signals": signals,
    }


def _choose_animal(obs: Mapping[str, Any], day: int) -> Optional[str]:
    market = _m(obs.get("market"))
    prices = _m(market.get("prices"))
    remaining = max(0, 29 - day)
    wheat = float(prices.get("WHEAT", 25) or 25)
    fertilizer = float(prices.get("FERTILIZER", 100) or 100)
    scored = []
    for name, spec in ANIMALS.items():
        productive = max(0, remaining - int(spec["first"]) + 1)
        units = 0 if productive <= 0 else 1 + (productive - 1) // int(spec["interval"])
        product_price = float(prices.get(spec["product"], 0) or 0)
        # Fertilizer is available daily, but discount it heavily for collection labour.
        value = units * product_price + remaining * fertilizer * 0.35
        cost = float(spec["cost"]) + remaining * wheat
        scored.append((value - cost, name))
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 500 else None


def _animal_target(tiles: Sequence[Sequence[Any]]) -> Optional[Position]:
    size = len(tiles)
    preferred = list(_shed_cells(size))
    preferred += [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]
    seen = set()
    for pos in preferred:
        if pos in seen:
            continue
        seen.add(pos)
        x, y = pos
        if 0 <= y < size and 0 <= x < len(tiles[y]) and tiles[y][x] is None:
            # Prefer bought quadrants; preserve the original 5x5 crop field.
            if x >= size // 2 or y >= size // 2:
                return pos
    return None


def _inventory_total(inv: Mapping[str, Any]) -> int:
    return sum(max(0, int(v or 0)) for v in inv.values())


def _animal_override(obs: Mapping[str, Any], farm: Mapping[str, Any], plan: Optional[str]) -> Tuple[Optional[List[Any]], Dict[str, Any]]:
    if not plan:
        return None, {"stage": "none"}
    tiles = farm.get("tiles", [])
    if not isinstance(tiles, list) or not tiles:
        return None, {"stage": "no_tiles"}
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inventories = private.get("inventories", [])
    inv = _m(inventories[0]) if isinstance(inventories, list) and inventories else {}
    position = _pos(farm.get("farmer", [0, 0]))
    expected_structure = str(ANIMALS[plan]["structure"])
    structures = _structures(tiles)
    matching = [(p, t) for p, t in structures if str(t.get("kind", "")).upper() == expected_structure]
    active = next(((p, t) for p, t in matching if str(t.get("animal", "")).upper() == plan), None)
    empty = next(((p, t) for p, t in matching if not t.get("animal")), None)

    if active is not None:
        target, tile = active
        if int(inv.get(plan, 0) or 0) > 0:
            return (["PLACE", plan] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "place"}
        if not bool(tile.get("fed_today", False)):
            if int(inv.get("WHEAT", 0) or 0) > 0:
                return (["FEED"] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "feed"}
            if position in _shed_cells(len(tiles)) and int(shed.get("WHEAT", 0) or 0) > 0:
                return ["PICKUP", "WHEAT", 1], {"stage": "pickup_feed"}
            return _route_to_shed(tiles, position), {"stage": "return_for_feed"}
        if int(tile.get("yield_units", 0) or 0) > 0:
            return (["HARVEST"] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "harvest"}
        if bool(tile.get("fertilizer_available", False)):
            return (["COLLECT_FERTILIZER"] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "fertilizer"}
        if not bool(tile.get("cared_today", False)):
            return (["CARE"] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "care"}
        if _inventory_total(inv) > 0:
            if position in _shed_cells(len(tiles)):
                return ["DROP"], {"stage": "drop"}
            return _route_to_shed(tiles, position), {"stage": "return_output"}
        return None, {"stage": "maintained"}

    if empty is not None:
        target, _ = empty
        if int(inv.get(plan, 0) or 0) > 0:
            return (["PLACE", plan] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "place"}
        if int(shed.get(plan, 0) or 0) > 0:
            if position in _shed_cells(len(tiles)):
                return ["PICKUP", plan, 1], {"stage": "pickup_animal"}
            return _route_to_shed(tiles, position), {"stage": "return_for_animal"}
        return None, {"stage": "await_purchase"}

    target = _animal_target(tiles)
    if target is not None:
        build = "BUILD_COOP" if expected_structure == "COOP" else "BUILD_PASTURE"
        return ([build] if position == target else [_route(tiles, position, target) or "PASS"]), {"stage": "build", "target": target}
    return None, {"stage": "no_space"}


def _market_orders(obs: Mapping[str, Any], farm: Mapping[str, Any], base: List[List[Any]], plan: Optional[str], animal_stage: str) -> List[List[Any]]:
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))
    tiles = farm.get("tiles", [])
    occupied = sum(tile not in (None, "LOCKED") for row in tiles for tile in row) if isinstance(tiles, list) else 0
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inventories = private.get("inventories", [])
    carried = sum(int(_m(inv).get(plan, 0) or 0) for inv in inventories) if plan and isinstance(inventories, list) else 0
    active = any(str(t.get("animal", "")).upper() == plan for _, t in _structures(tiles)) if plan else False

    sells = [o for o in base if isinstance(o, list) and o[:1] == ["SELL"]]
    others = [o for o in base if isinstance(o, list) and o[:1] not in (["SELL"], ["HIRE"])]
    orders = list(sells)

    buy_land = 10 <= day <= 14 and len(unlocked) == 1 and occupied >= 20 and money >= 8000
    if buy_land:
        orders.append(["BUY_LAND"])
        # Preserve cash on the expansion turn.
        return orders[:10]

    if plan and len(unlocked) >= 2 and day <= 16:
        if animal_stage == "await_purchase" and int(shed.get(plan, 0) or 0) + carried == 0 and not active:
            orders.append(["BUY_ANIMAL", plan, 1])
        if animal_stage in ("return_for_feed", "pickup_feed") and int(shed.get("WHEAT", 0) or 0) == 0:
            orders.append(["BUY_PRODUCT", "WHEAT", 8])

    for order in others:
        if len(orders) >= 10:
            break
        orders.append(order)
    # Limit labour while livestock consumes one worker's attention.
    hire_cap = 4 if plan else 5
    hires = min(hire_cap, sum(1 for o in base if isinstance(o, list) and o[:1] == ["HIRE"]))
    for _ in range(hires):
        if len(orders) >= 10:
            break
        orders.append(["HIRE"])
    return orders[:10]


def reset_state() -> None:
    global _MODE, _LAST_STEP, _ANIMAL_PLAN
    _MODE = "v10"
    _LAST_STEP = -1
    _ANIMAL_PLAN = None
    _RECORDS.clear()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    records = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return records


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _MODE, _LAST_STEP, _ANIMAL_PLAN
    started = time.perf_counter()
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = _m(farms[player])
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    regime = _regime(obs, farm)
    previous_mode = _MODE
    # Preserve the proven first melon cycle; require two independent stress signals.
    if _MODE == "v10" and day >= 10 and regime["risk_score"] >= 2:
        _MODE = "v12"

    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))
    if _ANIMAL_PLAN is None and len(unlocked) >= 2 and 10 <= day <= 16:
        _ANIMAL_PLAN = _choose_animal(obs, day)

    chosen = v10_agent if _MODE == "v10" else v12_agent
    base = dict(chosen(obs, configuration))
    farmer_override, animal_info = _animal_override(obs, farm, _ANIMAL_PLAN)
    farmer_action = farmer_override if farmer_override is not None else base.get("farmer", ["PASS"])
    market = _market_orders(obs, farm, list(base.get("market", [])), _ANIMAL_PLAN, str(animal_info.get("stage", "none")))
    legal = {"farmer": farmer_action, "hands": base.get("hands", []), "market": market}
    _RECORDS.append({
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "step": step, "day": day, "hour": hour,
        "mode": _MODE, "switched_this_turn": previous_mode != _MODE,
        "regime": regime,
        "land": {"unlocked": unlocked},
        "animal": {"plan": _ANIMAL_PLAN, **animal_info},
        "decision_duration_ms": (time.perf_counter() - started) * 1000.0,
        "action": legal,
    })
    return legal
