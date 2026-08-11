"""V33.31 dairy-only industrial animal plant.

Independent V33 lineage. V33.28 remains the physical/economic reference at
~64K median with four-land operation and ~76 productive tiles. V33.29 proved
its mixed-animal Q3 machinery is mechanically sound but economically weaker
because structures and labour were fragmented across milk/egg/wool lines.

This candidate keeps V33.29's proven independent four-district executor and
animal-safe mechanics, but concentrates Q3 biological capex entirely in dairy.
It uses the working mixed-engine code path rather than the V33.30 hook stack,
which regressed the bootstrap before Q2.  Cows are sized from remaining-horizon
payback plus recurring town absorption; bought wheat remains a legitimate
operating input.  No goose/sheep structures are commissioned.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial_v29 as _v29

_b = _v29._b


def _dairy_target(obs: Mapping[str, Any], day: int, active: Mapping[str, int]) -> Dict[str, int]:
    """Concentrate Q3 on 12-16 repayable cows; never diversify into weak lines."""
    cows = int(active.get("COW", 0) or 0)
    horizon = max(0, 30 - day)
    if horizon < 9:
        return {"COW": cows, "GOOSE": 0, "SHEEP": 0}

    demand = int(_v29._v28._daily_demand(obs, "MILK") or 0)
    price = float(_b._prices(obs).get("MILK", 160) or 160)

    # Twelve cows is the industrial floor while enough horizon remains.  Higher
    # recurring absorption supports 14-16 without immediately crushing price.
    target = 12
    if demand >= 7 and price >= 80:
        target = 14
    if demand >= 13 and price >= 90:
        target = 16
    if price < 45 and demand <= 1:
        target = 10

    # Biological capex has an ~8 day first-yield delay.  Freeze expansion late.
    if day >= 19:
        target = min(target, max(cows, 14))
    if day >= 21:
        target = cows
    return {"COW": max(cows, target), "GOOSE": 0, "SHEEP": 0}


def _sale_qty(obs: Mapping[str, Any], item: str, qty: int, day: int, shed_total: int) -> int:
    if qty <= 0:
        return 0
    if day >= 27:
        return qty
    if item == "MILK":
        price = float(_b._prices(obs).get("MILK", 160) or 160)
        demand = int(_v29._v28._daily_demand(obs, "MILK") or 0)
        # Keep cash cycling into land/feed/seed while limiting pathological dumps.
        if price >= 85 or shed_total >= 65:
            return min(qty, max(8, demand * 3))
        return min(qty, max(3, demand))
    return _v29._sale_qty(obs, item, qty, day, shed_total)


# V33.29's _unit_action and _capital_allocator resolve these names from their
# own module globals at runtime, so changing only these two strategy functions
# preserves the mechanically proven executor and four-district allocator.
_v29._mix_target = _dairy_target
_v29._sale_qty = _sale_qty


def agent(observation: Any, configuration: Any = None):
    return _v29.agent(observation, configuration)


def reset_state():
    return _v29.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v29.get_telemetry(clear=clear)
