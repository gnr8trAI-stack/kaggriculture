"""Replay-informed Kaggriculture V20 challenger.

This policy keeps the stable movement/task reservation logic from V2 but adds
an explicit growth/production/liquidation policy learned from public replay
patterns: winners scale land and labor earlier, then sustain denser productive
assets instead of remaining capped at a small farm.

The implementation is intentionally defensive. Unknown market/town schemas are
inspected conservatively and only actions whose names can be inferred from the
observation are emitted; otherwise the agent falls back to the validated V2
surface (movement, servicing, seed purchases, selling).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)
CROPS = ("STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT")
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def _as_dict(observation: Any) -> Dict[str, Any]:
    if isinstance(observation, dict):
        return observation
    out: Dict[str, Any] = {}
    for name in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            out[name] = getattr(observation, name)
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


def _kind(tile: Any) -> Optional[str]:
    if not isinstance(tile, Mapping):
        return None
    value = tile.get("kind", tile.get("type"))
    return str(value).upper() if value is not None else None


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


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
    if start == goal:
        return 0, "PASS"
    q = deque([(start, 0, None)])
    seen = {start}
    while q:
        pos, dist, first = q.popleft()
        for action, nxt in _neighbours(tiles, pos):
            if nxt in seen:
                continue
            seen.add(nxt)
            first_action = first or action
            if nxt == goal:
                return dist + 1, first_action
            q.append((nxt, dist + 1, first_action))
    return None


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


def _priority(tile: Any, day: int) -> Optional[int]:
    task = _tile_task(tile)
    if task is None:
        return None
    # Harvest is always urgent. Feed/water outrank care so production cycles do
    # not stall. Weeds become relatively less important late in the season.
    base = {"HARVEST": 0, "FEED": 1, "WATER": 1, "CARE": 2,
            "COLLECT_FERTILIZER": 3, "DIG": 5}[task[0]]
    if task[0] == "DIG" and day >= 22:
        base += 3
    return base


def _targets(tiles: Sequence[Sequence[Any]], day: int) -> List[Tuple[int, Position, List[Any]]]:
    out = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            p = _priority(tile, day)
            t = _tile_task(tile)
            if p is not None and t is not None:
                out.append((p, (x, y), t))
    return out


def _empty_tiles(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]


def _seed_count(private: Mapping[str, Any], crop: str) -> int:
    try:
        return int(private.get("seeds", {}).get(crop, 0) or 0)
    except Exception:
        return 0


def _best_crop(obs: Mapping[str, Any], private: Mapping[str, Any], day: int) -> str:
    # Prefer high-value crops when we already hold seed. Price-aware tie-breaks
    # are used when the market exposes a product->price mapping.
    prices = obs.get("market", {}).get("prices", {}) if isinstance(obs.get("market", {}), Mapping) else {}
    viable = [c for c in CROPS if _seed_count(private, c) > 0]
    if not viable:
        return "WHEAT"
    if isinstance(prices, Mapping):
        def score(c: str) -> Tuple[float, int]:
            try:
                p = float(prices.get(c, 0) or 0)
            except Exception:
                p = 0.0
            # modest lateness penalty for slower speculative crops
            late_penalty = 0.7 if day >= 23 and c in ("STRAWBERRY", "MELON") else 1.0
            return p * late_penalty, -CROPS.index(c)
        return max(viable, key=score)
    return viable[0]


def _assign(tiles: Sequence[Sequence[Any]], pos: Position,
            targets: Sequence[Tuple[int, Position, List[Any]]], reserved: Set[Position],
            crop: Optional[str]) -> List[Any]:
    candidates = []
    for priority, target, task in targets:
        if target in reserved:
            continue
        r = _route(tiles, pos, target)
        if r is not None:
            dist, first = r
            candidates.append((priority, dist, target, task, first))
    if candidates:
        candidates.sort(key=lambda z: (z[0], z[1], z[2][1], z[2][0]))
        _, dist, target, task, first = candidates[0]
        reserved.add(target)
        return task if dist == 0 else [first]

    if crop:
        candidates2 = []
        for target in _empty_tiles(tiles):
            if target in reserved:
                continue
            r = _route(tiles, pos, target)
            if r is not None:
                dist, first = r
                candidates2.append((dist, target, first))
        if candidates2:
            candidates2.sort(key=lambda z: (z[0], z[1][1], z[1][0]))
            dist, target, first = candidates2[0]
            reserved.add(target)
            return ["PLANT", crop] if dist == 0 else [first]
    return ["PASS"]


def _count_unlocked_tiles(tiles: Sequence[Sequence[Any]]) -> int:
    n = 0
    for row in tiles:
        for tile in row:
            if tile != "LOCKED" and _kind(tile) != "LOCKED":
                n += 1
    return n


def _sell_orders(private: Mapping[str, Any], liquidate: bool, threshold: int) -> List[List[Any]]:
    shed = private.get("shed", {}) if isinstance(private, Mapping) else {}
    orders = []
    if not isinstance(shed, Mapping):
        return orders
    for product in PRODUCTS:
        try:
            qty = int(shed.get(product, 0) or 0)
        except Exception:
            qty = 0
        if qty > 0 and (liquidate or qty >= threshold):
            orders.append(["SELL", product, qty])
            if len(orders) >= 10:
                break
    return orders


def _available_action_names(obj: Any) -> Set[str]:
    names: Set[str] = set()
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            names.add(str(k).upper())
            names |= _available_action_names(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            if isinstance(v, str):
                names.add(v.upper())
            else:
                names |= _available_action_names(v)
    return names


def _growth_orders(obs: Mapping[str, Any], farm: Mapping[str, Any], private: Mapping[str, Any],
                   day: int, hour: int, current_orders: int) -> List[List[Any]]:
    """Emit growth orders only when their action names are exposed by schema.

    This avoids guessing unsupported action strings. Once real replay fixtures
    expose the exact town action contract, these branches activate automatically.
    """
    if day >= 24 or current_orders >= 10:
        return []
    town = obs.get("town", {})
    market = obs.get("market", {})
    names = _available_action_names(town) | _available_action_names(market)
    money = float(farm.get("money", 0) or 0)
    hands = len(list(farm.get("hands", [])))
    tiles = farm.get("tiles", [])
    unlocked = _count_unlocked_tiles(tiles) if tiles else 0
    out: List[List[Any]] = []

    # Replay-derived targets: reach meaningful parallelism and unlock a third
    # land block early rather than plateauing at ~2 land / ~7 workers.
    target_hands = 4 if day < 5 else 7 if day < 10 else 10
    target_land_blocks = 2 if day < 6 else 3

    # We deliberately require the exact verb to appear somewhere in public
    # state before using it. Cost checks remain conservative because schemas vary.
    if hands < target_hands and "HIRE_HAND" in names and money > 500:
        out.append(["HIRE_HAND", 1])
    elif hands < target_hands and "HIRE" in names and money > 500:
        out.append(["HIRE", "HAND", 1])

    # Approximate land blocks from unlocked area. Common boards are 10x10; this
    # target simply detects obvious under-expansion and is harmless if verb absent.
    estimated_blocks = max(1, (unlocked + 24) // 25)
    if estimated_blocks < target_land_blocks and money > 1000:
        if "BUY_LAND" in names:
            out.append(["BUY_LAND", 1])
        elif "UNLOCK_LAND" in names:
            out.append(["UNLOCK_LAND", 1])

    return out[: max(0, 10 - current_orders)]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _as_dict(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, Sequence) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    if not isinstance(farm, Mapping):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    tiles = farm.get("tiles", [])
    hands_raw = list(farm.get("hands", []))
    action = {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands_raw], "market": []}
    if not tiles:
        return action

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    private = obs.get("private", {}) if isinstance(obs.get("private", {}), Mapping) else {}
    crop = _best_crop(obs, private, day)
    remaining = _seed_count(private, crop)
    targets = _targets(tiles, day)
    reserved: Set[Position] = set()

    # Near season end, stop opening new production cycles.
    allow_plant = day < 25 or (day == 25 and hour < 8)

    farmer_pos = _position(farm.get("farmer", [0, 0]))
    action["farmer"] = _assign(tiles, farmer_pos, targets, reserved,
                                crop if allow_plant and remaining > 0 else None)
    if action["farmer"][:1] == ["PLANT"]:
        remaining -= 1

    for i, hand in enumerate(hands_raw):
        action["hands"][i] = _assign(tiles, _position(hand), targets, reserved,
                                      crop if allow_plant and remaining > 0 else None)
        if action["hands"][i][:1] == ["PLANT"]:
            remaining -= 1

    liquidate = day >= 28 or (day == 27 and hour >= 18)
    # Faster inventory recycling during growth; full liquidation at the end.
    threshold = 5 if day < 20 else 3
    orders = _sell_orders(private, liquidate, threshold)

    # Replenish the chosen crop proportional to active workers. This converts
    # labor expansion into actual productive throughput rather than idle hands.
    desired_seed_buffer = max(4, 2 + len(hands_raw))
    held = _seed_count(private, crop)
    money = float(farm.get("money", 0) or 0)
    if allow_plant and held < desired_seed_buffer and len(orders) < 10:
        qty = desired_seed_buffer - held
        # Keep a reserve so growth purchases are not starved by seed buying.
        reserve = 1200.0 if day < 12 else 500.0
        if money > reserve + 10.0 * qty:
            orders.append(["BUY_SEED", crop, qty])

    orders.extend(_growth_orders(obs, farm, private, day, hour, len(orders)))
    action["market"] = orders[:10]
    return action
