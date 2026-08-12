"""V33.55 four-quadrant goose factory with explicit remaining-horizon ROI.

V33.54 restored crop solvency but stopped scaling at ~4 geese and never reached
Q4.  This revision changes the industrial mechanism rather than nudging one
threshold: Q1/Q2 remain the cash engine, Q3/Q4 are commissioned as biological
production districts, and goose capacity scales against actual free coops,
remaining days, daily-feed runway and crop working capital.

V19/V32 remain reference-only and are not imported.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v54 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator
_parent_livestock = _core._livestock_action


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
        n += sum(int(_b._m(inv).get(item, 0) or 0) for inv in invs)
    return n


def _roles(lands: int, hand_count: int):
    """Scale husbandry labour only when the industrial districts exist."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Five Q3 operators still leave >=5 crop units at the normal 9-12 hand
        # dawn footprint.  Idle livestock operators fall back to Q2 through the
        # core executor.
        for i in range(max(1, total - 5), total):
            roles[i] = "livestock3"
    if lands >= 4:
        # The factory is now the dominant marginal-return asset.  Split eight
        # husbandry operators across both districts, leaving the remainder as
        # Q1/Q2/Q4 crop liquidity workers.
        live = min(8, max(4, total - 5))
        q4n = live // 2
        q3n = live - q4n
        for i in range(max(1, total - live), max(1, total - q4n)):
            roles[i] = "livestock3"
        for i in range(max(1, total - q4n), total):
            roles[i] = "livestock4"
        # Give one retained crop unit explicit Q4 surface responsibility.
        for i in range(1, max(1, total - live)):
            if roles[i] in {"q1", "q2"}:
                roles[i] = "q4"
                break
    return roles


_core._roles = _roles
_b._roles = _roles


def _extra_coop(obs, farm, idx, p, stats, reserved, district: int):
    """Extend the industrial district to almost the full 5x5 quadrant."""
    day = int(obs.get("day", 0) or 0)
    if day > 22:
        return None
    q = stats["districts"][district]
    coops = int(q.get("coop", 0) or 0)
    # One crop cell remains available as a routing / opportunistic crop surface.
    target = 23
    if coops >= target:
        return None
    tiles = farm.get("tiles") or []
    goals = _b._empty_targets(tiles, {district}, reserved)
    r = _core._nearest(tiles, p, goals)
    if r is None:
        return None
    reserved.add(r[3])
    return _core._go(tiles, p, r[3], ["BUILD_COOP"]), "build_extra_coop_v55"


def _livestock_action(obs, farm, idx, p, stats, reserved, district: int):
    # V54's wrapper already enforces daily feed before discretionary work.
    result = _parent_livestock(obs, farm, idx, p, stats, reserved, district)
    if result is not None:
        action, label = result
        # Do not build pastures in V55: egg throughput is materially more robust
        # to glut than milk/wool and has the shortest first-yield horizon.
        if label == "build_pasture":
            return _extra_coop(obs, farm, idx, p, stats, reserved, district)
        return result
    return _extra_coop(obs, farm, idx, p, stats, reserved, district)


_core._livestock_action = _livestock_action


def _clean(orders):
    return [list(o) for o in orders if isinstance(o, list) and o and o[0] not in {"BUY_LAND", "BUY_ANIMAL"}][:10]


def _insert_after_sales(orders, order):
    out = [list(o) for o in orders if isinstance(o, list) and o]
    i = 0
    while i < len(out) and out[i][0] == "SELL":
        i += 1
    out.insert(i, order)
    return out[:10]


