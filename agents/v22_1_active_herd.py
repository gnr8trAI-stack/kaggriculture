"""V22.1 active-herd correction.

Single mutation over V22 Frontier Clone: make the replay target mean *simultaneous
placed livestock*, not merely purchased/owned livestock.  V22.0's gate exposed
that it could own 8 cows + 6 sheep while only 7-8 animals were active because
pasture construction and placement were lower priority than steady-state service.

Everything else stays on V22.0: land schedule, crop profile, market allocator,
V12 crop engine and terminal liquidation.
"""
from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Any, Mapping, Set, Tuple

from agents import v22_frontier_clone as _base

Position = Tuple[int, int]


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _active_species(tiles: Any) -> Counter:
    out = Counter()
    for _p, tile in _base._active_animals(tiles):
        species = str(tile.get("animal", "")).upper()
        if species in {"COW", "SHEEP"}:
            out[species] += 1
    return out


def _herd_crew_size(active_count: int, structure_count: int, unit_count: int) -> int:
    """Use more deployment capacity only while the herd is physically incomplete."""
    target = min(_base.FINAL_PASTURES, max(structure_count, active_count))
    incomplete = active_count < target or structure_count < target
    if unit_count <= 2:
        return max(0, unit_count - 1)
    if incomplete:
        # At the 14-animal frontier this gives seven livestock units and still
        # leaves farmer + four hands for crops.  Once deployed we release one.
        return min(7, max(1, unit_count - 5), max(2, ceil(max(1, target) / 2)))
    return min(6, max(1, unit_count - 5), max(2, ceil(max(1, active_count) / 3)))


def _deployment_first_action(
    obs: Mapping[str, Any], farm: Mapping[str, Any], unit_index: int,
    reserved: Set[Position], target_structures: int,
):
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    positions = [_base._pos(farm.get("farmer", [0, 0]))] + [_base._pos(h) for h in hands]
    if unit_index >= len(positions) or not isinstance(tiles, list) or not tiles:
        return None, "no_unit"
    position = positions[unit_index]
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    invs = private.get("inventories", [])
    inv = _m(invs[unit_index]) if isinstance(invs, list) and unit_index < len(invs) else {}

    active = _base._active_animals(tiles)
    active_species = _active_species(tiles)
    pastures = _base._pastures(tiles)
    empty = [p for p, t in pastures if not t.get("animal")]
    profile = _base._profile(int(obs.get("day", 0) or 0))
    target_species = {"COW": int(profile["cow"]), "SHEEP": int(profile["sheep"])}

    # 1) Do not allow an already-stressed animal to escape while expanding.
    urgent = [
        p for p, t in active
        if not bool(t.get("fed_today", False))
        and int(t.get("consecutive_unfed", 0) or 0) >= 1
        and p not in reserved
    ]
    if urgent:
        if int(inv.get("WHEAT", 0) or 0) > 0:
            route = _base._nearest_route(tiles, position, urgent)
            if route is not None:
                _, target, _ = route; reserved.add(target)
                return _base._go(tiles, position, target, ["FEED"]), "urgent_feed"
        if int(shed.get("WHEAT", 0) or 0) > 0:
            return _base._to_shed(tiles, position, ["PICKUP", "WHEAT", min(8, int(shed.get("WHEAT", 0) or 0))]), "urgent_pickup_feed"

    # 2) Placement is the highest growth priority once a pasture exists.
    for species in ("COW", "SHEEP"):
        if active_species[species] >= target_species[species]:
            continue
        if int(inv.get(species, 0) or 0) > 0 and empty:
            choices = [p for p in empty if p not in reserved]
            route = _base._nearest_route(tiles, position, choices)
            if route is not None:
                _, target, _ = route; reserved.add(target)
                return _base._go(tiles, position, target, ["PLACE", species]), "deploy_" + species.lower()

    # 3) Build missing physical capacity before optional animal service.
    if len(pastures) < target_structures:
        goals = [p for p in _base._pasture_build_candidates(tiles, target_structures) if p not in reserved]
        route = _base._nearest_route(tiles, position, goals)
        if route is not None:
            _, target, _ = route; reserved.add(target)
            return _base._go(tiles, position, target, ["BUILD_PASTURE"]), "build_pasture_priority"

    # 4) Pull the next required animal from shed after capacity exists.
    if empty:
        for species in ("COW", "SHEEP"):
            if active_species[species] < target_species[species] and int(shed.get(species, 0) or 0) > 0:
                return _base._to_shed(tiles, position, ["PICKUP", species, 1]), "pickup_deploy_" + species.lower()

    # 5) Once physical deployment work is exhausted, use V22 service logic.
    return _base._livestock_action_v22_original(obs, farm, unit_index, reserved, target_structures)


# Preserve original function before replacing module globals used by _base.agent.
if not hasattr(_base, "_livestock_action_v22_original"):
    _base._livestock_action_v22_original = _base._livestock_action
_base._livestock_action = _deployment_first_action
_base._livestock_crew_size = _herd_crew_size


def reset_state() -> None:
    _base.reset_state()
    _base._livestock_action = _deployment_first_action
    _base._livestock_crew_size = _herd_crew_size


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    result = _base.agent(observation, configuration)
    # Correct telemetry: owned != active.  Promotion gates must use simultaneous
    # placed species counts, not independent maxima of purchased stock.
    try:
        obs = _base._obs(observation)
        player = int(obs.get("player", 0) or 0)
        farm = _m((obs.get("farms") or [])[player])
        counts = _active_species(farm.get("tiles") or [])
        if _base._RECORDS:
            _base._RECORDS[-1]["active_cows"] = int(counts["COW"])
            _base._RECORDS[-1]["active_sheep"] = int(counts["SHEEP"])
            _base._RECORDS[-1]["active_animals"] = int(counts["COW"] + counts["SHEEP"])
    except Exception:
        pass
    return result
