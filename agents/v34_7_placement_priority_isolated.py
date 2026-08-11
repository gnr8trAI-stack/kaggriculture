"""V34.7 isolated livestock placement-throughput experiment.

Single economic mutation on top of V34.6: keep the 16-cow ceiling, day-24
purchase window, six-hand livestock service crew, and V19.2 land/crop/feed/
routing/market/staffing policy unchanged, but move pasture construction and
cow pickup ahead of optional harvest/care/fertilizer work.

Rationale: V34.6 bought a median 12 cows but activated only a median 10 and
built a median 11 pastures. Extending the purchase window did not unlock the
16-cow ceiling, so the remaining bottleneck is staging throughput rather than
nominal capacity or purchase timing. Feed survival and carried-cow placement
remain highest priority; only optional service work is deferred behind expansion.
"""
from __future__ import annotations
from typing import Any, List, Mapping, Optional, Set, Tuple

from agents import v34_6_cow16_window24_isolated as _v346

_v19 = _v346._v345._v343._v342._v19
_ORIGINAL = _v19._livestock_action


def _priority_livestock_action(
    obs: Mapping[str, Any], farm: Mapping[str, Any], unit_index: int,
    reserved: Set[_v19.Position], target_cows: int, full_service: bool,
) -> Tuple[Optional[List[Any]], str]:
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    positions = [_v19._pos(farm.get("farmer", [0, 0]))] + [_v19._pos(h) for h in hands]
    if unit_index >= len(positions) or not isinstance(tiles, list) or not tiles:
        return None, "no_unit"
    position = positions[unit_index]

    private = _v19._m(obs.get("private"))
    shed = _v19._m(private.get("shed"))
    inventories = private.get("inventories", [])
    inv = _v19._m(inventories[unit_index]) if isinstance(inventories, list) and unit_index < len(inventories) else {}

    active = _v19._active_cows(tiles)
    empty_pastures = _v19._empty_pastures(tiles)
    cow_count = _v19._cow_count(obs, farm)

    # Preserve highest-priority placement of already-carried cows.
    if int(inv.get(_v19.ANIMAL, 0) or 0) > 0 and empty_pastures:
        choices = [p for p in empty_pastures if p not in reserved]
        route = _v19._nearest_route(tiles, position, choices)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["PLACE", _v19.ANIMAL]), "place_cow"

    # Preserve feed survival ahead of all expansion work.
    if int(inv.get("WHEAT", 0) or 0) > 0:
        unfed = [p for p, t in active if not bool(t.get("fed_today", False)) and p not in reserved]
        route = _v19._nearest_route(tiles, position, unfed)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["FEED"]), "feed"

    output_load = sum(
        int(v or 0) for k, v in inv.items()
        if str(k).upper() not in {"WHEAT", _v19.ANIMAL}
    )
    if output_load > 0:
        return _v19._to_shed_action(tiles, position, ["DROP"]), "return_output"

    unfed = [(p, t) for p, t in active if not bool(t.get("fed_today", False)) and p not in reserved]
    if unfed:
        wheat_available = int(shed.get("WHEAT", 0) or 0)
        if wheat_available > 0:
            return _v19._to_shed_action(
                tiles, position, ["PICKUP", "WHEAT", min(4, wheat_available)]
            ), "pickup_feed"

    # V34.7 mutation: stage expansion before optional harvest/care/fertilizer.
    if int(shed.get(_v19.ANIMAL, 0) or 0) > 0 and empty_pastures:
        return _v19._to_shed_action(tiles, position, ["PICKUP", _v19.ANIMAL, 1]), "pickup_cow"

    pasture_count = len(_v19._pastures(tiles))
    if pasture_count < target_cows and cow_count <= target_cows:
        candidates = [p for p in _v19._outside_nw_empty(tiles) if p not in reserved]
        route = _v19._nearest_route(tiles, position, candidates)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["BUILD_PASTURE"]), "build_pasture"

    # Optional service remains unchanged after staging opportunities are exhausted.
    if full_service:
        harvestable = [p for p, t in active if int(t.get("yield_units", 0) or 0) > 0 and p not in reserved]
        route = _v19._nearest_route(tiles, position, harvestable)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["HARVEST"]), "harvest"

        uncared = [p for p, t in active if not bool(t.get("cared_today", False)) and p not in reserved]
        route = _v19._nearest_route(tiles, position, uncared)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["CARE"]), "care"

        fertilizer = [p for p, t in active if bool(t.get("fertilizer_available", False)) and p not in reserved]
        route = _v19._nearest_route(tiles, position, fertilizer)
        if route is not None:
            _, target, _ = route
            reserved.add(target)
            return _v19._route_or_action(tiles, position, target, ["COLLECT_FERTILIZER"]), "fertilizer"

    return None, "idle"


def _activate() -> None:
    _v346._activate()
    _v19._livestock_action = _priority_livestock_action


def reset_state() -> None:
    _v346.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _v346.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _v346.agent(observation, configuration)


_activate()
