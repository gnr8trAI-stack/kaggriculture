"""V33.32 burst-clearing industrial market strategy.

Independent V33 lineage built on V33.28's mechanically proven four-district
executor (zero invalids, four-land operation, ~76 productive tiles).  The new
mechanism fixes realized-price destruction rather than adding more physical
capacity.

Kaggriculture executes a SELL at the currently observed price and only refreshes
the market price after the turn.  Therefore splitting premium output into many
small sells is economically backwards: each small sale marks down the next one.
V33.32 treats premium marketing as impulse control.  It accumulates a serviceable
batch, clears the entire batch while the pre-impact price is attractive, then
waits for town absorption before the next burst.  Shed-pressure and D27 terminal
liquidation remain hard safety valves.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v28 as _v28

_b = _v28._b

BASE = dict(_v28.BASE)


def _burst_sale_qty(obs: Mapping[str, Any], item: str, qty: int, day: int, shed_total: int) -> int:
    if qty <= 0:
        return 0
    if day >= 27:
        return qty

    item = str(item).upper()
    price = float(_b._prices(obs).get(item, BASE.get(item, 1)) or BASE.get(item, 1))
    base = float(BASE.get(item, max(1.0, price)))
    demand = int(_v28._daily_demand(obs, item) or 0)

    # Hard capacity valve.  Once the shed approaches overflow, realize inventory
    # now; discarded output is always worse than a weak but positive sale.
    if shed_total >= 88:
        return qty

    # Melon has only town-centre absorption.  The valuable event is the first
    # synchronized harvest: accumulate enough to justify one market-impact event,
    # then clear the entire batch at the pre-impact quote.  Do not dribble six
    # melons per turn into a collapsing quadratic glut curve.
    if item == "MELON":
        if price >= 0.72 * base and (qty >= 28 or day >= 12):
            return qty
        if day >= 18 and price >= 0.45 * base:
            return qty
        return 0

    # Premium products have steep post-sale curves.  One large order receives
    # one pre-impact quote; after that, town demand is allowed to rebuild price.
    if item == "STRAWBERRY":
        batch = max(12, demand * 2)
        if price >= 0.78 * base and qty >= batch:
            return qty
        if day >= 23 and price >= 0.50 * base:
            return qty
        return 0

    if item == "MILK":
        batch = max(10, demand * 2)
        if price >= 0.76 * base and qty >= batch:
            return qty
        if day >= 23 and price >= 0.48 * base:
            return qty
        return 0

    if item == "WOOL":
        batch = max(6, demand * 2)
        if price >= 0.76 * base and qty >= batch:
            return qty
        if day >= 23 and price >= 0.45 * base:
            return qty
        return 0

    # Staples/fertilizer retain V33.28's proven fast cash conversion.
    return _v28._sale_qty_original(obs, item, qty, day, shed_total)


# Save the original once so the new function can delegate without recursion.
if not hasattr(_v28, "_sale_qty_original"):
    _v28._sale_qty_original = _v28._sale_qty
_v28._sale_qty = _burst_sale_qty


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
