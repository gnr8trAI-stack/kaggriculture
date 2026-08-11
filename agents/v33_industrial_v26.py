"""V33.26 herd-first industrial allocator.

Independent V33 architecture.  V33.24 demonstrated safe four-quadrant
commissioning but spent too early on Q4 while Q3 stalled near five cows. This
revision makes Q3 livestock the second compounding engine after the Q1 melon
bootstrap: Q2/Q3 unlock immediately from realized D10 cash, 8-9 dedicated Q3
operators build/service up to 20 cows, and Q4 is deferred until the herd is
mature enough to finance it. Crop districts use V33.25's demand-aware portfolio.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v25 as _v25

_b = _v25._b


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Herd throughput is the binding constraint. Give Q3 roughly half the
        # workforce, capped at nine livestock operators, plus one feed crop hand.
        crew = min(9, max(7, total // 2))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        fi = total - crew - 1
        if fi >= 1:
            roles[fi] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"; moved += 1
    return roles


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day",0) or 0); hour = int(obs.get("hour",0) or 0)
    lands = int(stats.get("lands",0) or 0); tiles = farm.get("tiles") or []
    private = _b._m(obs.get("private")); inv = _b._inventory(private,idx)
    if role == "livestock" and lands >= 3 and day <= 29:
        q3 = stats["districts"][3]; active = int(stats.get("animals",0) or 0)
        target = 16 if day <= 13 else 20 if day <= 22 else max(18,active)
        cells = int(q3.get("unlocked",0) or 0)
        pasture_target = min(target,max(0,cells-3))
        r = _b._livestock_action(obs,farm,idx,p,reserved,target,pasture_target)
        if r is not None: return r
        role = "feed"
    if role == "feed" and lands >= 3: districts={3}
    elif role == "q4" and lands >= 4: districts={4}
    elif role == "q2" and lands >= 2: districts={2}
    else: districts={1}
    task = _b._best_task(tiles,p,_v25._v24._v23._tile_tasks(tiles,districts,reserved),reserved)
    if task is not None: return task
    load = _b._inv_total(inv)
    if load >= 8 or (load > 0 and (hour >= 18 or day >= 28)):
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    if day <= 27 and hour <= 18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_v25._crop_for(day,_b._quadrant(len(tiles),g),obs)
            if seed_budget.get(crop,0)<=0: continue
            rr=_b._route(tiles,p,g)
            if rr is not None: choices.append((rr[0],g[1],g[0],g,crop,rr[1]))
        if choices:
            choices.sort(); dist,_,_,target,crop,first=choices[0]; reserved.add(target)
            if dist==0:
                seed_budget[crop]-=1; return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_to_plant"
    if load>0: return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    return ["PASS"],"idle"


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds"))
    inventories=private.get("inventories",[]); money=float(farm.get("money",0) or 0)
    hands=list(farm.get("hands") or []); lands=max(1,int(stats.get("lands",1) or 1))
    animals=int(stats.get("animals",0) or 0); productive=int(stats.get("productive",0) or 0)
    qs=stats["districts"]; q1,q2,q3,q4=(qs[i] for i in (1,2,3,4))
    orders:List[List[Any]]=[]
    meta:Dict[str,Any]={"land":0,"land_cost":0,"hires":0,"hire_cost":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate=day>=27
    keep_wheat=0 if liquidate else animals*4
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=keep_wheat if item=="WHEAT" else 0
        sell=max(0,qty-keep)
        if sell>0:
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    reserve=700 if lands==1 and day<=10 else 650+60*animals+(500 if day>=24 else 0)
    meta["reserve"]=reserve; spendable=max(0.0,money-reserve)

    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9)
    land_ok=False
    if lands==1:
        land_ok=10<=day<=13 and money>=6500
    elif lands==2:
        # Q3 is not optional: acquire immediately after Q2 while cows still have
        # time to clear their 8-day first-yield delay.
        land_ok=10<=day<=14 and productive>=20 and money>=7500
    elif lands==3:
        q3p=int(q3.get("productive",0) or 0); q3a=int(q3.get("animals",0) or 0); q3past=int(q3.get("pasture",0) or 0)
        # Do not repeat V33.24's premature Q4 capital drain. Herd first.
        land_ok=14<=day<=19 and q3p>=16 and q3past>=16 and q3a>=14 and money>=20000
    expected=max(0,horizon-3)*(1000 if lands==1 else 2300 if lands==2 else 2600)
    roi=(expected-land_cost)/max(1,land_cost); meta["ranked"].append(["land",round(roi,2)])
    bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; meta["land_cost"]=land_cost; bought_land=True; spendable-=land_cost

    # 16 hands on Q3 day gives 8-9 livestock operators while keeping crop engines
    # alive. Daily Fibonacci labour remains cheap enough relative to a cared herd.
    desired=5 if lands==1 else 9 if lands==2 else 16 if lands==3 else 17
    if day>=24: desired=min(desired,14)
    if day>=27: desired=min(desired,11)
    if day>=29: desired=min(desired,8)
    missing=max(0,desired-len(hands))
    if hour<=3 and day<=29 and missing>0 and len(orders)<10:
        add=min(missing,10-len(orders))
        while add>0 and _v25._v24._v23._hire_cost(len(hands),add)>spendable:add-=1
        if add>0:
            cost=_v25._v24._v23._hire_cost(len(hands),add); orders.extend([["HIRE"] for _ in range(add)])
            meta["hires"]=add; meta["hire_cost"]=cost; spendable-=cost
    nh=_v25._v24._v23._hire_cost(len(hands),1); meta["ranked"].append(["labour",round((horizon*180-nh)/max(1,nh),2)])

    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list):total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*5
    if animals and total_wheat<feed_target and day<29 and len(orders)<10:
        need=min(100,feed_target-total_wheat); wp=float(_b._prices(obs).get("WHEAT",25) or 25)
        affordable=max(0,int(max(0.0,spendable-400)//max(1,wp))); buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*wp

    if lands>=3 and day<=20 and not bought_land and len(orders)<10:
        pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0); total=animals+in_shed
        target=16 if day<=13 else 20; capacity=max(0,min(pasture-total,target-total))
        mp=float(_b._prices(obs).get("MILK",160) or 160); cycles=max(0,(horizon-8)//2)
        cow_roi=(cycles*2*mp-400)/400.0; meta["ranked"].append(["cow",round(cow_roi,2)])
        affordable=max(0,int(max(0.0,spendable-700)//400)); buy=min(6,capacity,affordable)
        if buy>0 and cow_roi>0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    if not liquidate and day<=27:
        remaining=max(25,(len(hands)+1)*5); need_by:Dict[str,int]={}
        for q in range(1,lands+1):
            if remaining<=0:break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                pasture_target=16 if day<=13 else 20
                idle=min(idle,max(0,min(3,int(z.get("unlocked",0) or 0)-pasture_target)))
            take=min(idle,remaining,25); remaining-=take
            crop=_v25._crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0); cap=25 if lands==1 and day<=9 and crop=="MELON" else 34
            need=max(0,min(cap,raw+3)-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-250)//cost)); buy=min(need,affordable)
            if buy>0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost
    return orders[:10],meta


_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator

def agent(observation:Any,configuration:Any=None):return _v25.agent(observation,configuration)
def reset_state():return _v25.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _v25.get_telemetry(clear=clear)
