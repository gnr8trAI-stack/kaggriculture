"""V33.51 autonomous district commissioning.

Mechanism change over V33.50: land commissioning is owned by this allocator rather
than inherited from the earlier land gate.  A district is purchased only when
actual bank cash can pay land plus its biological/crop commissioning packet.
This deliberately separates (1) unlock decision from (2) subsequent structure
and animal commissioning, avoiding the V50 failure mode where Q3 never existed
because a transient productive-tile count was used as a prerequisite.

V19.2 is reference-only and is not imported.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v50 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _land_cost(lands: int) -> int:
    # Verified Kaggriculture progression used throughout the V33 branch:
    # Q2=1000, Q3=2000, Q4=4000.
    return {1: 1000, 2: 2000, 3: 4000}.get(int(lands), 10**9)


def _insert_after_sales(orders, order):
    out = [list(o) for o in orders if isinstance(o, list) and o]
    i = 0
    while i < len(out) and out[i][0] == "SELL":
        i += 1
    out.insert(i, order)
    return out[:10]


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    qs = stats["districts"]
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))

    # This revision owns land decisions completely.  Remove any parent land
    # order so there is exactly one capital-allocation authority.
    orders = [o for o in orders if not (isinstance(o, list) and o and o[0] == "BUY_LAND")]

    # Operating packet intentionally uses actual cash only. Same-step quoted
    # sales are not pledged to capex, eliminating double-spend / ordering risk.
    active_animals = int(stats.get("animals", 0) or 0)
    crop_working = 700 + 35 * max(0, int(stats.get("productive", 0) or 0))
    feed_reserve = 45 * active_animals
    execution_buffer = 450
    reserve = crop_working + feed_reserve + execution_buffer

    # Q3 industrial district: third land costs 2k. Keep enough post-purchase
    # cash to buy a first six-goose tranche (1.8k) plus crop/feed reserve.  We
    # no longer require a particular instantaneous planted-tile count because
    # V50 telemetry showed that count collapses naturally at harvest boundaries
    # exactly when cash peaks.
    if lands == 2 and 7 <= day <= 15:
        land = _land_cost(2)
        commission_packet = 1800
        need_cash = land + commission_packet + max(900, reserve)
        if money >= need_cash:
            orders = _insert_after_sales(orders, ["BUY_LAND"])
            meta["district_commission_v51"] = {
                "district": 3,
                "bank": round(money, 1),
                "required": round(need_cash, 1),
                "post_land_packet": commission_packet,
            }
        else:
            meta["q3_capital_gap_v51"] = round(need_cash - money, 1)

    # Q4 is allowed only once Q3 is physically operating.  Use realized animal
    # count and structure count, not a forecast, then preserve a 2.4k post-land
    # packet for either eight geese or fast crops according to the parent ROI
    # allocator.  This makes Q4 an expansion of a functioning factory rather
    # than a speculative land purchase.
    elif lands == 3 and 11 <= day <= 21:
        q3_animals = int(q3.get("animals", 0) or 0)
        q3_structures = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        land = _land_cost(3)
        commission_packet = 2400
        need_cash = land + commission_packet + max(1200, reserve)
        if q3_animals >= 6 and q3_structures >= 8 and money >= need_cash:
            orders = _insert_after_sales(orders, ["BUY_LAND"])
            meta["district_commission_v51"] = {
                "district": 4,
                "bank": round(money, 1),
                "required": round(need_cash, 1),
                "q3_animals": q3_animals,
                "q3_structures": q3_structures,
            }
        else:
            meta["q4_gate_v51"] = {
                "cash_gap": round(max(0.0, need_cash - money), 1),
                "q3_animals": q3_animals,
                "q3_structures": q3_structures,
            }

    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)


def industrial_peaks():
    return _p.industrial_peaks()
