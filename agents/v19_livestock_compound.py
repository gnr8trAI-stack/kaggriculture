"""V19 controlled livestock-compounding challenger.

V19 keeps V15's proven opening and V18's two validated structural changes:
- unlock one additional quadrant from historical NW saturation, not a transient
  post-harvest occupancy snapshot;
- switch to V15's adaptive V12 crop/workload engine once scale begins (or by
  day 18) so production does not retire with V10's day-18 melon cutoff.

The only new economic mutation is a deliberately small livestock sidecar:
- cows only for this experiment;
- stage 2 cows first, then at most 4 when the farm remains healthy;
- pastures only outside the original NW crop quadrant;
- two late-index hands form the livestock crew so V15's first units retain the
  highest-priority crop work selected by its reservation-aware scheduler;
- feed survival is mandatory; CARE, harvest and fertilizer are serviced only
  while capacity permits;
- new livestock freezes under crop-danger / weed stress.

This is a challenger, not a promoted submission. It must break the absolute
money ceiling and beat V15/V18 in CI before packaging is allowed.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from agents import v15_champion as _v15

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)

# V18 scale unlock parameters.
LAND_COST_FIRST = 1000
POST_LAND_CASH_RESERVE = 2500
MIN_CASH_TO_EXPAND = LAND_COST_FIRST + POST_LAND_CASH_RESERVE
MIN_PEAK_NW_PRODUCTIVE = 20
EXPAND_MIN_DAY = 10
EXPAND_MAX_DAY = 20
FORCE_ADAPTIVE_DAY = 18
MAX_WEEDS_TO_EXPAND = 4
MAX_DANGER_TO_EXPAND = 2

# V19 controlled livestock parameters.
ANIMAL = "COW"
ANIMAL_COST = 400
INITIAL_COW_TARGET = 2
MAX_COW_TARGET = 4
START_COWS_MAX_DAY = 17
MIN_CASH_FOR_TWO = 1500
MIN_CASH_FOR_FOUR = 2500
MIN_HANDS_WITH_COWS = 6
MAX_HANDS_WITH_COWS = 7
FEED_BUFFER_PER_COW = 2
MAX_WEED_RATIO_FOR_GROWTH = 0.12
MAX_DANGER_FOR_GROWTH = 2
MAX_WEED_RATIO_FOR_FULL_SERVICE = 0.18

_LAST_STEP = -1
_PEAK_NW_PRODUCTIVE = 0
_FORCED_ADAPTIVE = False
_RECORDS = deque(maxlen=4096)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        k: getattr(value, k)
        for k in ("player", "step", "day", "hour", "farms", "private", "market", "town")
        if hasattr(value, k)
    }


def _kind(tile: Any) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, Mapping):
        return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _pos(value: Any) -> Position:
    if isinstance(value, Mapping):
        value = value.get("position", value.get("pos", [0, 0]))
    try:
        return int(value[0]), int(value[1])
    except Exception:
        return (0, 0)


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


def _shed_cells(size: int) -> Tuple[Position, ...]:
    half = size // 2
    return ((half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half))


def _nearest_route(
    tiles: Sequence[Sequence[Any]], start: Position, goals: Sequence[Position]
) -> Optional[Tuple[int, Position, str]]:
    choices: List[Tuple[int, int, int, Position, str]] = []
    for goal in goals:
        route = _route(tiles, start, goal)
        if route is None:
            continue
        distance, first = route
        choices.append((distance, goal[1], goal[0], goal, first))
    if not choices:
        return None
    choices.sort()
    distance, _, _, goal, first = choices[0]
    return (distance, goal, first)


def _inventory_total(inv: Mapping[str, Any]) -> int:
    return sum(max(0, int(v or 0)) for v in inv.values())


def _farm_health(farm: Mapping[str, Any]) -> Dict[str, int | float]:
    tiles = farm.get("tiles") or []
    unlocked = weeds = danger = productive = nw_productive = 0
    if not isinstance(tiles, list) or not tiles:
        return {
            "unlocked": 0, "weeds": 0, "danger": 0,
            "productive": 0, "nw_productive": 0, "weed_ratio": 0.0,
        }
    half = len(tiles) // 2
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            kind = _kind(tile)
            if kind == "LOCKED":
                continue
            unlocked += 1
            if kind == "WEED":
                weeds += 1
            if kind in {"PLANT", "COOP", "PASTURE"}:
                productive += 1
                if x < half and y < half:
                    nw_productive += 1
            if kind == "PLANT" and isinstance(tile, Mapping):
                if (not bool(tile.get("watered_today", False)) and
                        int(tile.get("consecutive_unwatered", 0) or 0) >= 1):
                    danger += 1
    return {
        "unlocked": unlocked,
        "weeds": weeds,
        "danger": danger,
        "productive": productive,
        "nw_productive": nw_productive,
        "weed_ratio": weeds / max(1, unlocked),
    }


def _pastures(tiles: Any) -> List[Tuple[Position, Mapping[str, Any]]]:
    result: List[Tuple[Position, Mapping[str, Any]]] = []
    if not isinstance(tiles, list):
        return result
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if isinstance(tile, Mapping) and _kind(tile) == "PASTURE":
                result.append(((x, y), tile))
    return result


def _active_cows(tiles: Any) -> List[Tuple[Position, Mapping[str, Any]]]:
    return [
        (pos, tile) for pos, tile in _pastures(tiles)
        if str(tile.get("animal", "")).upper() == ANIMAL
    ]


def _empty_pastures(tiles: Any) -> List[Position]:
    return [pos for pos, tile in _pastures(tiles) if not tile.get("animal")]


def _cow_count(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> int:
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inventories = private.get("inventories", [])
    carried = 0
    if isinstance(inventories, list):
        carried = sum(int(_m(inv).get(ANIMAL, 0) or 0) for inv in inventories)
    return len(_active_cows(farm.get("tiles", []))) + int(shed.get(ANIMAL, 0) or 0) + carried


def _outside_nw_empty(tiles: Any) -> List[Position]:
    if not isinstance(tiles, list) or not tiles:
        return []
    half = len(tiles) // 2
    sheds = set(_shed_cells(len(tiles)))
    result: List[Tuple[int, int, int, Position]] = []
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if tile is not None or (x < half and y < half) or (x, y) in sheds:
                continue
            # tile=None means unlocked empty. Keep livestock outside NW and
            # prefer short service routes to the central shed.
            distance = min(abs(x-sx) + abs(y-sy) for sx, sy in sheds)
            result.append((distance, y, x, (x, y)))
    result.sort()
    return [pos for _, _, _, pos in result]


def _growth_healthy(health: Mapping[str, Any]) -> bool:
    return (
        float(health.get("weed_ratio", 0.0) or 0.0) <= MAX_WEED_RATIO_FOR_GROWTH
        and int(health.get("danger", 0) or 0) <= MAX_DANGER_FOR_GROWTH
    )


def _cow_target(
    day: int, money: float, health: Mapping[str, Any], unlocked_count: int,
    cow_count: int, active_count: int,
) -> int:
    if unlocked_count < 2 or day > START_COWS_MAX_DAY or not _growth_healthy(health):
        return cow_count
    target = cow_count
    if money >= MIN_CASH_FOR_TWO:
        target = max(target, INITIAL_COW_TARGET)
    if active_count >= INITIAL_COW_TARGET and money >= MIN_CASH_FOR_FOUR:
        target = max(target, MAX_COW_TARGET)
    return min(MAX_COW_TARGET, target)


def _switch_v15_to_adaptive() -> None:
    if hasattr(_v15, "_MODE"):
        _v15._MODE = "v12"


def _route_or_action(
    tiles: Sequence[Sequence[Any]], position: Position, target: Position, action: List[Any]
) -> List[Any]:
    if position == target:
        return action
    route = _route(tiles, position, target)
    return [route[1]] if route is not None else ["PASS"]


def _to_shed_action(
    tiles: Sequence[Sequence[Any]], position: Position, action: List[Any]
) -> List[Any]:
    sheds = _shed_cells(len(tiles))
    if position in sheds:
        return action
    route = _nearest_route(tiles, position, sheds)
    return [route[2]] if route is not None else ["PASS"]


def _livestock_action(
    obs: Mapping[str, Any], farm: Mapping[str, Any], unit_index: int,
    reserved: Set[Position], target_cows: int, full_service: bool,
) -> Tuple[Optional[List[Any]], str]:
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    positions = [_pos(farm.get("farmer", [0, 0]))] + [_pos(h) for h in hands]
    if unit_index >= len(positions) or not isinstance(tiles, list) or not tiles:
        return None, "no_unit"
    position = positions[unit_index]

    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inventories = private.get("inventories", [])
    inv = _m(inventories[unit_index]) if isinstance(inventories, list) and unit_index < len(inventories) else {}

    active = _active_cows(tiles)
    empty_pastures = _empty_pastures(tiles)
    cow_count = _cow_count(obs, farm)

    # Complete animal placement before optional work.
    if int(inv.get(ANIMAL, 0) or 0) > 0 and empty_pastures:
        choices = [p for p in empty_pastures if p not in reserved]
        route = _nearest_route(tiles, position, choices)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["PLACE", ANIMAL]), "place_cow"

    # If the unit carries wheat, feed the nearest unfed cow first. Feeding every
    # day preserves care bonuses and mirrors the high-performing 4-cow replay.
    if int(inv.get("WHEAT", 0) or 0) > 0:
        unfed = [p for p, t in active if not bool(t.get("fed_today", False)) and p not in reserved]
        route = _nearest_route(tiles, position, unfed)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["FEED"]), "feed"

    # Harvested milk/fertilizer must reach the shed so V15's continuous SELL
    # policy can monetize it. Wheat-only inventory is retained for feeding.
    output_load = sum(
        int(v or 0) for k, v in inv.items()
        if str(k).upper() not in {"WHEAT", ANIMAL}
    )
    if output_load > 0:
        return _to_shed_action(tiles, position, ["DROP"]), "return_output"

    # Survival/service tasks on active cows.
    unfed = [(p, t) for p, t in active if not bool(t.get("fed_today", False)) and p not in reserved]
    if unfed:
        wheat_available = int(shed.get("WHEAT", 0) or 0)
        if wheat_available > 0:
            return _to_shed_action(
                tiles, position, ["PICKUP", "WHEAT", min(4, wheat_available)]
            ), "pickup_feed"

    if full_service:
        harvestable = [p for p, t in active if int(t.get("yield_units", 0) or 0) > 0 and p not in reserved]
        route = _nearest_route(tiles, position, harvestable)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["HARVEST"]), "harvest"

        uncared = [p for p, t in active if not bool(t.get("cared_today", False)) and p not in reserved]
        route = _nearest_route(tiles, position, uncared)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["CARE"]), "care"

        fertilizer = [p for p, t in active if bool(t.get("fertilizer_available", False)) and p not in reserved]
        route = _nearest_route(tiles, position, fertilizer)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["COLLECT_FERTILIZER"]), "fertilizer"

    # Place cows waiting in the shed into existing empty pastures.
    if int(shed.get(ANIMAL, 0) or 0) > 0 and empty_pastures:
        return _to_shed_action(tiles, position, ["PICKUP", ANIMAL, 1]), "pickup_cow"

    # Add one pasture at a time. Growth is already frozen by target_cows when
    # farm health is poor; never build more structures than the current target.
    pasture_count = len(_pastures(tiles))
    if pasture_count < target_cows and cow_count <= target_cows:
        candidates = [p for p in _outside_nw_empty(tiles) if p not in reserved]
        route = _nearest_route(tiles, position, candidates)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _route_or_action(tiles, position, target, ["BUILD_PASTURE"]), "build_pasture"

    return None, "idle"


def _inject_market_orders(
    base_orders: Sequence[Any], *, expansion_eligible: bool, land_injected: bool,
    obs: Mapping[str, Any], farm: Mapping[str, Any], target_cows: int,
) -> Tuple[List[List[Any]], Dict[str, int]]:
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    active_count = len(_active_cows(tiles))
    cow_count = _cow_count(obs, farm)
    empty_pastures = len(_empty_pastures(tiles))

    # Keep V15 orders except residual land/animal orders; this layer owns those.
    clean: List[List[Any]] = []
    for raw in base_orders:
        if not isinstance(raw, list) or not raw:
            continue
        op = str(raw[0]).upper()
        if op in {"BUY_LAND", "BUY_ANIMAL"}:
            continue
        clean.append(list(raw))

    critical: List[List[Any]] = []
    if expansion_eligible and land_injected:
        critical.append(["BUY_LAND"])

    # Feed reserve scales with active cows. Buying wheat is economically safe:
    # it is the survival input and only WHEAT/FERTILIZER are market-buyable.
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_target = active_count * FEED_BUFFER_PER_COW
    if active_count > 0 and wheat < feed_target:
        critical.append(["BUY_PRODUCT", "WHEAT", feed_target - wheat])

    # Buy only for already-built empty pastures. This keeps capital staged and
    # prevents animals sitting idle in the shed while structures lag behind.
    need = min(empty_pastures, max(0, target_cows - cow_count))
    if need > 0:
        affordable = max(0, int((float(farm.get("money", 0) or 0) - 1000) // ANIMAL_COST))
        buy = min(need, affordable)
        if buy > 0:
            critical.append(["BUY_ANIMAL", ANIMAL, buy])

    # Give the crop scheduler its original hires, but guarantee a six-hand floor
    # once cows exist so the last two hands can be dedicated to livestock.
    hires_in_clean = sum(1 for o in clean if o[:1] == ["HIRE"])
    desired_hands = min(MAX_HANDS_WITH_COWS, MIN_HANDS_WITH_COWS if (active_count or target_cows > 0) else len(hands))
    extra_hires = max(0, desired_hands - len(hands) - hires_in_clean)
    for _ in range(extra_hires):
        critical.append(["HIRE"])

    # Critical survival/setup orders go first; preserve as many of V15's sells,
    # hires and seed buys as the 10-order cap permits.
    orders = (critical + clean)[:10]
    return orders, {
        "wheat_bought": sum(int(o[2]) for o in critical if o[:2] == ["BUY_PRODUCT", "WHEAT"]),
        "cows_bought": sum(int(o[2]) for o in critical if o[:2] == ["BUY_ANIMAL", ANIMAL]),
        "extra_hires": extra_hires,
    }


def reset_state() -> None:
    global _LAST_STEP, _PEAK_NW_PRODUCTIVE, _FORCED_ADAPTIVE
    _LAST_STEP = -1
    _PEAK_NW_PRODUCTIVE = 0
    _FORCED_ADAPTIVE = False
    _RECORDS.clear()
    reset = getattr(_v15, "reset_state", None)
    if callable(reset):
        reset()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _LAST_STEP, _PEAK_NW_PRODUCTIVE, _FORCED_ADAPTIVE

    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = _m(farms[player])
    tiles = farm.get("tiles") or []
    if not isinstance(tiles, list) or not tiles:
        return {"farmer": ["PASS"], "hands": [], "market": []}

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    health = _farm_health(farm)
    _PEAK_NW_PRODUCTIVE = max(_PEAK_NW_PRODUCTIVE, int(health["nw_productive"]))
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    money = float(farm.get("money", 0) or 0)

    expansion_eligible = (
        len(unlocked) == 1
        and EXPAND_MIN_DAY <= day <= EXPAND_MAX_DAY
        and _PEAK_NW_PRODUCTIVE >= MIN_PEAK_NW_PRODUCTIVE
        and money >= MIN_CASH_TO_EXPAND
        and int(health["weeds"]) <= MAX_WEEDS_TO_EXPAND
        and int(health["danger"]) <= MAX_DANGER_TO_EXPAND
    )

    if expansion_eligible or day >= FORCE_ADAPTIVE_DAY:
        _FORCED_ADAPTIVE = True
    if _FORCED_ADAPTIVE:
        _switch_v15_to_adaptive()

    base = dict(_v15.agent(observation, configuration))

    # The current observation still shows the old quadrant on the purchase turn;
    # livestock begins from the following state after land is actually unlocked.
    cow_count = _cow_count(obs, farm)
    active_count = len(_active_cows(tiles))
    target_cows = _cow_target(day, money, health, len(unlocked), cow_count, active_count)
    full_service = float(health["weed_ratio"]) <= MAX_WEED_RATIO_FOR_FULL_SERVICE

    farmer_action = list(base.get("farmer", ["PASS"]))
    hand_actions = [list(a) if isinstance(a, list) else ["PASS"] for a in base.get("hands", [])]
    actions = [farmer_action] + hand_actions

    # Dedicate the last two hands, not the farmer/first hands. V15 assigns units
    # sequentially, so this preserves its highest-priority crop reservations.
    hands = list(farm.get("hands") or [])
    crew_count = min(2, len(hands)) if (active_count or target_cows > 0 or len(_pastures(tiles)) > 0) else 0
    crew_indices = list(range(1 + len(hands) - crew_count, 1 + len(hands))) if crew_count else []
    reserved: Set[Position] = set()
    stages: List[str] = []
    overrides = 0
    for unit_index in crew_indices:
        action, stage = _livestock_action(obs, farm, unit_index, reserved, target_cows, full_service)
        stages.append(stage)
        if action is not None and unit_index < len(actions):
            actions[unit_index] = action
            overrides += 1

    land_injected = bool(expansion_eligible)
    market, market_info = _inject_market_orders(
        base.get("market", []), expansion_eligible=expansion_eligible,
        land_injected=land_injected, obs=obs, farm=farm, target_cows=target_cows,
    )

    result = {
        "farmer": actions[0] if actions else farmer_action,
        "hands": actions[1:],
        "market": market,
    }

    _RECORDS.append({
        "step": step, "day": day, "hour": hour, "money": money,
        "unlocked_count": len(unlocked),
        "peak_nw_productive": _PEAK_NW_PRODUCTIVE,
        "health": dict(health),
        "expansion_eligible": expansion_eligible,
        "land_injected": land_injected,
        "forced_adaptive": _FORCED_ADAPTIVE,
        "cow_count": cow_count,
        "active_cows": active_count,
        "pastures": len(_pastures(tiles)),
        "target_cows": target_cows,
        "full_service": full_service,
        "crew_count": crew_count,
        "livestock_overrides": overrides,
        "livestock_stages": stages,
        **market_info,
    })
    return result
