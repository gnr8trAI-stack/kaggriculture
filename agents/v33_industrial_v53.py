"""V33.53 biological-capital compounding across Q3/Q4.

V33.52 restored the missing Q2 authority and recovered the two-district cash
engine, but the 24-game telemetry still showed zero Q3/Q4 operation.  This is a
mechanism change: once two crop districts create the first realizable cash
packet, land and short-payback goose capacity are funded before another long
crop cycle.  Q4 is commissioned from a functioning Q3 biological base while
there is still enough horizon for its goose tranche to repay.

This remains the independent V33 industrial architecture.  V19/V32 are not
imported.  Verified mechanics used here: Q3/Q4 land cost 2k/4k; goose cost 300;
first egg after four days then daily; structures cost labour actions rather than
cash; day labour resets and is cheap relative to productive-capital throughput.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v52 as _p
from agents import v33_industrial_v50 as _v50
from agents import v33_industrial_v45 as _core

_b = _p._b
_base_allocator = _p._v50_allocator


def _quoted_sales(obs, orders):
    prices = _b._prices(obs)
    value = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = str(o[1]).upper()
            value += int(o[2]) * float(prices.get(item, _b.VALUE.get(item, 1)) or _b.VALUE.get(item, 1))
    return value


def _pending(obs: Mapping[str, Any], item: str) -> int:
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    n = int(shed.get(item, 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        for inv in invs:
            n += int(_b._m(inv).get(item, 0) or 0)
    return n


def _roles(lands: int, hand_count: int):
    """Asset-backed district crews with enough commissioners to actually scale."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Four Q3 operators can commission/service a meaningful goose tranche
        # while leaving five crop operators at the V48 nine-hand target.
        for i in range(max(1, total - 4), total):
            roles[i] = "livestock3"
    if lands >= 4:
        # At the eleven-hand target keep four Q3 + three Q4 livestock operators.
        # Remaining operators continue Q1/Q2; a Q4 livestock worker falls back
        # to Q4 crop tasks whenever no husbandry work is pending.
        for i in range(max(1, total - 7), max(1, total - 3)):
            roles[i] = "livestock3"
        for i in range(max(1, total - 3), total):
            roles[i] = "livestock4"
    return roles


_core._roles = _roles
_b._roles = _roles


def _clean_base_orders(orders):
    out = []
    for o in orders:
        if not isinstance(o, list) or not o:
            continue
        # This allocator owns land and livestock purchases.  Parent retains
        # sales, feed, seeds and labour.
        if o[0] in {"BUY_LAND", "BUY_ANIMAL"}:
            continue
        out.append(list(o))
    return out[:10]


def _funding_packet(orders, land_order=True):
    # When land is the highest ROI capital choice, do not let a same-turn seed
    # packet pre-spend its cash. Sales execute first and finance the atomic land
    # purchase in a deterministic market-order slot.
    out = [list(o) for o in orders if isinstance(o, list) and o and o[0] == "SELL"]
    if land_order:
        out.append(["BUY_LAND"])
    return out[:10]


