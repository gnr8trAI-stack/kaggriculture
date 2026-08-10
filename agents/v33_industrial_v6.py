"""V33.6 crop-first industrial cashflow candidate.

Independent V33 architecture.  V33.5 demonstrated that four-land utilization and
large daily labour pools are mechanically achievable, but over-bought seed and
livestock capital before revenue compounded.  V33.6 constrains working capital,
uses the frontier strawberry-heavy crop mix, and delays livestock capex until
cashflow has paid for the crop engine.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial as _b

_b.HIRE_COST = 1
_base_unit_action = _b._unit_action


def _crop_for(day:int,district:int,obs:Mapping[str,Any])->str:
    if district == 3:
        return "WHEAT"
    if day <= 20:
        return "STRAWBERRY"
    if day <= 25:
        return "CARROT"
    return "WHEAT"


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    # Preserve V33.5 maturity-gated behaviour if available in the core state;
    # otherwise use the independent V33 router.  Inventory liquidation remains
    # first priority after a successful harvest.
    inv=_b._inventory(_b._m(obs.get("private")),idx)
    if _b._inv_total(inv)>0:
        return _b._to_shed(farm.get("tiles") or [],p,["DROP"]),"drop_inventory"
    return _base_unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role)


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds"))
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    lands=int(stats.get("lands",1) or 1); animals=int(stats.get("animals",0) or 0); qs=stats["districts"]
    orders=[]; meta:Dict[str,Any]={"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate=day>=28

    # Revenue conversion is always first.
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0)
        keep=animals*3 if item=="WHEAT" and not liquidate else 0
        sell=max(0,qty-keep)
        if sell>0:
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    # Daily labour roughly matches the 9-10 HIRE/day frontier signature.
    desired={1:8,2:9,3:10,4:10}.get(lands,8)
    if day<=27:
        for _ in range(min(10-len(orders),max(0,desired-len(hands)))):
            if money<25:break
            orders.append(["HIRE"]);meta["hires"]+=1;money-=1

    # Preserve operating cash.  Land buys are serial and require retained cash.
    land_gate={1:(4,2200),2:(7,3000),3:(10,4000)}
    if lands<4 and horizon>=9 and len(orders)<10:
        min_day,min_cash=land_gate[lands]
        if day>=min_day and money>=min_cash:
            orders.append(["BUY_LAND"]);meta["land"]=1;money-=1000

    # Small seed pool, replenished only as consumed. Avoid V33.5's 12k seed burn.
    active=list(range(1,lands+1))
    crop_targets:Dict[str,int]={}
    for q in active:
        crop=_crop_for(day,q,obs)
        idle=int(qs[q].get("idle",0) or 0)
        if q==3: idle=min(idle,12)
        crop_targets[crop]=crop_targets.get(crop,0)+min(12,max(2,idle))
    reserve=1200 if lands<4 else 800
    for crop,raw in sorted(crop_targets.items(),key=lambda kv:-kv[1]):
        if len(orders)>=10:break
        have=int(seeds.get(crop,0) or 0)+int(meta["seeds"].get(crop,0) or 0)
        target=min(18,max(6,raw))
        need=max(0,target-have)
        affordable=max(0,int(max(0.0,money-reserve)//_b.SEED_COST[crop]))
        buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_SEED",crop,buy]);meta["seeds"][crop]=buy;money-=buy*_b.SEED_COST[crop]

    # Livestock only after crop engine has generated substantial retained cash.
    if lands>=3 and day<=22 and money>=12000 and len(orders)<10:
        pastures=int(qs[3].get("pasture",0) or 0); cows=animals+int(shed.get("COW",0) or 0)
        target=6 if money<20000 else 10 if money<35000 else 14
        cap=max(0,min(pastures-cows,target-cows)); affordable=max(0,int((money-5000)//400))
        buy=min(2,cap,affordable)
        if buy>0:
            orders.append(["BUY_ANIMAL","COW",buy]);meta["cows"]=buy;money-=400*buy
    wheat=int(shed.get("WHEAT",0) or 0); feed_need=max(0,animals*3-wheat)
    if feed_need>0 and money>2500 and len(orders)<10:
        buy=min(feed_need,12);orders.append(["BUY_PRODUCT","WHEAT",buy]);meta["feed"]=buy;money-=25*buy

    meta["reserve"]=money
    return orders[:10],meta


_b._crop_for=_crop_for
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def reset_state():return _b.reset_state()
def reset_telemetry():return _b.reset_telemetry()
def get_telemetry(clear:bool=False):return _b.get_telemetry(clear=clear)
def agent(observation:Any,configuration:Any=None):return _b.agent(observation,configuration)
