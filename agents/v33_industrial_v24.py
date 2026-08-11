"""V33.24 bootstrap-preserving industrial surge.

V33.23 proved the clean V33 executor can safely operate three districts, 50+
productive tiles and 11 day-workers, but it diluted the proven first melon cash
cycle by buying Q2 at game start and then capped Q3 at only ~5 cows.  V33.24
keeps Q1 concentrated through the first day-10 melon harvest, then reinvests
realized cash into Q2 crops, Q3 16-cow livestock/feed, and ROI-positive Q4.
Labour continues to use the true per-day Fibonacci hire economics.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v23 as _v23

_b=_v23._b


def _roles(lands:int,hand_count:int)->List[str]:
    total=hand_count+1
    roles=["q1"]*total
    if lands>=2:
        for i in range(1,total):
            roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        crew=min(4,max(2,total//4))
        for i in range(max(1,total-crew),total):
            roles[i]="livestock"
        fi=total-crew-1
        if fi>=1: roles[fi]="feed"
    if lands>=4:
        moved=0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<3:
                roles[i]="q4"; moved+=1
    return roles


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    lands=int(stats.get("lands",0) or 0); tiles=farm.get("tiles") or []
    private=_b._m(obs.get("private")); inv=_b._inventory(private,idx)
    if role=="livestock" and lands>=3 and day<=28:
        q3=stats["districts"][3]; active=int(stats.get("animals",0) or 0)
        target=12 if day<=13 else 16 if day<=22 else max(12,active)
        q3_cells=int(q3.get("unlocked",0) or 0)
        pasture_target=min(target,max(0,q3_cells-5))
        r=_b._livestock_action(obs,farm,idx,p,reserved,target,pasture_target)
        if r is not None:return r
        role="feed"
    if role=="feed" and lands>=3: districts={3}
    elif role=="q4" and lands>=4: districts={4}
    elif role=="q2" and lands>=2: districts={2}
    else: districts={1}
    task=_b._best_task(tiles,p,_v23._tile_tasks(tiles,districts,reserved),reserved)
    if task is not None:return task
    load=_b._inv_total(inv)
    if load>=8 or (load>0 and (hour>=18 or day>=28)):
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    if day<=27 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_v23._crop_for(day,_b._quadrant(len(tiles),g),obs)
            if seed_budget.get(crop,0)<=0:continue
            rr=_b._route(tiles,p,g)
            if rr is not None:choices.append((rr[0],g[1],g[0],g,crop,rr[1]))
        if choices:
            choices.sort(); dist,_,_,target,crop,first=choices[0]; reserved.add(target)
            if dist==0:
                seed_budget[crop]-=1; return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_to_plant"
    if load>0:return _b._to_shed(tiles,p,["DROP"]),"drop_output"
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

    # Cash conversion is first priority; final reward is terminal bank balance.
    keep_wheat=0 if liquidate else animals*3
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=keep_wheat if item=="WHEAT" else 0
        sell=max(0,qty-keep)
        if sell>0:
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    reserve=700 if lands==1 and day<=10 else 350+40*animals+(300 if day>=24 else 0)
    meta["reserve"]=reserve; spendable=max(0.0,money-reserve)

    # Preserve the full Q1 bootstrap. Expansion begins only when the first melon
    # cycle has actually generated cash, matching the strongest replay evidence.
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9)
    land_ok=False
    if lands==1:
        land_ok=10<=day<=13 and money>=6500
    elif lands==2:
        q2p=int(q2.get("productive",0) or 0)
        land_ok=10<=day<=15 and productive>=20 and q2p>=4 and money>=6500
    elif lands==3:
        q3p=int(q3.get("productive",0) or 0); q3a=int(q3.get("animals",0) or 0)
        # Q4 can still return a full melon crop through D17, then multiple wheat cycles.
        floor=9000 if day<=17 else 7500
        land_ok=12<=day<=20 and q3p>=8 and q3a>=4 and money>=floor
    expected=max(0,horizon-3)*(1000 if lands==1 else 1800 if lands==2 else 2400)
    roi=(expected-land_cost)/max(1,land_cost); meta["ranked"].append(["land",round(roi,2)])
    bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; meta["land_cost"]=land_cost
        bought_land=True; spendable-=land_cost

    # Daily Fibonacci labour. Five hands are enough for the concentrated Q1 crop;
    # after expansion, cheap labour scales to commissioning throughput.
    desired=5 if lands==1 else 8 if lands==2 else 11 if lands==3 else 12
    if day>=25:desired=min(desired,9)
    if day>=28:desired=min(desired,7)
    missing=max(0,desired-len(hands))
    if hour<=3 and day<=29 and missing>0 and len(orders)<10:
        add=min(missing,10-len(orders))
        while add>0 and _v23._hire_cost(len(hands),add)>spendable:add-=1
        if add>0:
            cost=_v23._hire_cost(len(hands),add); orders.extend([["HIRE"] for _ in range(add)])
            meta["hires"]=add; meta["hire_cost"]=cost; spendable-=cost
    next_hire=_v23._hire_cost(len(hands),1)
    meta["ranked"].append(["labour",round((horizon*140-next_hire)/max(1,next_hire),2)])

    # Feed runway before animal purchases. Market wheat is intentionally allowed:
    # a Q3 pasture tile has much higher marginal value than dedicating it to feed.
    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list):
        total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*3
    if animals and total_wheat<feed_target and day<29 and len(orders)<10:
        need=min(60,feed_target-total_wheat); affordable=max(0,int(max(0.0,spendable-250)//25))
        buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*25

    # High-density Q3 cows. Capacity is built by dedicated workers; purchases are
    # staged against actual empty pasture and never against hypothetical capacity.
    if lands>=3 and day<=21 and not bought_land and len(orders)<10:
        pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0)
        total=animals+in_shed; target=12 if day<=13 else 16
        capacity=max(0,min(pasture-total,target-total))
        cow_roi=(max(0,horizon-8)*320-400)/400.0; meta["ranked"].append(["cow",round(cow_roi,2)])
        affordable=max(0,int(max(0.0,spendable-500)//400)); buy=min(4,capacity,affordable)
        if buy>0 and cow_roi>0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    # Crop capital. Before D10 keep every coin focused on 25 Q1 melons. After the
    # first harvest, commission Q2 and Q4 with melons while a full cycle remains;
    # Q3 keeps only a small wheat strip because purchased feed is cheap vs milk ROI.
    if not liquidate and day<=27:
        need_by:Dict[str,int]={}; remaining=max(25,(len(hands)+1)*6)
        for q in range(1,lands+1):
            if remaining<=0:break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                # Reserve up to 16-18 cells for pasture, leave at most six for wheat.
                pasture_target=12 if day<=13 else 16
                idle=min(idle,max(0,min(6,int(z.get("unlocked",0) or 0)-pasture_target)))
            take=min(idle,remaining,25); remaining-=take
            crop=_v23._crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0)
            if lands==1 and day<=9 and crop=="MELON": cap=25
            elif crop=="MELON": cap=48
            else: cap=30
            need=max(0,min(cap,raw+3)-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-150)//cost)); buy=min(need,affordable)
            if buy>0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost
    return orders[:10],meta


_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None):
    return _v23.agent(observation,configuration)


def reset_state():
    return _v23.reset_state()


def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _v23.get_telemetry(clear=clear)
