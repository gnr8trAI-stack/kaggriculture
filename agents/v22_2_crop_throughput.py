"""V22.2 crop-throughput correction.

Second and final mutation in the bounded frontier-clone experiment:
- inherits V22.1's simultaneous herd deployment fix;
- preserves V22 land/livestock/labour economics;
- adds a short early-day planting lane for strawberry deficits;
- guarantees strawberry seed acquisition is not silently crowded out by SELL/HIRE
  orders while the frontier profile is still ramping.

If this does not materially move the absolute money distribution, the clone
approach is considered falsified and development moves to direct donor-policy
extraction rather than more V22.x mutations.
"""
from __future__ import annotations

from typing import Any, Mapping, Set, Tuple

from agents import v22_1_active_herd as _herd

_base = _herd._base
Position = Tuple[int, int]


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _priority_crop(day: int, farm: Mapping[str, Any]):
    profile = _base._profile(day)
    counts = _base._crop_counts(farm.get("tiles") or [])
    if 7 <= day <= 16 and counts["STRAWBERRY"] < int(profile["STRAWBERRY"]):
        return "STRAWBERRY"
    crop, _ = _base._frontier_choose_crop({"day": day}, farm)
    return crop


def _dedicated_plant_actions(obs: Mapping[str, Any], farm: Mapping[str, Any], result: dict) -> None:
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    if day < 7 or day > 16 or hour >= 8:
        return

    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    positions = [_base._pos(farm.get("farmer", [0, 0]))] + [_base._pos(h) for h in hands]
    unit_count = len(positions)
    active_count = len(_base._active_animals(tiles))
    target_structures = min(_base.FINAL_PASTURES, int(_base._profile(day)["cow"]) + int(_base._profile(day)["sheep"]))
    crew = _base._livestock_crew_size(active_count, max(len(_base._pastures(tiles)), target_structures), unit_count)
    crop_units = max(0, unit_count - crew)
    if crop_units <= 0:
        return

    private = _m(obs.get("private"))
    seeds = _m(private.get("seeds"))
    crop = _priority_crop(day, farm)
    if crop is None or int(seeds.get(crop, 0) or 0) <= 0:
        return

    target = _base._profile(day)
    counts = _base._crop_counts(tiles)
    deficit = max(0, int(target.get(crop, 0)) - int(counts[crop]))
    if deficit <= 0:
        return

    farmer_action = list(result.get("farmer", ["PASS"]))
    hand_actions = [list(a) for a in result.get("hands", [])]
    actions = [farmer_action] + hand_actions
    while len(actions) < unit_count:
        actions.append(["PASS"])

    # Only two early-day planting lanes.  The remaining crop units retain V12's
    # watering/harvest routing so the ramp does not recreate the V16 weed failure.
    planter_count = min(2, crop_units, deficit, int(seeds.get(crop, 0) or 0))
    empties = _base._frontier_empties(tiles)
    reserved: Set[Position] = set()
    for unit_index in range(planter_count):
        choices = [p for p in empties if p not in reserved]
        route = _base._nearest_route(tiles, positions[unit_index], choices)
        if route is None:
            continue
        _, goal, _ = route
        reserved.add(goal)
        actions[unit_index] = _base._go(tiles, positions[unit_index], goal, ["PLANT", crop])

    result["farmer"] = actions[0]
    result["hands"] = actions[1:]


def _ensure_strawberry_seed_order(obs: Mapping[str, Any], farm: Mapping[str, Any], result: dict) -> None:
    day = int(obs.get("day", 0) or 0)
    if not (7 <= day <= 16):
        return
    profile = _base._profile(day)
    counts = _base._crop_counts(farm.get("tiles") or [])
    private = _m(obs.get("private"))
    seeds = _m(private.get("seeds"))
    deficit = max(0, int(profile["STRAWBERRY"]) - int(counts["STRAWBERRY"]) - int(seeds.get("STRAWBERRY", 0) or 0))
    if deficit <= 0:
        return
    money = float(farm.get("money", 0) or 0)
    affordable = max(0, int((money - 1500) // 100))
    qty = min(12, deficit, affordable)
    if qty <= 0:
        return

    orders = [list(o) for o in result.get("market", []) if isinstance(o, list) and o]
    if any(o[0] == "BUY_SEED" and len(o) > 1 and str(o[1]).upper() == "STRAWBERRY" for o in orders):
        return

    # Preserve land/animal/feed investments first.  Insert seed order ahead of
    # HIRE and SELL, then trim to the simulator's ten-order cap.
    priority = []
    remainder = []
    for order in orders:
        if order[0] in {"BUY_LAND", "BUY_ANIMAL", "BUY_PRODUCT"}:
            priority.append(order)
        else:
            remainder.append(order)
    result["market"] = (priority + [["BUY_SEED", "STRAWBERRY", qty]] + remainder)[:10]


def reset_state() -> None:
    _herd.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _herd.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    result = dict(_herd.agent(observation, configuration))
    obs = _base._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = _m(farms[player])
    _dedicated_plant_actions(obs, farm, result)
    _ensure_strawberry_seed_order(obs, farm, result)
    if _base._RECORDS:
        counts = _base._crop_counts(farm.get("tiles") or [])
        _base._RECORDS[-1]["v22_2_strawberry"] = int(counts["STRAWBERRY"])
        _base._RECORDS[-1]["v22_2_market_orders"] = result.get("market", [])
    return result
