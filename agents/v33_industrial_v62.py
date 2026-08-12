"""V33.62 demand-clock industrial compounding.

Independent V33 architecture built on the strongest measured V33 economic
control (V33.25), not on V19/V32.  This revision changes the operating model:
production and realization are synchronized to the town's deterministic demand
clock, daily labour is sized from live work backlog, and Q4 is commissioned as
short-cycle crop capacity when its remaining-horizon payback is positive.

Q1: melon bootstrap, then demand-priced short crops.
Q2: demand-balanced crop cash engine.
Q3: dairy/feed district with bought wheat operating input.
Q4: ROI-gated short-cycle crop district; no long-duration planting late.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial_v25 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator

BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,
        "EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
SHOP = {
    "BAKERY":{"EGG":1,"WHEAT":1},
    "PIZZA_SHOP":{"MILK":1,"TOMATO":1,"WHEAT":1},
    "BRUNCH_SPOT":{"EGG":1,"WHEAT":1,"STRAWBERRY":1},
    "YARN_STORE":{"WOOL":2},
    "ICE_CREAM_SHOP":{"STRAWBERRY":1,"MILK":1,"WHEAT":1},
    "PET_CAFE":{"CARROT":2},
    "SMOOTHIE_SHOP":{"STRAWBERRY":1,"MILK":1},
    "FARMERS_MARKET":{"WHEAT":1,"CARROT":1,"TOMATO":1,"STRAWBERRY":1},
}
CROP = {
    "WHEAT":(4,4,10), "CARROT":(3,3,20), "TOMATO":(4,11,50),
    "STRAWBERRY":(4,16,100),
}


def _shop_name(v: Any) -> str:
    return str(v or "").upper().replace(" ","_").replace("-","_")


def _daily_demand(obs: Mapping[str,Any], item: str) -> int:
    item=item.upper(); d=0 if item=="FERTILIZER" else 1
    town=_b._m(obs.get("town")); shops=town.get("unlocked_shops",[])
    if isinstance(shops,list):
        for raw in shops:
            d += 6*int(SHOP.get(_shop_name(raw),{}).get(item,0) or 0)
    return d


def _crop_for(day: int, district: int, obs: Mapping[str,Any]) -> str:
    if district==1 and day<=1:
        return "MELON"
    if district==3:
        return "WHEAT"
    horizon=max(0,30-day); prices=_b._prices(obs)
    market=_b._m(obs.get("market")); inv=_b._m(market.get("inventory"))
    allowed=("WHEAT","CARROT","TOMATO","STRAWBERRY")
    scored=[]
    for crop in allowed:
        units,duration,seed=CROP[crop]
        if horizon<duration: continue
        live=float(prices.get(crop,BASE[crop]) or BASE[crop])
        demand=_daily_demand(obs,crop)
        deficit=max(0,10000-int(inv.get(crop,10000) or 10000))
        # Value production that has recurring town absorption; penalize a live glut.
        demand_cover=min(1.8, 0.75 + 0.08*demand)
        scarcity=1.0 + min(0.35, deficit/1200.0)
        glut=0.72 if live < BASE[crop]*0.80 else 0.88 if live < BASE[crop]*0.94 else 1.0
        projected=max(live,BASE[crop]*0.92)*demand_cover*scarcity*glut
        score=(units*projected-seed)/duration
        if district==4 and crop in {"WHEAT","CARROT"}: score*=1.12
        if day>=18 and crop in {"TOMATO","STRAWBERRY"}: score*=0.55
        scored.append((score,crop))
    return max(scored)[1] if scored else "WHEAT"


def _task_backlog(farm: Mapping[str,Any], stats: Mapping[str,Any], day: int) -> int:
    tiles=farm.get("tiles") or []; work=0
    for row in tiles:
        if not isinstance(row,list): continue
        for t in row:
            if not isinstance(t,Mapping): continue
            kind=str(t.get("kind","")).upper()
            if kind=="WEED": work += 1
            elif kind=="PLANT":
                if int(t.get("yield_units",0) or 0)>0: work += 1
                if not bool(t.get("watered_today",False)): work += 1
            elif "animal" in t:
                if not bool(t.get("fed_today",False)): work += 1
                if int(t.get("yield_units",0) or 0)>0: work += 1
                if not bool(t.get("cared_today",False)): work += 1
    # Commission a bounded amount of idle owned surface each day.
    work += min(24,int(stats.get("idle",0) or 0))
    return work


def _hire_cost(existing: int, add: int) -> int:
    # Existing hands were all hired today; nth hire cost is Fibonacci 1,1,2,...
    def fib(n):
        a,b=1,1
        for _ in range(n): a,b=b,a+b
        return a
    return sum(fib(existing+i) for i in range(add))


def _pulse_sell(obs: Mapping[str,Any], item: str, qty: int, day: int, hour: int) -> int:
    if qty<=0: return 0
    if day>=27 or item=="MELON": return qty
    price=float(_b._prices(obs).get(item,BASE.get(item,1)) or BASE.get(item,1))
    demand=_daily_demand(obs,item)
    # Town shops consume after hours 0,4,8,...; hour 1/5/... sees the fresh scarcity.
    pulse=(hour%4)==1
    if item=="FERTILIZER":
        return qty if price>=BASE[item]*0.95 else 0
    if pulse:
        per_pulse=max(1,(demand+5)//6)
        premium=2 if price>=BASE.get(item,1)*1.08 else 1
        return min(qty, per_pulse*premium + (3 if qty>=80 else 0))
    # Capacity safety valve; never let the shed choke the factory.
    if qty>=85: return min(qty, max(8,demand//2))
    if price>=BASE.get(item,1)*1.18: return min(qty,max(2,demand//3))
    return 0


def _quoted_sales(obs, orders) -> float:
    prices=_b._prices(obs); total=0.0
    for o in orders:
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL":
            total += int(o[2])*float(prices.get(str(o[1]).upper(),BASE.get(str(o[1]).upper(),1)) or 1)
    return total


def _capital_allocator(obs, farm, stats):
    orders,meta=_parent_allocator(obs,farm,stats); meta=dict(meta)
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    lands=max(1,int(stats.get("lands",1) or 1)); money=float(farm.get("money",0) or 0)
    animals=int(stats.get("animals",0) or 0); hands=len(list(farm.get("hands") or []))
    qs=stats["districts"]; q3=qs[3]

    # Replace continuous dumping with town-clock realization while retaining all
    # non-sale orders from the V25 capital allocator.
    clean=[]; sale_value=0.0
    for o in orders:
        if not isinstance(o,list) or not o: continue
        if o[0]=="SELL" and len(o)>=3:
            item=str(o[1]).upper(); q=_pulse_sell(obs,item,int(o[2]),day,hour)
            if q>0:
                clean.append(["SELL",item,q]); sale_value += q*float(_b._prices(obs).get(item,BASE.get(item,1)) or 1)
        else:
            clean.append(list(o))

    # JIT labour: remove V25's fixed labour packet and hire to live daily work,
    # not to land count.  One hand has ~24 actions/day; use a conservative 16
    # useful actions after travel/shed overhead.
    clean=[o for o in clean if o[0]!="HIRE"]
    backlog=_task_backlog(farm,stats,day)
    desired=min(15,max(4,(backlog+15)//16))
    if lands>=3: desired=max(desired,9)
    if lands>=4: desired=max(desired,10)
    if day>=25: desired=min(desired,9)
    reserve=500+55*animals+(700 if lands<4 and day<=18 else 0)
    realizable=money+0.90*sale_value
    add=max(0,desired-hands)
    while add>0 and _hire_cost(hands,add)>max(0,realizable-reserve): add-=1
    if hour<=2 and add>0:
        # Preserve order slots for land/feed/seed; the market repeats next turn.
        add=min(add,max(0,10-len(clean)))
        clean.extend([["HIRE"] for _ in range(add)])

    # Q4: explicitly commission when Q3 exists and remaining short-cycle crop
    # margin can repay $4k land plus reserve.  V25's herd>=8/$10k gate was too late.
    if lands==3 and 12<=day<=18 and horizon>=12 and not any(o[0]=="BUY_LAND" for o in clean):
        q3p=int(q3.get("productive",0) or 0); q3a=int(q3.get("animals",0) or 0)
        q12=int(qs[1].get("productive",0) or 0)+int(qs[2].get("productive",0) or 0)
        expected=(horizon-3)*(max(24,q12)*32 + max(4,q3a)*95)
        need=4000+reserve
        if q12>=28 and q3p>=8 and q3a>=5 and realizable>=need and expected>=need*4:
            # SELLs first so same-turn realized cash can fund land.
            sell=[o for o in clean if o[0]=="SELL"]
            rest=[o for o in clean if o[0]!="SELL" and o[0]!="BUY_LAND"]
            clean=(sell+[["BUY_LAND"]]+rest)[:10]
            meta["q4_demand_clock"]={"day":day,"q12":q12,"q3p":q3p,"q3a":q3a,"realizable":round(realizable,1),"expected":round(expected,1)}

    meta["demand_clock_v62"]={"backlog":backlog,"hands":hands,"desired":desired,"realizable":round(realizable,1),"reserve":reserve,"hour":hour}
    return clean[:10],meta


_b._crop_for=_crop_for
_b._capital_allocator=_capital_allocator


def agent(observation: Any, configuration: Any=None): return _p.agent(observation,configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
