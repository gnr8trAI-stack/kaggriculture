"""V33.23 mechanics-correct industrial allocator.

Independent V33 lineage.  This revision corrects two mechanics errors that
capped earlier industrial candidates: farm hands are day-workers whose hire
price follows the daily Fibonacci sequence (1,1,2,3,5,...) rather than a flat
$500, and land costs are $1k/$2k/$4k.  It therefore treats labour as cheap
throughput capacity, buys Q2 from starting capital, compounds the first melon
cycle into Q3/Q4, and explicitly commissions Q3 livestock/feed and Q4 crops.
V19.2 remains benchmark-only.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set
from agents import v33_industrial as _b

GAME_DAYS = 30


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    # Melon has the strongest base-price return per occupied tile if it can
    # still reach its day-10 max yield.  Use wheat only when that horizon closes.
    return "MELON" if day <= 17 else "WHEAT"


def _age(tile: Mapping[str, Any], day: int) -> int:
    try:
        p = tile.get("planted_day", day)
        return max(0, day - int(day if p is None else p))
    except Exception:
        return 0


def _tile_tasks(tiles: Any, districts: Set[int], reserved: Set[_b.Position]):
    tasks = []
    if not isinstance(tiles, list) or not tiles:
        return tasks
    day = int(getattr(_b, "_CURRENT_DAY", 0) or 0)
    max_yield_day = {"WHEAT":4, "CARROT":3, "MELON":10}
    n = len(tiles)
    for y,row in enumerate(tiles):
        if not isinstance(row,list):
            continue
        for x,tile in enumerate(row):
            p=(x,y)
            if _b._quadrant(n,p) not in districts or p in reserved:
                continue
            kind=_b._kind(tile)
            if kind=="WEED":
                tasks.append((3,p,["DIG"],"dig")); continue
            if kind!="PLANT" or not isinstance(tile,Mapping):
                continue
            crop=str(tile.get("crop","")).upper()
            watered=bool(tile.get("watered_today",tile.get("watered",False)))
            danger=int(tile.get("consecutive_unwatered",0) or 0)>=1
            yld=int(tile.get("yield_units",tile.get("yield",0)) or 0)
            # One-time crops are held until max-yield day unless liquidation is
            # close. Ongoing crops are harvested whenever scheduled output exists.
            if yld>0 and (crop not in max_yield_day or day>=27 or _age(tile,day)>=max_yield_day[crop]):
                tasks.append((0,p,["HARVEST"],"harvest_crop"))
            elif not watered and danger and day<29:
                tasks.append((0,p,["WATER"],"water_urgent"))
            elif not watered and day<28:
                tasks.append((1,p,["WATER"],"water"))
    return tasks


def _roles(lands: int, hand_count: int) -> List[str]:
    total=hand_count+1
    roles=["q1"]*total
    if lands>=2:
        for i in range(1,total):
            roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        # Dedicated livestock/feed division while preserving both crop engines.
        crew=min(4,max(2,total//4))
        for i in range(max(1,total-crew),total):
            roles[i]="livestock"
        fi=total-crew-1
        if fi>=1:
            roles[fi]="feed"
    if lands>=4:
        moved=0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<3:
                roles[i]="q4"; moved+=1
    return roles


_base_unit_action=_b._unit_action


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    day=int(obs.get("day",0) or 0)
    hour=int(obs.get("hour",0) or 0)
    lands=int(stats.get("lands",0) or 0)
    private=_b._m(obs.get("private"))
    inv=_b._inventory(private,idx)
    tiles=farm.get("tiles") or []

    if role=="livestock" and lands>=3 and day<=28:
        q3=stats["districts"][3]
        active=int(stats.get("animals",0) or 0)
        target=10 if day<=14 else 16 if day<=21 else max(12,active)
        q3_cells=int(q3.get("unlocked",0) or 0)
        pasture_target=min(target,max(0,q3_cells-6))
        r=_b._livestock_action(obs,farm,idx,p,reserved,target,pasture_target)
        if r is not None:
            return r
        role="feed"

    if role=="feed" and lands>=3:
        districts={3}
    elif role=="q4" and lands>=4:
        districts={4}
    elif role=="q2" and lands>=2:
        districts={2}
    else:
        districts={1}

    task=_b._best_task(tiles,p,_tile_tasks(tiles,districts,reserved),reserved)
    if task is not None:
        return task

    load=_b._inv_total(inv)
    # Convert carried output to shed early enough for terminal market sales.
    if load>=8 or (load>0 and (hour>=18 or day>=28)):
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"

    # Never start a crop so late in the day that it cannot be watered before the
    # end-of-day refresh; never start long-payback production after D27.
    if day<=27 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_crop_for(day,_b._quadrant(len(tiles),g),obs)
            if seed_budget.get(crop,0)<=0:
                continue
            rr=_b._route(tiles,p,g)
            if rr is not None:
                choices.append((rr[0],g[1],g[0],g,crop,rr[1]))
        if choices:
            choices.sort(); dist,_,_,target,crop,first=choices[0]
            reserved.add(target)
            if dist==0:
                seed_budget[crop]-=1
                return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_to_plant"

    if load>0:
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    return ["PASS"],"idle"


def _fib(n:int)->int:
    # n is 1-based hire number within the day.
    a,b=1,1
    if n<=2:return 1
    for _ in range(3,n+1):
        a,b=b,a+b
    return b


def _hire_cost(existing:int,add:int)->int:
    return sum(_fib(existing+i+1) for i in range(add))


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    horizon=max(0,GAME_DAYS-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds"))
    inventories=private.get("inventories",[])
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    lands=max(1,int(stats.get("lands",1) or 1)); animals=int(stats.get("animals",0) or 0)
    productive=int(stats.get("productive",0) or 0); qs=stats["districts"]
    q1,q2,q3,q4=(qs[i] for i in (1,2,3,4))
    orders:List[List[Any]]=[]
    meta:Dict[str,Any]={"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[],"hire_cost":0}
    liquidate=day>=27

    # Final score is bank cash. Sell continuously, with only a small feed runway
    # held before liquidation. This also avoids shed-capacity loss.
    keep_wheat=0 if liquidate else animals*3
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0)
        keep=keep_wheat if item=="WHEAT" else 0
        sell=max(0,qty-keep)
        if sell>0:
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    # Shared operating runway. Labour is costed with the actual daily Fibonacci
    # schedule, not the old flat-$500 assumption.
    reserve=250+35*animals+(250 if day>=24 else 0)
    meta["reserve"]=reserve
    spendable=max(0.0,money-reserve)

    # Industrial land ladder. Q2 is funded from starting capital. Q3/Q4 are paid
    # from realized crop cash and only while enough horizon remains to commission.
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9)
    land_ok=False
    if lands==1:
        land_ok=day<=3 and money>=1700
    elif lands==2:
        land_ok=8<=day<=16 and productive>=18 and money>=6000
    elif lands==3:
        q3_prod=int(q3.get("productive",0) or 0); q3_anim=int(q3.get("animals",0) or 0)
        land_ok=10<=day<=17 and q3_prod>=6 and q3_anim>=2 and money>=8500
    expected=(max(0,horizon-3)*(900 if lands==1 else 1500 if lands==2 else 2200))
    roi=(expected-land_cost)/max(1,land_cost)
    meta["ranked"].append(["land",round(roi,2)])
    bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; bought_land=True; spendable-=land_cost

    # Cheap day-workers are the throughput engine. Hire aggressively near dawn;
    # the exact Fibonacci bill is reserved before seed/cow purchases.
    desired=7 if lands==1 else 9 if lands==2 else 11 if lands==3 else 12
    if day>=25: desired=min(desired,9)
    if day>=28: desired=min(desired,7)
    missing=max(0,desired-len(hands))
    if hour<=3 and day<=29 and missing>0 and len(orders)<10:
        add=min(missing,10-len(orders))
        # Preserve reserve but exploit the very low first hires of every day.
        while add>0 and _hire_cost(len(hands),add)>spendable:
            add-=1
        if add>0:
            cost=_hire_cost(len(hands),add)
            orders.extend([["HIRE"] for _ in range(add)])
            meta["hires"]=add; meta["hire_cost"]=cost; spendable-=cost
    meta["ranked"].append(["labour",round((horizon*140-max(1,_hire_cost(len(hands),1)))/max(1,_hire_cost(len(hands),1)),2)])

    # Feed solvency before biological capex. Include carried wheat.
    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list):
        total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*4
    if animals and total_wheat<feed_target and day<28 and len(orders)<10:
        need=min(50,feed_target-total_wheat)
        # README base buy price is dynamic; reserve $25/unit conservatively.
        affordable=max(0,int(max(0.0,spendable-200)//25))
        buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*25

    # Q3 herd: pasture first, cows second. Cows are bought in batches only against
    # serviceable built capacity and with enough horizon for milk payback.
    if lands>=3 and day<=21 and not bought_land and len(orders)<10:
        pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0)
        total=animals+in_shed; target=10 if day<=14 else 16
        capacity=max(0,min(pasture-total,target-total))
        cow_roi=(max(0,horizon-8)*320-400)/400.0
        meta["ranked"].append(["cow",round(cow_roi,2)])
        affordable=max(0,int(max(0.0,spendable-500)//400))
        buy=min(4,capacity,affordable)
        if buy>0 and cow_roi>0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    # Seed only currently serviceable surface. The first cycle deliberately caps
    # melon exposure so Q2+labour remain solvent; after realized harvest cash,
    # commission Q1/Q2/Q4 and a Q3 wheat/feed strip aggressively.
    if not liquidate and day<=27:
        service_cap=max(20,(len(hands)+1)*6)
        need_by:Dict[str,int]={}; remaining=service_cap
        for q in range(1,lands+1):
            if remaining<=0:break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                pasture_target=10 if day<=14 else 16
                idle=min(idle,max(0,int(z.get("unlocked",0) or 0)-6-pasture_target))
            take=min(idle,remaining,24); remaining-=take
            crop=_crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0)
            # Bootstrap at most 20 melons; after D8, fill serviceable surface.
            cap=20 if crop=="MELON" and day<=7 else 42 if crop=="MELON" else 28
            need=max(0,min(cap,raw+3)-have)
            cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-150)//cost))
            buy=min(need,affordable)
            if buy>0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost

    return orders[:10],meta


_b._CURRENT_DAY=0
_base_agent=_b.agent
_b._crop_for=_crop_for
_b._tile_tasks=_tile_tasks
_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None):
    obs=_b._obs(observation); _b._CURRENT_DAY=int(obs.get("day",0) or 0)
    return _base_agent(observation,configuration)


def reset_state():
    _b._CURRENT_DAY=0
    return _b.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear:bool=False):
    return _b.get_telemetry(clear=clear)
