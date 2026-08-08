"""V16 challenger: exact V15 economics plus a conservative farm-health governor.

V15 remains the champion. This wrapper only changes actions when farm health is
at risk. It does not replace V15 crop economics, market switching, livestock,
or normal workload routing.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from agents.v15_champion import agent as _v15_agent

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        k: getattr(value, k)
        for k in ("player", "step", "day", "hour", "farms", "market", "town", "private")
        if hasattr(value, k)
    }


def _pos(value: Any) -> Position:
    if isinstance(value, Mapping):
        value = value.get("position", value.get("pos", [0, 0]))
    try:
        return int(value[0]), int(value[1])
    except Exception:
        return (0, 0)


def _kind(tile: Any) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, Mapping):
        return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _inside(tiles: Sequence[Sequence[Any]], pos: Position) -> bool:
    x, y = pos
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
    if start == goal:
        return (0, "PASS")
    queue = deque([(start, 0, None)])
    seen = {start}
    while queue:
        (x, y), distance, first = queue.popleft()
        for action, dx, dy in MOVES:
            nxt = (x + dx, y + dy)
            if nxt in seen or not _inside(tiles, nxt):
                continue
            seen.add(nxt)
            initial = first or action
            if nxt == goal:
                return (distance + 1, initial)
            queue.append((nxt, distance + 1, initial))
    return None


def _health(tiles: Sequence[Sequence[Any]]) -> Dict[str, Any]:
    usable = weeds = plants = unwatered = danger = 0
    weed_positions: List[Position] = []
    danger_positions: List[Position] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            kind = _kind(tile)
            if kind == "LOCKED":
                continue
            usable += 1
            if kind == "WEED":
                weeds += 1
                weed_positions.append((x, y))
            elif kind == "PLANT" and isinstance(tile, Mapping):
                plants += 1
                watered = bool(tile.get("watered_today", False))
                if not watered:
                    unwatered += 1
                    if int(tile.get("consecutive_unwatered", 0) or 0) >= 1:
                        danger += 1
                        danger_positions.append((x, y))
    ratio = weeds / max(1, usable)
    return {
        "usable": usable,
        "weeds": weeds,
        "weed_ratio": ratio,
        "plants": plants,
        "unwatered": unwatered,
        "danger": danger,
        "weed_positions": weed_positions,
        "danger_positions": danger_positions,
    }


def _nearest_cleanup(
    tiles: Sequence[Sequence[Any]],
    start: Position,
    weeds: Sequence[Position],
    reserved: Set[Position],
) -> Optional[List[Any]]:
    choices = []
    for target in weeds:
        if target in reserved:
            continue
        route = _route(tiles, start, target)
        if route is None:
            continue
        distance, first = route
        choices.append((distance, target[1], target[0], target, first))
    if not choices:
        return None
    choices.sort()
    distance, _, _, target, first = choices[0]
    reserved.add(target)
    return ["DIG"] if distance == 0 else [first]


def _is_discretionary(action: Any) -> bool:
    if not isinstance(action, list) or not action:
        return True
    return str(action[0]).upper() in {
        "PASS", "PLANT", "BUILD_COOP", "BUILD_PASTURE"
    }


def _guard_market(
    orders: Any,
    *,
    unhealthy: bool,
    late_plant_risk: bool,
    weeds: int,
    danger: int,
    hands: int,
    backlog: int,
    hour: int,
) -> List[List[Any]]:
    clean: List[List[Any]] = []
    for raw in orders if isinstance(orders, list) else []:
        if not isinstance(raw, list) or not raw:
            continue
        op = str(raw[0]).upper()
        if unhealthy and op in {"BUY_LAND", "BUY_ANIMAL"}:
            continue
        if (unhealthy or late_plant_risk) and op == "BUY_SEED":
            continue
        clean.append(list(raw))

    # V15 already sizes labour from crop workload. Add at most two emergency
    # hands only when health backlog materially exceeds available units.
    units = hands + 1
    emergency_need = max(0, backlog - 3 * units)
    if (weeds >= 2 or danger > 0) and emergency_need > 0 and hour <= 18:
        for _ in range(min(2, emergency_need, max(0, 10 - len(clean)))):
            clean.append(["HIRE"])
    return clean[:10]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    base = dict(_v15_agent(observation, configuration))
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return base
    farm = _m(farms[player])
    tiles = farm.get("tiles") or []
    if not isinstance(tiles, list) or not tiles:
        return base

    hour = int(obs.get("hour", 0) or 0)
    hands = list(farm.get("hands") or [])
    health = _health(tiles)

    # A healthy elite farm normally carries almost no weeds. Do not wait for a
    # runaway. The hard trigger is deliberately conservative: >=2 weeds or 8%.
    unhealthy = health["danger"] > 0 or health["weeds"] >= 2 or health["weed_ratio"] >= 0.08

    # Newly planted seeds already count as one missed watering day. Late
    # discretionary planting is therefore dangerous when work remains.
    late_plant_risk = hour >= 19 or (
        hour >= 16 and (health["unwatered"] + health["weeds"]) > len(hands) + 1
    )

    farmer_action = list(base.get("farmer", ["PASS"]))
    hand_actions = [list(a) if isinstance(a, list) else ["PASS"] for a in base.get("hands", [])]
    actions = [farmer_action] + hand_actions
    positions = [_pos(farm.get("farmer", [0, 0]))] + [_pos(h) for h in hands]

    # Never override V15's watering/harvest/feed/care/logistics. Only redirect
    # discretionary actions into cleanup once immediate plant-danger work is
    # already being handled by V15.
    if health["weeds"] > 0:
        reserved: Set[Position] = set()
        for i, action in enumerate(actions):
            if i >= len(positions) or not _is_discretionary(action):
                continue
            cleanup = _nearest_cleanup(tiles, positions[i], health["weed_positions"], reserved)
            if cleanup is not None:
                actions[i] = cleanup
            if len(reserved) >= health["weeds"]:
                break

    # Stop discretionary planting late in the day even before weeds appear.
    if late_plant_risk:
        for i, action in enumerate(actions):
            if action[:1] == ["PLANT"]:
                actions[i] = ["PASS"]

    backlog = health["unwatered"] + health["weeds"]
    market = _guard_market(
        base.get("market", []),
        unhealthy=unhealthy,
        late_plant_risk=late_plant_risk,
        weeds=health["weeds"],
        danger=health["danger"],
        hands=len(hands),
        backlog=backlog,
        hour=hour,
    )

    return {
        "farmer": actions[0] if actions else farmer_action,
        "hands": actions[1:],
        "market": market,
    }
