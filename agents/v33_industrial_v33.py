"""V33.33 all-product batch-clearing industrial strategy.

Independent V33 lineage.  V33.32 demonstrated that Kaggriculture sells an order
at the pre-impact quote, so dribbling repeated SELL orders destroys realized
price.  V33.33 extends that mechanism from premium output to the whole farm:
productive districts accumulate serviceable lots and monetize them as a single
market-impact event, while feed reserve, shed pressure and D27 liquidation stay
hard constraints.

This is an economic allocator change, not a V19/V32 parameter mutation.  The
four-district executor/capital allocator remains V33.28; only realized marketing
policy changes here so the benchmark isolates the mechanism.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v32 as _v32

_v28 = _v32._v28
_b = _v32._b
BASE = dict(_v32.BASE)


def _batch_sale_qty(obs: Mapping[str, Any], item: str, qty: int, day: int, shed_total: int) -> int:
    if qty <= 0:
        return 0
    if day >= 27:
        return qty

    item = str(item).upper()
    price = float(_b._prices(obs).get(item, BASE.get(item, 1)) or BASE.get(item, 1))
    base = float(BASE.get(item, max(1.0, price)))
    demand = int(_v28._daily_demand(obs, item) or 0)

    # Inventory overflow is terminally destructive.  Clear aggressively before
    # the 100-slot shed can discard subsequent harvest/livestock output.
    if shed_total >= 82:
        return qty

    # One order receives one pre-impact quote.  Batch thresholds are therefore
    # sized to amortize a single market-price impact across a meaningful lot.
    policy = {
        "MELON":      (20, 0.68, 0.48),
        "WHEAT":      (24, 0.86, 0.62),
        "CARROT":     (18, 0.84, 0.58),
        "TOMATO":     (16, 0.82, 0.55),
        "STRAWBERRY": (12, 0.78, 0.50),
        "EGG":        (18, 0.82, 0.56),
        "MILK":       (12, 0.76, 0.48),
        "WOOL":       (8,  0.76, 0.46),
        "FERTILIZER": (18, 0.78, 0.50),
    }
    batch, early_ratio, late_ratio = policy.get(item, (16, 0.80, 0.52))

    # Recurring town/shop absorption justifies larger waits for high-throughput
    # products; zero-demand products should clear after one useful lot.
    if demand > 0:
        batch = max(batch, min(36, demand * 2))
    elif item == "MELON":
        batch = max(20, batch)

    if price >= early_ratio * base and qty >= batch:
        return qty

    # From D22 onward favor realization over perfect quotes; enough horizon has
    # elapsed that another full recovery/batch cycle is uncertain.
    if day >= 22 and price >= late_ratio * base:
        return qty

    # Earlier pressure valve avoids reaching the hard 82-slot emergency point.
    if shed_total >= 72 and price >= 0.40 * base:
        return qty
    return 0


_v28._sale_qty = _batch_sale_qty


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
