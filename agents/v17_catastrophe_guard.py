"""V17 challenger: exact V15 plus a catastrophe-only weed guard.

V16 proved that aggressively minimizing weeds destroys V15's economics. V17
therefore leaves V15 completely untouched during normal farm operation and
intervenes only when weed growth enters a severe, accelerating regime.

The guard uses hysteresis:
- normal mode: V15 actions are returned verbatim;
- crisis entry: very high weed ratio, or high ratio plus day-over-day growth;
- crisis exit: weeds recover to a clearly safe level.

During crisis we first freeze land expansion. Only in a severe crisis do we
suppress new planting and redirect otherwise-discretionary actions to DIG.
Critical V15 work (water, harvest, feed, care, logistics, selling) is never
replaced by this overlay.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from agents.v15_champion import agent as _v15_agent

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)

# Evidence-driven conservative thresholds. V15 reached ~24% weeds in strong
# starter games, so V17 deliberately does not intervene anywhere near that
# normal operating range.
ENTER_RATIO = 0.30
ABSOLUTE_CRISIS_RATIO = 0.40
SEVERE_RATIO = 0.36
EXIT_RATIO = 0.18
RISING_WEEDS_PER_DAY = 3
MIN_CRISIS_WEEDS = 8

_STATE: Dict[str, Any] = {}
_METRICS: Dict[str, Any] = {}


def _reset() -> None:
    _STATE.clear()
    _STATE.update({
        "last_step": -1,
        "day": None,
        "previous_day_weeds": None,
        "day_weeds": None,
        "crisis": False,
    })
    _METRICS.clear()
    _METRICS.update({
        "crisis_turns": 0,
        "crisis_entries": 0,
        "blocked_land": 0,
        "blocked_seed": 0,
        "cleanup_overrides": 0,
        "max_weed_ratio": 0.0,
        "max_weeds": 0,
    })


_reset()


def get_telemetry() -> Dict[str, Any]:
    """Return per-game guard telemetry for CI/research; unused by Kaggle."""
    return dict(_METRICS)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        key: getattr(value, key)
        for key in ("player", "step", "day", "hour", "farms", "market", "town", "private")
        if hasattr(value, key)
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


def _farm_health(tiles: Sequence[Sequence[Any]]) -> Dict[str, Any]:
    usable = weeds = 0
    weed_positions: List[Position] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            kind = _kind(tile)
            if kind == "LOCKED":
                continue
            usable += 1
            if kind == "WEED":
                weeds += 1
                weed_positions.append((x, y))
    return {
        "usable": usable,
        "weeds": weeds,
        "ratio": weeds / max(1, usable),
        "weed_positions": weed_positions,
    }


def _update_crisis(step: int, day: int, weeds: int, ratio: float) -> Tuple[bool, bool, int]:
    if step <= int(_STATE.get("last_step", -1)):
        _reset()
    _STATE["last_step"] = step

    previous_day = _STATE.get("day")
    if previous_day is None:
        _STATE["day"] = day
        _STATE["day_weeds"] = weeds
    elif day != previous_day:
        _STATE["previous_day_weeds"] = _STATE.get("day_weeds")
        _STATE["day_weeds"] = weeds
        _STATE["day"] = day

    prev_weeds = _STATE.get("previous_day_weeds")
    day_growth = weeds - int(prev_weeds) if prev_weeds is not None else 0
    rising = day_growth >= RISING_WEEDS_PER_DAY

    crisis = bool(_STATE.get("crisis", False))
    if crisis:
        if ratio <= EXIT_RATIO or weeds <= 4:
            crisis = False
    else:
        enter = ratio >= ABSOLUTE_CRISIS_RATIO or (
            ratio >= ENTER_RATIO and weeds >= MIN_CRISIS_WEEDS and rising
        )
        if enter:
            crisis = True
            _METRICS["crisis_entries"] += 1
    _STATE["crisis"] = crisis

    _METRICS["max_weed_ratio"] = max(float(_METRICS["max_weed_ratio"]), ratio)
    _METRICS["max_weeds"] = max(int(_METRICS["max_weeds"]), weeds)
    if crisis:
        _METRICS["crisis_turns"] += 1
    return crisis, rising, day_growth


def _nearest_weed_action(
    tiles: Sequence[Sequence[Any]], start: Position, weeds: Sequence[Position], reserved: Set[Position]
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


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    base = dict(_v15_agent(observation, configuration))

    player = int(obs.get("player", 0) or 0)
    step = int(obs.get("step", 0) or 0)
    day = int(obs.get("day", step // 24) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return base
    farm = _m(farms[player])
    tiles = farm.get("tiles") or []
    if not isinstance(tiles, list) or not tiles:
        return base

    health = _farm_health(tiles)
    crisis, rising, day_growth = _update_crisis(step, day, health["weeds"], health["ratio"])
    if not crisis:
        # The central V17 rule: healthy/normal farms execute exact V15.
        return base

    severe = health["ratio"] >= SEVERE_RATIO

    # Market intervention is intentionally minimal. Stop buying more land in a
    # crisis. Only in a severe crisis stop buying more seeds. All selling/feed
    # purchases and V15 economic decisions remain untouched.
    market: List[List[Any]] = []
    for raw in base.get("market", []) if isinstance(base.get("market", []), list) else []:
        if not isinstance(raw, list) or not raw:
            continue
        op = str(raw[0]).upper()
        if op == "BUY_LAND":
            _METRICS["blocked_land"] += 1
            continue
        if severe and op == "BUY_SEED":
            _METRICS["blocked_seed"] += 1
            continue
        market.append(list(raw))

    farmer_action = list(base.get("farmer", ["PASS"]))
    hand_actions = [list(a) if isinstance(a, list) else ["PASS"] for a in base.get("hands", [])]
    actions = [farmer_action] + hand_actions

    # Cleanup policy:
    # - ordinary crisis: ONLY consume PASS slots; never steal productive work;
    # - severe crisis: BUILD/PLANT may also be converted, but critical care and
    #   logistics remain inviolate.
    positions = [_pos(farm.get("farmer", [0, 0]))] + [_pos(h) for h in (farm.get("hands") or [])]
    allowed = {"PASS"} if not severe else {"PASS", "PLANT", "BUILD_COOP", "BUILD_PASTURE"}
    reserved: Set[Position] = set()
    for idx, action in enumerate(actions):
        if idx >= len(positions) or not action:
            continue
        if str(action[0]).upper() not in allowed:
            continue
        cleanup = _nearest_weed_action(tiles, positions[idx], health["weed_positions"], reserved)
        if cleanup is not None:
            actions[idx] = cleanup
            _METRICS["cleanup_overrides"] += 1
        # At most one cleanup redirect per turn. V16's broad multi-unit cleanup
        # was too expensive economically.
        break

    return {
        "farmer": actions[0] if actions else farmer_action,
        "hands": actions[1:],
        "market": market[:10],
    }
