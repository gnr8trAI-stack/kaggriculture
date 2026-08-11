"""V33.29 staged terminal liquidation.

Single-mechanism experiment on top of V33.28. V33.28 reached a robust ~64k
median with four productive districts, but its D27 terminal rule dumps all
remaining inventory at once. Since terminal reward is bank cash and unsold shed
inventory has no value, we still guarantee full liquidation by the end; the only
change here is to stage premium liquidation across D25-D29 so recurring town
absorption can restore price between sales instead of forcing a D27 glut.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v28 as _v28

_b = _v28._b
BASE = _v28.BASE


def _sale_qty(obs: Mapping[str, Any], item: str, qty: int, day: int, shed_total: int) -> int:
    if qty <= 0:
        return 0
    price = float(_b._prices(obs).get(item, BASE.get(item, 1)) or BASE.get(item, 1))
    base = float(BASE.get(item, max(1, price)))
    demand = _v28._daily_demand(obs, item)

    # Final day is non-negotiable: inventory has no terminal value.
    if day >= 29:
        return qty

    # Melon has no recurring shop sink; realize it immediately.
    if item == "MELON":
        return qty

    # Staples remain working-capital products. V29 changes only terminal premium
    # liquidation; keeping staple behavior identical isolates the mechanism.
    if item in {"WHEAT", "CARROT", "TOMATO", "EGG", "FERTILIZER"}:
        if item == "TOMATO" and price < 24 and day < 24 and shed_total < 75:
            return min(qty, max(2, demand))
        return qty

    # Preserve V28's normal premium pacing before the terminal window.
    if day < 25:
        threshold = 0.72 * base if day < 24 else 0.42 * base
        if price >= threshold or shed_total >= 82:
            return min(qty, max(4, demand * 2 if demand else 4))
        return 0

    # D25-D28: drain inventory progressively while letting town consumption
    # recover price. The floor rises as the deadline approaches; low-price stock
    # is still forced out in bounded daily chunks so D29 cannot become one dump.
    days_left = max(1, 29 - day)
    floor_ratio = {25: 0.50, 26: 0.38, 27: 0.26, 28: 0.12}.get(day, 0.12)
    required_daily = max(1, (qty + days_left - 1) // days_left)
    absorption_chunk = max(4, demand * 2 if demand else 4)
    if price >= floor_ratio * base:
        return min(qty, max(required_daily, absorption_chunk))
    # Even below the floor, bleed enough inventory to make guaranteed D29
    # liquidation feasible without reproducing V28's full-quantity shock.
    return min(qty, required_daily)


# V28's installed capital allocator resolves _sale_qty through its module globals,
# so replacing that symbol changes only liquidation pacing; land, crops, cows,
# staffing, feed, and seed allocation remain byte-for-byte V28 behavior.
_v28._sale_qty = _sale_qty


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
