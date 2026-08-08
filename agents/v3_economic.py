"""Kaggriculture v3 replay-mined economic / farm-health agent.

The runtime does not replay fixed winning routes. Offline replay mining learns
phase targets (crop density, animals, hands, cash reserve) and weed thresholds.
This file contains conservative defaults; CI replaces the policy block with a
policy mined from the fit-window Kaggle replay corpus before packaging.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str, int, int]] = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0))
FARMHOUSE = (4, 4)
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
SELLABLE = ("FERTILIZER", "MILK", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WOOL", "EGG", "WHEAT")

# BEGIN LEARNED_POLICY
POLICY = {
    "primary_crop": "STRAWBERRY",
    "primary_animal": "COW",
    "weed_soft_ratio": 0.06,
    "weed_hard_ratio": 0.12,
    "phases": {
        "5": {"target_crops": 12, "target_animals": 2, "target_hands": 2, "target_land": 1, "cash_reserve": 250, "max_backlog_per_unit": 2.0},
        "10": {"target_crops": 15, "target_animals": 3, "target_hands": 3, "target_land": 1, "cash_reserve": 400, "max_backlog_per_unit": 2.0},
        "15": {"target_crops": 14, "target_animals": 5, "target_hands": 4, "target_land": 1, "cash_reserve": 600, "max_backlog_per_unit": 1.8},
        "20": {"target_crops": 12, "target_animals": 6, "target_hands": 4, "target_land": 1, "cash_reserve": 800, "max_backlog_per_unit": 1.6},
        "25": {"target_crops": 10, "target_animals": 6, "target_hands": 4, "target_land": 1, "cash_reserve": 1000, "max_backlog_per_unit": 1.5},
        "29": {"target_crops": 6, "target_animals": 5, "target_hands": 2, "target_land": 1, "cash_reserve": 0, "max_backlog_per_unit": 1.5},
    },
}
# END LEARNED_POLICY


def _d(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(o: Any) -> Dict[str, Any]:
    if isinstance(o, dict):
        return o
    out: Dict[str, Any] = {}
    for n in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            out[n] = getattr(o, n)
        except Exception:
            pass
    return out


def _pos(v: Any) -> Position:
    if isinstance(v, Mapping):
        v = v.get("position", v.get("pos", [0, 0]))
    try:
        return int(v[0]), int(v[1])
    except Exception:
        return 0, 0


def _kind(t: Any) -> Optional[str]:
    if not isinstance(t, Mapping):
        return None
    v = t.get("kind", t.get("type"))
    return str(v).upper() if v is not None else None


def _inside(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    x, y = p
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _walkable(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    if not _inside(tiles, p):
        return False
    t = tiles[p[1]][p[0]]
    return t != "LOCKED" and _kind(t) != "LOCKED"


def _neigh(tiles: Sequence[Sequence[Any]], p: Position) -> Iterable[Tuple[str, Position]]:
    x, y = p
    for a, dx, dy in DIRECTIONS:
        q = x + dx, y + dy
        if _walkable(tiles, q):
            yield a, q


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
    if start == goal:
        return 0, "PASS"
    q = deque([(start, 0, None)])
    seen = {start}
    while q:
        p, dist, first = q.popleft()
        for a, nxt in _neigh(tiles, p):
            if nxt in seen:
                continue
            seen.add(nxt)
            initial = first or a
            if nxt == goal:
                return dist + 1, initial
            q.append((nxt, dist + 1, initial))
    return None


def _phase(day: int) -> Mapping[str, Any]:
    phases = _d(POLICY.get("phases"))
    keys = sorted((int(k), k) for k in phases)
    if not keys:
        return {}
    for d, key in keys:
        if day <= d:
            return _d(phases[key])
    return _d(phases[keys[-1][1]])


def _animal_structure(animal: str) -> str:
    return "COOP" if animal == "GOOSE" else "PASTURE"


def _count(tiles: Sequence[Sequence[Any]]) -> Dict[str, Any]:
    c: Dict[str, Any] = {"pasture": 0, "coop": 0, "weed": 0, "usable": 0, "occupied": 0, "crop_total": 0, "animal_total": 0}
    for crop in CROPS:
        c[f"crop_{crop}"] = 0
    for animal in ANIMALS:
        c[f"animal_{animal}"] = 0
    for row in tiles:
        for t in row:
            if t == "LOCKED" or _kind(t) == "LOCKED":
                continue
            c["usable"] += 1
            if t is not None:
                c["occupied"] += 1
            td = _d(t)
            k = _kind(t)
            if k == "PASTURE":
                c["pasture"] += 1
            elif k == "COOP":
                c["coop"] += 1
            elif k == "PLANT":
                crop = str(td.get("crop", "")).upper()
                if crop in CROPS:
                    c[f"crop_{crop}"] += 1
                    c["crop_total"] += 1
            elif k == "WEED":
                c["weed"] += 1
            animal = str(td.get("animal", "")).upper()
            if animal in ANIMALS:
                c[f"animal_{animal}"] += 1
                c["animal_total"] += 1
    c["weed_ratio"] = c["weed"] / max(1, c["usable"])
    c["occupancy_ratio"] = c["occupied"] / max(1, c["usable"])
    return c


def _targets(tiles: Sequence[Sequence[Any]], weed_ratio: float) -> List[Tuple[int, Position, List[Any], Optional[str]]]:
    out: List[Tuple[int, Position, List[Any], Optional[str]]] = []
    soft = float(POLICY.get("weed_soft_ratio", 0.06) or 0.06)
    hard = float(POLICY.get("weed_hard_ratio", 0.12) or 0.12)
    weed_priority = 1 if weed_ratio >= hard else 2 if weed_ratio >= soft else 6
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            k = _kind(t)
            td = _d(t)
            if k == "PLANT":
                if int(td.get("yield_units", td.get("yield", 0)) or 0) > 0:
                    out.append((0, (x, y), ["HARVEST"], None))
                elif not bool(td.get("watered_today", td.get("watered", False))):
                    out.append((2, (x, y), ["WATER"], None))
            elif k in {"PASTURE", "COOP"} and td.get("animal"):
                if int(td.get("yield_units", td.get("yield", 0)) or 0) > 0:
                    out.append((0, (x, y), ["HARVEST"], None))
                if not bool(td.get("fed_today", td.get("fed", False))):
                    out.append((1, (x, y), ["FEED"], "WHEAT"))
                if not bool(td.get("cared_today", td.get("cared", False))):
                    out.append((3, (x, y), ["CARE"], None))
                if bool(td.get("fertilizer_available", False)):
                    out.append((4, (x, y), ["COLLECT_FERTILIZER"], None))
            elif k == "WEED":
                out.append((weed_priority, (x, y), ["DIG"], None))
    return out


def _empty(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    return [(x, y) for y, row in enumerate(tiles) for x, t in enumerate(row) if t is None]


def _empty_structures(tiles: Sequence[Sequence[Any]], structure: str) -> List[Position]:
    out = []
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if _kind(t) == structure and not _d(t).get("animal"):
                out.append((x, y))
    return out


def _move_or(action: List[Any], tiles: Sequence[Sequence[Any]], pos: Position, target: Position) -> List[Any]:
    r = _route(tiles, pos, target)
    if r is None:
        return ["PASS"]
    dist, first = r
    return action if dist == 0 else [first]


def _unit_action(tiles: Sequence[Sequence[Any]], pos: Position, inv: Mapping[str, Any], targets: Sequence[Tuple[int, Position, List[Any], Optional[str]]], reserved: Set[Position], counts: Mapping[str, Any], seeds: Mapping[str, Any], phase: Mapping[str, Any], healthy: bool) -> List[Any]:
    inv = _d(inv)
    crop = str(POLICY.get("primary_crop", "STRAWBERRY")).upper()
    animal = str(POLICY.get("primary_animal", "COW")).upper()
    structure = _animal_structure(animal)
    target_animals = int(phase.get("target_animals", 0) or 0)
    target_crops = int(phase.get("target_crops", 0) or 0)

    if int(inv.get(animal, 0) or 0) > 0:
        cand = []
        for t in _empty_structures(tiles, structure):
            if t in reserved:
                continue
            r = _route(tiles, pos, t)
            if r:
                cand.append((r[0], t, r[1]))
        if cand:
            cand.sort()
            dist, t, first = cand[0]
            reserved.add(t)
            return ["PLACE", animal] if dist == 0 else [first]

    if int(inv.get("WHEAT", 0) or 0) > 0:
        feed = []
        for _, t, _, req in targets:
            if req == "WHEAT" and t not in reserved:
                r = _route(tiles, pos, t)
                if r:
                    feed.append((r[0], t, r[1]))
        if feed:
            feed.sort()
            dist, t, first = feed[0]
            reserved.add(t)
            return ["FEED"] if dist == 0 else [first]

    carried = sum(int(v or 0) for k, v in inv.items() if k not in ("WHEAT", animal))
    if carried:
        return _move_or(["DROP"], tiles, pos, FARMHOUSE)

    cand = []
    for pri, t, action, req in targets:
        if t in reserved or req == "WHEAT":
            continue
        r = _route(tiles, pos, t)
        if r:
            cand.append((pri, r[0], t, action, r[1]))
    if cand:
        cand.sort(key=lambda z: (z[0], z[1], z[2][1], z[2][0]))
        _, dist, t, action, first = cand[0]
        reserved.add(t)
        return action if dist == 0 else [first]

    if any(req == "WHEAT" for _, _, _, req in targets):
        return _move_or(["PICKUP", "WHEAT", 1], tiles, pos, FARMHOUSE)
    if not healthy:
        return ["PASS"]

    if int(counts.get(f"animal_{animal}", 0) or 0) < target_animals and _empty_structures(tiles, structure):
        return _move_or(["PICKUP", animal, 1], tiles, pos, FARMHOUSE)
    structures = int(counts.get("coop" if structure == "COOP" else "pasture", 0) or 0)
    if structures < target_animals:
        empt = _empty(tiles)
        if empt:
            empt.sort(key=lambda p: (abs(p[0] - FARMHOUSE[0]) + abs(p[1] - FARMHOUSE[1]), -p[1], -p[0]))
            op = "BUILD_COOP" if structure == "COOP" else "BUILD_PASTURE"
            return _move_or([op], tiles, pos, empt[0])
    if int(counts.get(f"crop_{crop}", 0) or 0) < target_crops and int(seeds.get(crop, 0) or 0) > 0:
        empt = _empty(tiles)
        if empt:
            empt.sort(key=lambda p: (p[1], p[0]))
            return _move_or(["PLANT", crop], tiles, pos, empt[0])
    return ["PASS"]


def _market(obs: Mapping[str, Any], farm: Mapping[str, Any], counts: Mapping[str, Any], phase: Mapping[str, Any], backlog: int, healthy: bool) -> List[List[Any]]:
    private = _d(obs.get("private"))
    shed = _d(private.get("shed"))
    seeds = _d(private.get("seeds"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    actions: List[List[Any]] = []
    liquidate = day >= 29 or (day == 28 and hour >= 18)
    if liquidate:
        for p in SELLABLE:
            q = int(shed.get(p, 0) or 0)
            if q > 0:
                actions.append(["SELL", p, q])
                if len(actions) >= 10:
                    break
        return actions

    crop = str(POLICY.get("primary_crop", "STRAWBERRY")).upper()
    animal = str(POLICY.get("primary_animal", "COW")).upper()
    reserve_cash = float(phase.get("cash_reserve", 0) or 0)
    target_animals = int(phase.get("target_animals", 0) or 0)
    target_crops = int(phase.get("target_crops", 0) or 0)
    if healthy:
        total_animals = int(counts.get(f"animal_{animal}", 0) or 0) + int(shed.get(animal, 0) or 0)
        if total_animals < target_animals and money > reserve_cash:
            actions.append(["BUY_ANIMAL", animal, 1])
        crop_need = max(0, target_crops - int(counts.get(f"crop_{crop}", 0) or 0) - int(seeds.get(crop, 0) or 0))
        if crop_need and money > reserve_cash:
            actions.append(["BUY_SEED", crop, min(crop_need, 4)])

    feed = int(shed.get("WHEAT", 0) or 0)
    target_feed = max(2, int(counts.get("animal_total", 0) or 0) * 2)
    if feed < target_feed and money > reserve_cash:
        actions.append(["BUY_PRODUCT", "WHEAT", min(target_feed - feed, 6)])

    hands = len(farm.get("hands") or [])
    hires_today = int(farm.get("hires_today", 0) or 0)
    target_hands = int(phase.get("target_hands", 0) or 0)
    if not healthy:
        target_hands += 2
    desired = max(target_hands, min(8, max(0, backlog - 1)))
    if hands < desired and hires_today < 3 and money > reserve_cash:
        for _ in range(min(desired - hands, 3 - hires_today)):
            actions.append(["HIRE"])

    reserve = {"WHEAT": target_feed}
    for p in SELLABLE:
        q = max(0, int(shed.get(p, 0) or 0) - reserve.get(p, 0))
        while q > 0 and len(actions) < 10:
            batch = min(q, 2 if p == "FERTILIZER" else 4)
            actions.append(["SELL", p, batch])
            q -= batch
        if len(actions) >= 10:
            break
    return actions[:10]


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = _d(farms[player])
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    if not tiles:
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}

    day = int(obs.get("day", 0) or 0)
    phase = _phase(day)
    private = _d(obs.get("private"))
    inventories = list(private.get("inventories") or [])
    seeds = _d(private.get("seeds"))
    counts = _count(tiles)
    targets = _targets(tiles, float(counts["weed_ratio"]))
    backlog = len(targets)
    unit_count = max(1, len(hands) + 1)
    max_backlog = float(phase.get("max_backlog_per_unit", 2.0) or 2.0) * unit_count
    healthy = float(counts["weed_ratio"]) < float(POLICY.get("weed_soft_ratio", 0.06) or 0.06) and backlog <= max_backlog

    reserved: Set[Position] = set()
    units = [farm.get("farmer", [0, 0])] + hands
    unit_actions: List[List[Any]] = []
    for i, unit in enumerate(units):
        inv = inventories[i] if i < len(inventories) else {}
        unit_actions.append(_unit_action(tiles, _pos(unit), inv, targets, reserved, counts, seeds, phase, healthy))

    return {"farmer": unit_actions[0] if unit_actions else ["PASS"], "hands": unit_actions[1:], "market": _market(obs, farm, counts, phase, backlog, healthy)}
