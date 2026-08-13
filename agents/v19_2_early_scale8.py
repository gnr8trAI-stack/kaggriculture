"""V19.2 live challenger: V19.1 feed accounting + controlled earlier scale.

Compared with V19, this challenger:
- counts carried WHEAT before replenishing feed, preserving market-order slots;
- permits the second land purchase from day 8 instead of day 10;
- lowers the historical NW productive threshold from 20 to 18;
- keeps a 2,000 cash reserve after the first land purchase;
- switches to the adaptive V12 engine by day 16;
- targets seven hands once livestock exists, with an eight-hand ceiling.

Cow count and livestock routing remain V19's proven 2->4 design. This is the
larger of the two live mutations, intended to test whether V19's current live
ceiling is primarily delayed scale rather than animal composition.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from agents import v19_livestock_compound as _v19

# Controlled scale mutation.
_v19.EXPAND_MIN_DAY = 8
_v19.EXPAND_MAX_DAY = 18
_v19.MIN_PEAK_NW_PRODUCTIVE = 18
_v19.MIN_CASH_TO_EXPAND = 3000
_v19.FORCE_ADAPTIVE_DAY = 16
_v19.MIN_HANDS_WITH_COWS = 7
_v19.MAX_HANDS_WITH_COWS = 8


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _inject_market_orders(
    base_orders: Sequence[Any], *, expansion_eligible: bool, land_injected: bool,
    obs: Mapping[str, Any], farm: Mapping[str, Any], target_cows: int,
) -> Tuple[List[List[Any]], Dict[str, int]]:
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    inventories = private.get("inventories", [])
    tiles = farm.get("tiles") or []
    hands = list(farm.get("hands") or [])
    active_count = len(_v19._active_cows(tiles))
    cow_count = _v19._cow_count(obs, farm)
    empty_pastures = len(_v19._empty_pastures(tiles))

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

    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_m(inv).get("WHEAT", 0) or 0) for inv in inventories)
    feed_target = active_count * _v19.FEED_BUFFER_PER_COW
    if active_count > 0 and total_wheat < feed_target:
        critical.append(["BUY_PRODUCT", "WHEAT", feed_target - total_wheat])

    need = min(empty_pastures, max(0, target_cows - cow_count))
    if need > 0:
        affordable = max(0, int((float(farm.get("money", 0) or 0) - 1200) // _v19.ANIMAL_COST))
        buy = min(need, affordable)
        if buy > 0:
            critical.append(["BUY_ANIMAL", _v19.ANIMAL, buy])

    hires_in_clean = sum(1 for o in clean if o[:1] == ["HIRE"])
    desired_hands = min(
        _v19.MAX_HANDS_WITH_COWS,
        _v19.MIN_HANDS_WITH_COWS if (active_count or target_cows > 0) else len(hands),
    )
    extra_hires = max(0, desired_hands - len(hands) - hires_in_clean)
    for _ in range(extra_hires):
        critical.append(["HIRE"])

    orders = (critical + clean)[:10]
    return orders, {
        "wheat_bought": sum(int(o[2]) for o in critical if o[:2] == ["BUY_PRODUCT", "WHEAT"]),
        "cows_bought": sum(int(o[2]) for o in critical if o[:2] == ["BUY_ANIMAL", _v19.ANIMAL]),
        "extra_hires": extra_hires,
    }


_v19._inject_market_orders = _inject_market_orders


def reset_state() -> None:
    _v19.reset_state()


def reset_telemetry() -> None:
    _v19.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v19.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    return _v19.agent(observation, configuration)
