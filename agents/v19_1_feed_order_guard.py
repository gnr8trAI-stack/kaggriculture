"""V19.1 live challenger: carried-feed-aware market ordering.

This is intentionally a small V19 mutation. V19 replenishes feed using only
WHEAT visible in the shed. Wheat already carried by livestock workers is also
usable feed, but V19 does not count it; that can create unnecessary BUY_PRODUCT
orders, consume one of the ten market-order slots, and crowd out V15 crop/sell
orders. V19.1 counts all private wheat before replenishing. Farm routing,
expansion, cow count and crop policy are otherwise unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from agents import v19_livestock_compound as _v19


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

    # V19.1 fix: feed in a worker inventory is already economically committed
    # and immediately usable. Count it before placing another market order.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(inventories, list):
        total_wheat += sum(int(_m(inv).get("WHEAT", 0) or 0) for inv in inventories)
    feed_target = active_count * _v19.FEED_BUFFER_PER_COW
    if active_count > 0 and total_wheat < feed_target:
        critical.append(["BUY_PRODUCT", "WHEAT", feed_target - total_wheat])

    need = min(empty_pastures, max(0, target_cows - cow_count))
    if need > 0:
        affordable = max(0, int((float(farm.get("money", 0) or 0) - 1000) // _v19.ANIMAL_COST))
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


# Patch only the market-injection layer used by V19.agent.
_v19._inject_market_orders = _inject_market_orders


def reset_state() -> None:
    _v19.reset_state()


def reset_telemetry() -> None:
    _v19.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v19.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    return _v19.agent(observation, configuration)
