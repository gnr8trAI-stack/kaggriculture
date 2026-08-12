"""V33.54 crop-funded livestock with hard husbandry solvency.

V33.53 proved the Q3 mechanism and reached a median nine geese, but telemetry
showed the economic failure clearly: Q1/Q2 fell to zero productive tiles while
cash was recycled into geese, then the herd suffered a service/feed collapse.
This revision preserves the funding factory before biological scaling and makes
animal survival a first-class operating obligation.

Mechanisms:
* Q3 is still senior land, but only with a post-purchase crop working-capital
  packet rather than buying land and animals out of the same thin cash balance.
* Goose purchases compete only for cash above crop/feed reserve and committed
  seed/feed orders.
* Every unfed animal is a daily priority. This both eliminates escape risk and
  makes CARE bonuses realizable on subsequent fed production days.
* Q4 remains ROI-gated on a functioning Q3 factory plus a cash commissioning
  packet. V19/V32 remain reference-only and are not imported.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v53 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_base_allocator = _p._base_allocator
_base_livestock = _core._livestock_action


def _quoted_sales(obs, orders):
    prices = _b._prices(obs); value = 0.0
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


def _daily_feed_first(obs, farm, idx, p, stats, reserved, district: int):
    """Feed every animal daily before discretionary husbandry/construction."""
    tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); inv = _b._inventory(private, idx)
    active = []
    for kind in ("COOP", "PASTURE"):
        for g, t in _core._structure_cells(tiles, district, kind):
            if _core._species(t):
                active.append((g, t))
    unfed = [g for g, t in active if not bool(t.get("fed_today", False)) and g not in reserved]
    if unfed:
        if int(inv.get("WHEAT", 0) or 0) > 0:
            r = _core._nearest(tiles, p, unfed)
            if r is not None:
                reserved.add(r[3])
                return _core._go(tiles, p, r[3], ["FEED"]), "feed_daily_v54"
        wheat = int(shed.get("WHEAT", 0) or 0)
        if wheat > 0:
            return _b._to_shed(tiles, p, ["PICKUP", "WHEAT", min(12, wheat)]), "pickup_daily_feed_v54"
    return None


def _livestock_action(obs, farm, idx, p, stats, reserved, district: int):
    urgent = _daily_feed_first(obs, farm, idx, p, stats, reserved, district)
    if urgent is not None:
        return urgent
    return _base_livestock(obs, farm, idx, p, stats, reserved, district)


_core._livestock_action = _livestock_action


def _roles(lands: int, hand_count: int):
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total): roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        for i in range(max(1, total - 4), total): roles[i] = "livestock3"
    if lands >= 4:
        for i in range(max(1, total - 7), max(1, total - 3)): roles[i] = "livestock3"
        for i in range(max(1, total - 3), total): roles[i] = "livestock4"
    return roles


_core._roles = _roles
_b._roles = _roles


def _clean(orders):
    return [list(o) for o in orders if isinstance(o, list) and o and o[0] not in {"BUY_LAND", "BUY_ANIMAL"}][:10]


def _fund_land(orders):
    out = [list(o) for o in orders if isinstance(o, list) and o and o[0] == "SELL"]
    out.append(["BUY_LAND"])
    return out[:10]


def _capital_allocator(obs, farm, stats):
    base_orders, meta = _base_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30 - day)
    money = float(farm.get("money", 0) or 0)
    lands = max(1, int(stats.get("lands", 1) or 1)); qs = stats["districts"]
    if lands == 1:
        return base_orders[:10], meta

    orders = _clean(base_orders)
    sale_quote = _quoted_sales(obs, orders)
    realizable = money + 0.85 * sale_quote
    animals = int(stats.get("animals", 0) or 0)
    q1, q2, q3, q4 = (qs[i] for i in (1, 2, 3, 4))
    idle12 = int(q1.get("idle", 0) or 0) + int(q2.get("idle", 0) or 0)
    prod12 = int(q1.get("productive", 0) or 0) + int(q2.get("productive", 0) or 0)

    # Seed capital needed to refill roughly half a crop district plus daily-feed
    # runway. This is working capital, not dead reserve.
    crop_reserve = 950 if idle12 >= 18 else 650
    feed_reserve = 30 * animals
    reserve = crop_reserve + feed_reserve + 200
    meta["industrial_reserve_v54"] = reserve
    meta["crop_funding_state_v54"] = {"productive12": prod12, "idle12": idle12}
    meta["realizable_cash_v54"] = round(realizable, 1)

    # Q3 later than V53 by only the time needed to retain a genuine crop packet.
    if lands == 2 and 4 <= day <= 11 and horizon >= 15:
        need = 2000 + reserve
        if realizable >= need:
            meta["district_commission_v54"] = {"district": 3, "bank": round(money,1), "required": round(need,1), "horizon": horizon}
            return _fund_land(orders), meta
        meta["q3_capital_gap_v54"] = round(need - realizable, 1)

    # Q4 is funded only after Q3 has survived long enough to prove serviceability.
    if lands == 3 and 9 <= day <= 17 and horizon >= 12:
        q3_geese = int(q3.get("geese", 0) or 0)
        q3_struct = int(q3.get("coop", 0) or 0) + int(q3.get("pasture", 0) or 0)
        need = 4000 + reserve + 500
        if q3_geese >= 8 and q3_struct >= 10 and realizable >= need:
            meta["district_commission_v54"] = {"district": 4, "bank": round(money,1), "required": round(need,1), "q3_geese": q3_geese, "horizon": horizon}
            return _fund_land(orders), meta
        meta["q4_gate_v54"] = {"cash_gap": round(max(0.0,need-realizable),1), "q3_geese": q3_geese, "q3_structures": q3_struct}

    if day >= 24 or lands < 3:
        return orders[:10], meta

    # If the crop engine is sparse, seed working capital outranks another goose.
    has_seed_order = any(o[0] == "BUY_SEED" for o in orders)
    private = _b._m(obs.get("private")); seeds = _b._m(private.get("seeds"))
    if idle12 >= 12 and not has_seed_order and len(orders) < 10:
        crop = "CARROT" if day <= 20 else "WHEAT"
        have = int(seeds.get(crop, 0) or 0)
        want = max(0, min(24, idle12) - have)
        cost = _core.SEED_COST[crop]
        budget = max(0.0, realizable - feed_reserve - 500)
        buy = min(want, max(0, int(budget // cost)))
        if buy > 0:
            orders.append(["BUY_SEED", crop, buy])
            meta["crop_rescue_packet_v54"] = {crop: buy}

    # Account for all committed operating purchases before biological capex.
    prices = _b._prices(obs); committed = 0.0
    for o in orders:
        if len(o) < 3: continue
        if o[0] == "BUY_SEED": committed += _core.SEED_COST.get(str(o[1]).upper(),0) * int(o[2])
        elif o[:2] == ["BUY_PRODUCT","WHEAT"]: committed += float(prices.get("WHEAT",25) or 25) * int(o[2])

    total_geese = int(stats.get("geese", 0) or 0) + _pending(obs, "GOOSE")
    coop_capacity = int(q3.get("coop", 0) or 0) + (int(q4.get("coop", 0) or 0) if lands >= 4 else 0)
    free = max(0, coop_capacity - total_geese)
    if day <= 12: target = 6
    elif day <= 16: target = 12
    elif day <= 20: target = 22 if lands >= 4 else 16
    elif day <= 23: target = 30 if lands >= 4 else 18
    else: target = total_geese

    spendable = max(0.0, realizable - reserve - committed)
    need = max(0, target - total_geese)
    buy = min(4, free, need, max(0, int(spendable // 300)))
    if buy > 0 and len(orders) < 10:
        i = 0
        while i < len(orders) and orders[i][0] == "SELL": i += 1
        orders.insert(i, ["BUY_ANIMAL", "GOOSE", buy]); orders = orders[:10]
        meta["geese_bought_v54"] = buy; meta["goose_target_v54"] = target; meta["goose_spendable_v54"] = round(spendable,1)

    # Daily feed doubles as care-bonus enablement. Hold a four-day wheat runway.
    shed = _b._m(private.get("shed")); invs = private.get("inventories", [])
    wheat = int(shed.get("WHEAT", 0) or 0)
    if isinstance(invs, list): wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in invs)
    feed_target = max(0, (animals + buy) * 4)
    already = sum(int(o[2]) for o in orders if len(o)>=3 and o[:2]==["BUY_PRODUCT","WHEAT"])
    gap = max(0, feed_target - wheat - already)
    if gap > 0 and len(orders) < 10:
        price = float(prices.get("WHEAT",25) or 25)
        # Feed is mandatory operating capex; permit it to consume the feed reserve.
        affordable = max(0, int(max(0.0, realizable - committed - 250) // max(1.0, price)))
        qty = min(50, gap, affordable)
        if qty > 0:
            orders.append(["BUY_PRODUCT","WHEAT",qty]); meta["feed_topup_v54"] = qty

    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