def _capital_allocator(obs, farm, stats):
    base_orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30 - day)
    money = float(farm.get("money", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1)); qs = stats["districts"]
    if lands == 1:
        return base_orders[:10], meta

    orders = _clean(base_orders)
    sale_quote = _quoted_sales(obs, orders)
    realizable = money + 0.82 * sale_quote
    animals = int(stats.get("animals", 0) or 0)
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))
    prod12 = int(q1.get("productive", 0) or 0) + int(q2.get("productive", 0) or 0)
    idle12 = int(q1.get("idle", 0) or 0) + int(q2.get("idle", 0) or 0)

    # Working capital is intentionally compact: enough to refill a short crop
    # packet and buy three days of wheat at roughly equilibrium prices.
    crop_reserve = 520 + 10 * min(30, idle12)
    feed_reserve = 75 * animals
    execution_buffer = 220
    reserve = crop_reserve + feed_reserve + execution_buffer
    meta["industrial_reserve_v55"] = reserve
    meta["realizable_cash_v55"] = round(realizable, 1)

    # Q3: unlock while at least 18 days remain for eggs.  Require a live two-
    # quadrant crop base, but do not wait for a cash peak tied to one harvest
    # boundary.  Land itself is only 2k; the retained reserve commissions it.
    if lands == 2 and 4 <= day <= 10 and horizon >= 18:
        land_cost = 2000
        # Two crop districts must still be genuinely operating.
        roi = ((horizon - 5) * 23 * 38 - land_cost) / land_cost
        need = land_cost + reserve
        meta["q3_land_roi_v55"] = round(roi, 2)
        if prod12 >= 18 and roi > 0 and realizable >= need:
            orders = _insert_after_sales(orders, ["BUY_LAND"])
            meta["district_commission_v55"] = {"district": 3, "required": round(need, 1), "horizon": horizon}
            return orders[:10], meta

    # Q4: second biological district.  Buy it as soon as Q3 demonstrates a
    # physical goose base and the remaining-horizon egg margin covers land plus
    # one commissioning tranche.  This is an ROI decision, not a fixed-date buy.
    if lands == 3 and 7 <= day <= 15 and horizon >= 14:
        q3_geese = int(q3.get("geese", 0) or 0)
        q3_coops = int(q3.get("coop", 0) or 0)
        land_cost = 4000
        roi = ((horizon - 5) * 23 * 38 - land_cost) / land_cost
        need = land_cost + reserve + 900
        meta["q4_land_roi_v55"] = round(roi, 2)
        if q3_geese >= 6 and q3_coops >= 8 and roi > 0 and realizable >= need:
            orders = _insert_after_sales(orders, ["BUY_LAND"])
            meta["district_commission_v55"] = {"district": 4, "required": round(need, 1), "q3_geese": q3_geese, "horizon": horizon}
            return orders[:10], meta

    if day >= 25 or lands < 3:
        return orders[:10], meta

    # Crop liquidity survives the goose ramp.  Only refill when Q1/Q2 have
    # material idle surface; livestock never consumes this committed packet.
    private = _b._m(obs.get("private")); seeds = _b._m(private.get("seeds"))
    if idle12 >= 10 and not any(o[0] == "BUY_SEED" for o in orders) and len(orders) < 10:
        crop = "CARROT" if day <= 20 else "WHEAT"
        have = int(seeds.get(crop, 0) or 0)
        want = max(0, min(28, idle12 + 2) - have)
        cost = _core.SEED_COST[crop]
        budget = max(0.0, realizable - feed_reserve - 380)
        buy = min(want, max(0, int(budget // cost)))
        if buy > 0:
            orders.append(["BUY_SEED", crop, buy])
            meta["crop_packet_v55"] = {crop: buy}

    prices = _b._prices(obs)
    committed = 0.0
    for o in orders:
        if len(o) < 3:
            continue
        if o[0] == "BUY_SEED":
            committed += _core.SEED_COST.get(str(o[1]).upper(), 0) * int(o[2])
        elif o[:2] == ["BUY_PRODUCT", "WHEAT"]:
            committed += float(prices.get("WHEAT", 25) or 25) * int(o[2])

    # Capacity-backed goose compounding.  Egg's official glut curve is shallow:
    # one full-field 24-day throughput only moves $50 -> ~$40, so V55 prefers
    # many geese over premium milk/wool once structures exist.
    total_geese = int(stats.get("geese", 0) or 0) + _pending(obs, "GOOSE")
    coop_capacity = int(q3.get("coop", 0) or 0) + (int(q4.get("coop", 0) or 0) if lands >= 4 else 0)
    free = max(0, coop_capacity - total_geese)
    if day <= 10:
        target = 12
    elif day <= 14:
        target = 24
    elif day <= 18:
        target = 36 if lands >= 4 else 24
    elif day <= 22:
        target = 44 if lands >= 4 else 28
    else:
        target = total_geese

    spendable = max(0.0, realizable - reserve - committed)
    need_geese = max(0, target - total_geese)
    # Purchase at most eight per packet so placement can catch up and the next
    # turn re-prices operating reserve from the new herd size.
    goose_buy = min(8, free, need_geese, max(0, int(spendable // 300)))
    if goose_buy > 0 and len(orders) < 10:
        orders = _insert_after_sales(orders, ["BUY_ANIMAL", "GOOSE", goose_buy])
        meta["geese_bought_v55"] = goose_buy
        meta["goose_target_v55"] = target
        meta["goose_capacity_v55"] = coop_capacity
        spendable -= 300 * goose_buy

    # Daily-feed solvency.  Four days of wheat covers routing delays and avoids
    # the V53 escape/care collapse.  Feed has seniority over further seed/livestock
    # discretionary spend once the herd exists.
    shed = _b._m(private.get("shed")); invs = private.get("inventories", [])
    wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(invs, list):
        wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in invs)
    feed_target = (animals + goose_buy) * 4
    existing_feed = sum(int(o[2]) for o in orders if len(o) >= 3 and o[:2] == ["BUY_PRODUCT", "WHEAT"])
    gap = max(0, feed_target - wheat - existing_feed)
    if gap > 0 and len(orders) < 10:
        wheat_price = float(prices.get("WHEAT", 25) or 25)
        aff = max(0, int(max(0.0, realizable - committed - 180) // max(1.0, wheat_price)))
        qty = min(90, gap, aff)
        if qty > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", qty])
            meta["feed_topup_v55"] = qty

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
