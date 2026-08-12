"""V33.56 crop-saturation industrial allocator.

V33.54 is the stable mechanics baseline (24/24 DONE, median 17.6k) but its
telemetry exposes the dominant economic bottleneck: Q1/Q2 repeatedly fall from
~40 productive tiles to ~10 because replenishment buys only a handful of seeds
while 30-40 owned crop tiles sit idle.  V33.56 changes the capital allocator,
not action mechanics: owned crop land is treated as already-paid productive
capital and refilling it outranks new livestock or land whenever remaining-
horizon crop ROI is positive.

The controller remains the independent V33 architecture; V19/V32 are not
imported.  V54's daily-feed husbandry and zero-invalid execution are retained.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v54 as _p
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


def _seed_inventory(obs, crop):
    private = _b._m(obs.get("private")); seeds = _b._m(private.get("seeds"))
    return int(seeds.get(crop, 0) or 0)


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30-day)
    lands = max(1, int(stats.get("lands", 1) or 1)); money = float(farm.get("money", 0) or 0)
    qs = stats["districts"]; q1,q2 = qs[1],qs[2]
    idle12 = int(q1.get("idle",0) or 0) + int(q2.get("idle",0) or 0)
    prod12 = int(q1.get("productive",0) or 0) + int(q2.get("productive",0) or 0)

    # The bootstrap packet at one land is proven and must remain atomic.
    if lands == 1 or day >= 27:
        return orders[:10], meta

    # Existing crop land has no further land capex.  When >=8 crop tiles are
    # idle, saturating them is senior to BUY_ANIMAL and discretionary BUY_LAND.
    # Preserve same-turn sales, mandatory feed and hires, then fund exactly the
    # crops the V45 district workers are asking to plant.
    if idle12 >= 8 and horizon >= 3:
        kept=[]
        for o in orders:
            if not isinstance(o,list) or not o: continue
            if o[0] in {"BUY_SEED","BUY_ANIMAL"}: continue
            # If crop utilization has collapsed, defer Q3/Q4 one packet rather
            # than buying more capital while paid-for tiles are idle.
            if o[0] == "BUY_LAND" and prod12 < 30: continue
            kept.append(list(o))
        orders=kept[:10]

        sale_quote=_quoted_sales(obs,orders)
        realizable=money + 0.90*sale_quote
        prices=_b._prices(obs)
        animals=int(stats.get("animals",0) or 0)
        committed=0.0
        for o in orders:
            if len(o)>=3 and o[:2]==["BUY_PRODUCT","WHEAT"]:
                committed += int(o[2])*float(prices.get("WHEAT",25) or 25)
        # Daily-feed runway + small execution cushion; crop seeds themselves
        # are the working-capital reserve, not an additional cash hoard.
        reserve = 250 + 45*animals
        budget=max(0.0,realizable-committed-reserve)

        wants=[]
        for q,z in ((1,q1),(2,q2)):
            idle=int(z.get("idle",0) or 0)
            if idle<=0: continue
            crop=_core._crop_for(day,q,obs)
            cost=int(_core.SEED_COST.get(crop,10) or 10)
            have=_seed_inventory(obs,crop)
            # District-local target plus a small rolling buffer.  Duplicate crop
            # requests are merged below so aggregate private seed inventory is
            # not double-counted.
            wants.append((crop,idle+6,cost))
        merged={}
        for crop,want,cost in wants:
            prev=merged.get(crop,[0,cost]); prev[0]+=want; merged[crop]=prev
        seed_meta={}
        for crop,(raw_need,cost) in sorted(merged.items(), key=lambda kv: kv[1][0], reverse=True):
            if len(orders)>=10 or budget < cost: break
            have=_seed_inventory(obs,crop)
            need=max(0,min(52,raw_need)-have)
            buy=min(need,max(0,int(budget//cost)))
            if buy>0:
                # Sales first, then seed working capital, then the surviving
                # feed/hire/capex packet.
                idx=0
                while idx<len(orders) and orders[idx][0]=="SELL": idx+=1
                orders.insert(idx,["BUY_SEED",crop,buy]); orders=orders[:10]
                budget-=buy*cost; seed_meta[crop]=buy
        meta["crop_saturation_v56"]={"idle12":idle12,"productive12":prod12,"seed_buy":seed_meta,"budget_after":round(budget,1)}

    # Only after Q1/Q2 are operating near capacity may biological/land capex
    # survive the packet.  Parent V54 still owns ROI, reserve and Q3/Q4 rules.
    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)

def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
