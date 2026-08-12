"""V33.50 cash-first goose-compounding industrial allocator.

V33.49 improved terminal cash but still unlocked Q3 before the crop engine had
working capital, then stalled around two geese.  This revision changes the
capital sequence rather than another cosmetic threshold:

* Q1/Q2 must accumulate a real commissioning packet before Q3 is purchased.
* Once Q3 exists, geese are the first biological-capital tranche because their
  verified first-yield/payback horizon is materially shorter than cow/sheep.
* Structures remain capital-backed by V49's executor guard; purchases are made
  only into already-built free coops.
* Q4 is deferred until Q3 has a self-funding goose base and enough realizable
  cash to buy land without starving feed/replanting.
* Crop working capital is preserved explicitly through the Q3 ramp.

V19.2 is not imported and remains reference control only.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v49 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _quoted_sales(obs, orders):
    prices = _b._prices(obs)
    value = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = str(o[1]).upper()
            value += int(o[2]) * float(prices.get(item, _b.VALUE.get(item, 1)) or _b.VALUE.get(item, 1))
    return value


def _pending_species(obs: Mapping[str, Any], species: str) -> int:
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    n = int(shed.get(species, 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        for inv in invs:
            n += int(_b._m(inv).get(species, 0) or 0)
    return n


def _keep_order(o):
    return isinstance(o, list) and bool(o)


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1))
    money = float(farm.get("money", 0) or 0)
    sales_quote = _quoted_sales(obs, orders)
    realizable = money + 0.85 * sales_quote
    qs = stats["districts"]
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))

    # Q3 must be funded, not merely affordable.  V48/V49 bought it around step
    # 124 while median cash was still ~1k and subsequently could not capitalize
    # the district.  Require two working crop districts plus a 4.8k packet.
    if lands == 2:
        prod12 = int(q1.get("productive", 0) or 0) + int(q2.get("productive", 0) or 0)
        allow_q3 = (
            5 <= day <= 13
            and prod12 >= 22
            and realizable >= 4800
        )
        if not allow_q3:
            orders = [o for o in orders if not (_keep_order(o) and o[0] == "BUY_LAND")]
            meta["q3_deferred_v50"] = {
                "realizable": round(realizable, 1),
                "crop_productive": prod12,
            }

    # Q4 is a second scale step, not a rescue purchase.  Require a productive
    # Q3 goose base and enough realizable cash to preserve a full operating
    # reserve after the verified 4k third-land price.
    if lands == 3:
        q3_geese = int(q3.get("geese", 0) or 0)
        q3_struct = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        allow_q4 = (
            day <= 17
            and q3_geese >= 10
            and q3_struct >= 12
            and realizable >= 8200
        )
        if not allow_q4:
            orders = [o for o in orders if not (_keep_order(o) and o[0] == "BUY_LAND")]
            meta["q4_deferred_v50"] = {
                "q3_geese": q3_geese,
                "q3_structures": q3_struct,
                "realizable": round(realizable, 1),
            }

    if day >= 27 or lands < 3:
        return orders[:10], meta

    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    q3_geese = int(q3.get("geese", 0) or 0)
    pending_geese = _pending_species(obs, "GOOSE")
    total_geese = q3_geese + pending_geese
    coops = int(q3.get("coop", 0) or 0)
    free_slots = max(0, coops - total_geese)

    # Parent revisions occasionally choose cow/sheep while Q3 is still tiny.
    # During bootstrap, use the shorter-payback goose tranche first.  Preserve
    # sales/feed/seed/land/hire orders but own livestock purchasing here.
    controlled = []
    for o in orders:
        if not _keep_order(o):
            continue
        if o[0] == "BUY_ANIMAL" and len(o) >= 2:
            continue
        controlled.append(o)
    orders = controlled[:10]

    # Operating reserve is feed + one crop packet + execution cushion.  We value
    # quoted same-step sales conservatively; no double-spending against full
    # market quote.  Target rises only while enough horizon remains for egg cash.
    active_animals = int(stats.get("animals", 0) or 0)
    reserve = 900 + 55 * active_animals
    if lands == 3 and q3_geese >= 10 and day <= 17:
        # Begin accumulating Q4 land packet without freezing biological growth.
        reserve += 1000
    spendable = max(0.0, realizable - reserve)

    if day <= 12:
        goose_target = 8
    elif day <= 17:
        goose_target = 16
    elif day <= 22:
        goose_target = 22
    else:
        goose_target = total_geese

    need = max(0, goose_target - total_geese)
    affordable = max(0, int(spendable // 300))
    buy = min(4, free_slots, need, affordable)
    if buy > 0 and len(orders) < 10:
        # Funding sales execute in the same market packet. Keep this after sales
        # but before discretionary seed expansion where possible.
        insert_at = 0
        while insert_at < len(orders) and orders[insert_at][0] == "SELL":
            insert_at += 1
        orders.insert(insert_at, ["BUY_ANIMAL", "GOOSE", buy])
        orders = orders[:10]
        meta["geese_bought_v50"] = buy
        meta["goose_target_v50"] = goose_target
        meta["goose_free_slots_v50"] = free_slots
        meta["goose_realizable_v50"] = round(realizable, 1)
        spendable -= 300 * buy

    # Feed is survival capex.  Keep a three-day buffer across all animals; parent
    # feed orders are retained, but top up if the Q3 ramp outruns them.
    wheat = int(shed.get("WHEAT", 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        wheat += sum(int(_b._m(inv).get("WHEAT", 0) or 0) for inv in invs)
    feed_target = max(0, (active_animals + buy) * 3)
    already_feed = sum(int(o[2]) for o in orders if len(o) >= 3 and o[:2] == ["BUY_PRODUCT", "WHEAT"])
    feed_gap = max(0, feed_target - wheat - already_feed)
    if feed_gap > 0 and len(orders) < 10:
        feed_buy = min(40, feed_gap, max(0, int(spendable // 10)))
        if feed_buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", feed_buy])
            meta["feed_topup_v50"] = feed_buy

    # Protect the Q1/Q2 cash engine through the biological ramp.  If no seed buy
    # survived the parent allocator, reserve a small fast-cycle packet instead of
    # allowing all working capital to migrate into livestock.
    if day <= 20 and not any(o[0] == "BUY_SEED" for o in orders if _keep_order(o)) and len(orders) < 10:
        seeds = _b._m(private.get("seeds"))
        idle12 = int(q1.get("idle", 0) or 0) + int(q2.get("idle", 0) or 0)
        crop = "WHEAT" if day <= 10 else "CARROT"
        have = int(seeds.get(crop, 0) or 0)
        want = max(0, min(20, idle12 + 4) - have)
        cost = 10 if crop == "WHEAT" else 20
        seed_budget = max(0.0, spendable - 350)
        seed_buy = min(want, max(0, int(seed_budget // cost)))
        if seed_buy > 0:
            orders.append(["BUY_SEED", crop, seed_buy])
            meta["crop_packet_v50"] = {crop: seed_buy}

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