def _capital_allocator(obs, farm, stats):
    base_orders, meta = _base_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0); hour = int(obs.get("hour", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1)); horizon = max(0, 30 - day)
    qs = stats["districts"]

    # Preserve the proven Q1->Q2 bootstrap intact. V52 showed Q2 unlock step 1
    # with zero invalids, so do not perturb that mechanics path.
    if lands == 1:
        return base_orders[:10], meta

    orders = _clean_base_orders(base_orders)
    sale_quote = _quoted_sales(obs, orders)
    realizable = money + 0.85 * sale_quote
    animals = int(stats.get("animals", 0) or 0)

    # Mandatory reserve: one modest replant packet + near-term feed + execution
    # cushion.  Structures are action-capex, not cash-capex in Kaggriculture.
    reserve = 350 + 18 * animals
    meta["industrial_reserve_v53"] = reserve
    meta["realizable_cash_v53"] = round(realizable, 1)

    # Q3: from the first post-bootstrap crop realization. Eight geese placed by
    # roughly D7 still have ~19 production days after their four-day startup, so
    # the land+first-tranche remaining-horizon ROI is strongly positive.
    if lands == 2 and 3 <= day <= 10 and horizon >= 16:
        q3_land = 2000
        if realizable >= q3_land + reserve + 150:
            meta["district_commission_v53"] = {
                "district": 3, "bank": round(money, 1),
                "realizable": round(realizable, 1), "reserve": reserve,
                "horizon": horizon,
            }
            return _funding_packet(orders), meta
        meta["q3_capital_gap_v53"] = round(q3_land + reserve + 150 - realizable, 1)

    # Q4: buy only from a functioning Q3 factory and only while a new goose
    # tranche clears the remaining-horizon hurdle.  We deliberately require
    # realized animals/structures rather than forecast capacity.
    if lands == 3 and 7 <= day <= 16 and horizon >= 13:
        q3 = qs[3]
        q3_geese = int(q3.get("geese", 0) or 0)
        q3_struct = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        q4_land = 4000
        if q3_geese >= 8 and q3_struct >= 10 and realizable >= q4_land + reserve + 500:
            meta["district_commission_v53"] = {
                "district": 4, "bank": round(money, 1),
                "realizable": round(realizable, 1), "reserve": reserve,
                "q3_geese": q3_geese, "q3_structures": q3_struct,
                "horizon": horizon,
            }
            return _funding_packet(orders), meta
        meta["q4_gate_v53"] = {
            "cash_gap": round(max(0.0, q4_land + reserve + 500 - realizable), 1),
            "q3_geese": q3_geese, "q3_structures": q3_struct,
        }

    if day >= 24 or lands < 3:
        return orders[:10], meta

    # Own goose capital across BOTH livestock districts. V50 only counted Q3
    # free coops, which made Q4 unable to compound after Q3 filled.
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    total_geese = int(stats.get("geese", 0) or 0) + _pending(obs, "GOOSE")
    coop_capacity = int(qs[3].get("coop", 0) or 0)
    if lands >= 4:
        coop_capacity += int(qs[4].get("coop", 0) or 0)
    free_coops = max(0, coop_capacity - total_geese)

    if day <= 10:
        goose_target = 10
    elif day <= 14:
        goose_target = 18
    elif day <= 18:
        goose_target = 30 if lands >= 4 else 22
    elif day <= 22:
        goose_target = 38 if lands >= 4 else 24
    else:
        goose_target = total_geese

    # Existing feed/seed orders are obligations. Conservatively reserve their
    # quoted cost before allocating the remainder to biological capital.
    prices = _b._prices(obs)
    committed = 0.0
    for o in orders:
        if len(o) < 3: continue
        if o[0] == "BUY_SEED":
            committed += _core.SEED_COST.get(str(o[1]).upper(), 0) * int(o[2])
        elif o[:2] == ["BUY_PRODUCT", "WHEAT"]:
            committed += float(prices.get("WHEAT", 25) or 25) * int(o[2])
    spendable = max(0.0, realizable - reserve - committed)
    need = max(0, goose_target - total_geese)
    affordable = max(0, int(spendable // 300))
    buy = min(6, free_coops, need, affordable)
    if buy > 0 and len(orders) < 10:
        # Sales first, goose capital next, operating orders after it.
        i = 0
        while i < len(orders) and orders[i][0] == "SELL": i += 1
        orders.insert(i, ["BUY_ANIMAL", "GOOSE", buy])
        orders = orders[:10]
        meta["geese_bought_v53"] = buy
        meta["goose_target_v53"] = goose_target
        meta["goose_capacity_v53"] = coop_capacity
        meta["goose_spendable_v53"] = round(spendable, 1)

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
