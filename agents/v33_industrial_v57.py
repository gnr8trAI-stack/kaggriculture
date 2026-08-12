"""V33.57 staged four-district industrial allocator.

V33.56 restored crop saturation and lifted the median back above 32k, but it
never commissioned Q3/Q4. V33.53 proved Q3 mechanics yet over-invested in geese
and starved the crop factory. V33.57 combines the two pieces deliberately:

* retain V56's paid-land crop saturation and V54's daily-feed safety;
* commission Q3 from the first genuinely productive two-district cash packet;
* cap biological capital until Q1/Q2 utilization and labour have recovered;
* commission Q4 only from a functioning Q3 plus healthy crop throughput;
* keep land, animal and operating cash decisions inside one allocator.

This remains the independent V33 architecture; V19/V32 are reference-only.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v56 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator


def _quoted_sales(obs, orders):
    prices = _b._prices(obs); total = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = str(o[1]).upper()
            total += int(o[2]) * float(prices.get(item, _b.VALUE.get(item, 1)) or _b.VALUE.get(item, 1))
    return total


def _pending(obs: Mapping[str, Any], item: str) -> int:
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    n = int(shed.get(item, 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        n += sum(int(_b._m(inv).get(item, 0) or 0) for inv in invs)
    return n


def _land_packet(orders):
    # Atomic capex: same-turn sales fund land before any discretionary purchase.
    out = [list(o) for o in orders if isinstance(o, list) and o and o[0] == "SELL"]
    out.append(["BUY_LAND"])
    return out[:10]


def _capital_allocator(obs, farm, stats):
    parent_orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30-day)
    lands = max(1, int(stats.get("lands", 1) or 1)); money = float(farm.get("money", 0) or 0)
    hands = len(list(farm.get("hands") or [])); qs = stats["districts"]
    q1,q2,q3,q4 = (qs[i] for i in (1,2,3,4))
    prod12 = int(q1.get("productive",0) or 0) + int(q2.get("productive",0) or 0)
    idle12 = int(q1.get("idle",0) or 0) + int(q2.get("idle",0) or 0)

    orders = [list(o) for o in parent_orders if isinstance(o,list) and o]
    # V57 owns expansion and biological capex so the decisions are mutually
    # exclusive and can be ranked against crop/feed operating obligations.
    orders = [o for o in orders if o[0] not in {"BUY_LAND","BUY_ANIMAL"}][:10]
    sale_quote = _quoted_sales(obs, orders)
    realizable = money + 0.88*sale_quote
    animals = int(stats.get("animals",0) or 0)
    reserve = 300 + 35*animals

    meta["allocator_v57"] = {
        "lands": lands, "prod12": prod12, "idle12": idle12,
        "hands": hands, "animals": animals, "realizable": round(realizable,1),
        "reserve": reserve, "horizon": horizon,
    }

    if lands == 1 or day >= 27:
        return parent_orders[:10], meta

    # Q3: V56 reaches roughly 2.8k cash and 26+ productive tiles around D6.
    # Buy the 2k district only when the crop factory is already paying for it;
    # unlike V53, do not pair the land purchase with a large goose tranche.
    if lands == 2 and 4 <= day <= 10 and horizon >= 16:
        need = 2000 + reserve
        if prod12 >= 24 and realizable >= need:
            meta["district_commission_v57"] = {"district":3,"required":round(need,1),"realizable":round(realizable,1)}
            return _land_packet(orders), meta
        meta["q3_gate_v57"] = {"cash_gap":round(max(0.0,need-realizable),1),"productive_gap":max(0,24-prod12)}

    # Q4: explicit four-district operation, but only after Q3 is mechanically
    # proven and Q1/Q2 have recovered. The 4k land must retain at least eight
    # days of runway for a short-payback goose/crop tranche.
    if lands == 3 and 10 <= day <= 20 and horizon >= 9:
        q3_geese = int(q3.get("geese",0) or 0)
        q3_struct = int(q3.get("coop",0) or 0) + int(q3.get("pasture",0) or 0)
        need = 4000 + reserve + 350
        if q3_geese >= 4 and q3_struct >= 4 and prod12 >= 30 and hands >= 7 and realizable >= need:
            meta["district_commission_v57"] = {"district":4,"required":round(need,1),"realizable":round(realizable,1),"q3_geese":q3_geese}
            return _land_packet(orders), meta
        meta["q4_gate_v57"] = {"cash_gap":round(max(0.0,need-realizable),1),"q3_geese":q3_geese,"q3_structures":q3_struct,"prod12":prod12,"hands":hands}

    if lands < 3 or day >= 24:
        return orders[:10], meta

    # Biological capital is subordinate to keeping the paid crop districts
    # utilized. Stage the herd so crop labour/cash can recover after each step.
    private = _b._m(obs.get("private")); prices = _b._prices(obs)
    total_geese = int(stats.get("geese",0) or 0) + _pending(obs,"GOOSE")
    capacity = int(q3.get("coop",0) or 0) + (int(q4.get("coop",0) or 0) if lands >= 4 else 0)
    free = max(0, capacity-total_geese)

    if prod12 < 24 or idle12 >= 18:
        target = total_geese
    elif lands == 3:
        target = 4 if hands < 8 or prod12 < 30 else (8 if day <= 16 else 12)
    else:
        target = 8 if prod12 < 32 else (14 if day <= 18 else 18)

    committed = 0.0
    for o in orders:
        if len(o) < 3: continue
        if o[0] == "BUY_SEED": committed += _core.SEED_COST.get(str(o[1]).upper(),0)*int(o[2])
        elif o[:2] == ["BUY_PRODUCT","WHEAT"]: committed += float(prices.get("WHEAT",25) or 25)*int(o[2])
    spendable = max(0.0, realizable-reserve-committed)
    buy = min(2, free, max(0,target-total_geese), max(0,int(spendable//300)))
    if buy > 0 and len(orders) < 10:
        i=0
        while i < len(orders) and orders[i][0] == "SELL": i += 1
        orders.insert(i,["BUY_ANIMAL","GOOSE",buy]); orders=orders[:10]
        meta["goose_stage_v57"]={"target":target,"buy":buy,"capacity":capacity,"spendable":round(spendable,1)}

    # Four-day feed runway remains mandatory operating capital.
    shed = _b._m(private.get("shed")); invs = private.get("inventories",[])
    wheat = int(shed.get("WHEAT",0) or 0)
    if isinstance(invs,list): wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in invs)
    desired_feed = max(0,(animals+buy)*4)
    already = sum(int(o[2]) for o in orders if len(o)>=3 and o[:2]==["BUY_PRODUCT","WHEAT"])
    gap = max(0,desired_feed-wheat-already)
    if gap > 0 and len(orders) < 10:
        wp = float(prices.get("WHEAT",25) or 25)
        affordable=max(0,int(max(0.0,realizable-committed-250)//max(1.0,wp)))
        qty=min(40,gap,affordable)
        if qty>0: orders.append(["BUY_PRODUCT","WHEAT",qty]); meta["feed_topup_v57"]=qty

    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None): return _p.agent(observation, configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
