"""V33.28 market-absorbing industrial allocator.

Independent V33 lineage. V33.27 proved safe four-land commissioning but also
showed that physical scale alone is not economic scale: premium gluts destroy
realized reward. This candidate sizes the Q3 cow engine to observed town milk
absorption, paces premium sales against market recovery, and plants Q1/Q2/Q4
from projected marginal demand rather than current spot price alone.

The objective is terminal bank cash. Unsold inventory has zero terminal value,
so all pacing rules collapse into liquidation from D27 onward.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial_v25 as _v25

_b = _v25._b

BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,
        "EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
SHOP_DEMAND = {
    "BAKERY": {"EGG":1,"WHEAT":1},
    "PIZZA_SHOP": {"MILK":1,"TOMATO":1,"WHEAT":1},
    "BRUNCH_SPOT": {"EGG":1,"WHEAT":1,"STRAWBERRY":1},
    "YARN_STORE": {"WOOL":2},
    "ICE_CREAM_SHOP": {"STRAWBERRY":1,"MILK":1,"WHEAT":1},
    "PET_CAFE": {"CARROT":2},
    "SMOOTHIE_SHOP": {"STRAWBERRY":1,"MILK":1},
    "FARMERS_MARKET": {"WHEAT":1,"CARROT":1,"TOMATO":1,"STRAWBERRY":1},
}
CROP_SPEC = {
    "WHEAT": (4,4,10), "CARROT": (3,3,20), "TOMATO": (4,11,50),
    "STRAWBERRY": (4,16,100),
}


def _shop_name(v: Any) -> str:
    return str(v or "").upper().replace(" ", "_").replace("-", "_")


def _daily_demand(obs: Mapping[str,Any], item: str) -> int:
    # Town center consumes one of each non-fertilizer product per day. Each shop
    # consumes every 4 turns => six/day; single-product entries are encoded 2x.
    item = item.upper(); d = 0 if item == "FERTILIZER" else 1
    town = _b._m(obs.get("town")); shops = town.get("unlocked_shops", [])
    if isinstance(shops, list):
        for raw in shops:
            d += 6 * int(SHOP_DEMAND.get(_shop_name(raw), {}).get(item, 0) or 0)
    return d


def _market_inv(obs: Mapping[str,Any], item: str) -> int:
    market = _b._m(obs.get("market")); inv = _b._m(market.get("inventory"))
    return int(inv.get(item, 10000) or 10000)


def _crop_score(crop: str, district: int, day: int, obs: Mapping[str,Any]) -> float:
    units, duration, seed = CROP_SPEC[crop]
    horizon = max(0, 30-day)
    if horizon < duration: return -1e9
    price = float(_b._prices(obs).get(crop, BASE[crop]) or BASE[crop])
    demand = _daily_demand(obs, crop)
    inv = _market_inv(obs, crop)
    # Estimate supply state when this planting first monetizes. Town absorption
    # during the growth window creates headroom; our own tile consumes some of it.
    projected = inv - demand * duration + units
    oversupply = max(0, projected - 10000)
    scarcity = max(0, 10000 - projected)
    effective = price
    if crop in {"STRAWBERRY"}:
        if demand < 7: effective *= 0.20
        if oversupply > 10: effective *= max(0.08, 1.0-oversupply/90.0)
    elif crop == "TOMATO":
        if demand < 7: effective *= 0.55
        if oversupply > 80: effective *= 0.55
    elif crop == "CARROT":
        if demand < 7 and oversupply > 80: effective *= 0.65
    elif crop == "WHEAT":
        # Wheat is the safe sink and also benefits from feed purchases removing
        # inventory from the market.
        effective *= 1.0 + min(0.35, scarcity/1200.0)
    # Q2/Q4 diversify only when a premium product has real local absorption.
    if district in {2,4} and crop in {"STRAWBERRY","TOMATO"} and demand >= 13:
        effective *= 1.10
    return (units*effective-seed)/max(1,duration)


def _crop_for(day: int, district: int, obs: Mapping[str,Any]) -> str:
    if district == 1 and day <= 1:
        return "MELON"
    if district == 3:
        return "WHEAT"
    choices = ("WHEAT","CARROT","TOMATO","STRAWBERRY")
    scored = sorted(((_crop_score(c,district,day,obs),c) for c in choices), reverse=True)
    return scored[0][1] if scored else "WHEAT"


def _cow_target(obs: Mapping[str,Any], day: int, active: int) -> int:
    # A cared cow settles around 1.5 milk/day after first yield. Size production
    # to recurring town absorption rather than a fixed herd constant.
    demand = _daily_demand(obs, "MILK")
    price = float(_b._prices(obs).get("MILK",160) or 160)
    target = max(4, min(16, (demand + 1) * 2 // 3 + 2))
    if price < 80: target = min(target, 6)
    elif price < 120: target = min(target, 9)
    if day >= 19: target = min(target, max(active, 10))
    if day >= 22: target = active
    return max(active, target)


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1; roles = ["q1"] * total
    if lands >= 2:
        for i in range(1,total): roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        crew = min(7, max(4, total//3))
        for i in range(max(1,total-crew), total): roles[i] = "livestock"
        fi = total-crew-1
        if fi >= 1: roles[fi] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved < 3:
                roles[i] = "q4"; moved += 1
    return roles


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    lands=int(stats.get("lands",0) or 0); tiles=farm.get("tiles") or []
    private=_b._m(obs.get("private")); inv=_b._inventory(private,idx)
    if role == "livestock" and lands >= 3 and day <= 28:
        q3=stats["districts"][3]; active=int(stats.get("animals",0) or 0)
        target=_cow_target(obs,day,active); cells=int(q3.get("unlocked",0) or 0)
        pasture_target=min(target,max(0,cells-5))
        r=_b._livestock_action(obs,farm,idx,p,reserved,target,pasture_target)
        if r is not None: return r
        role="feed"
    if role=="feed" and lands>=3: districts={3}
    elif role=="q4" and lands>=4: districts={4}
    elif role=="q2" and lands>=2: districts={2}
    else: districts={1}
    task=_b._best_task(tiles,p,_v25._v24._v23._tile_tasks(tiles,districts,reserved),reserved)
    if task is not None: return task
    load=_b._inv_total(inv)
    if load>=8 or (load>0 and (hour>=18 or day>=28)):
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    if day<=27 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_crop_for(day,_b._quadrant(len(tiles),g),obs)
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


def _sale_qty(obs, item: str, qty: int, day: int, shed_total: int) -> int:
    if qty <= 0: return 0
    if day >= 27: return qty
    price=float(_b._prices(obs).get(item,BASE.get(item,1)) or BASE.get(item,1))
    base=float(BASE.get(item,max(1,price)))
    demand=_daily_demand(obs,item)
    # Melon has no shop demand and holding it has almost no recovery path.
    if item=="MELON": return qty
    # Staples / fertilizer tolerate throughput; realize them quickly for capex.
    if item in {"WHEAT","CARROT","TOMATO","EGG","FERTILIZER"}:
        if item=="TOMATO" and price < 24 and day < 24 and shed_total < 75: return min(qty,max(2,demand))
        return qty
    # Premium inventory is sold into recurring demand, not dumped into a $1 glut.
    threshold=0.72*base if day<24 else 0.42*base
    if price>=threshold or shed_total>=82:
        return min(qty,max(4,demand*2 if demand else 4))
    return 0


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds"))
    inventories=private.get("inventories",[]); money=float(farm.get("money",0) or 0)
    hands=list(farm.get("hands") or []); lands=max(1,int(stats.get("lands",1) or 1))
    animals=int(stats.get("animals",0) or 0); productive=int(stats.get("productive",0) or 0)
    qs=stats["districts"]; q3=qs[3]
    orders:List[List[Any]]=[]
    meta:Dict[str,Any]={"land":0,"land_cost":0,"hires":0,"hire_cost":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate=day>=27
    shed_total=sum(max(0,int(v or 0)) for v in shed.values())
    keep_wheat=0 if liquidate else animals*4
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=keep_wheat if item=="WHEAT" else 0
        sell=_sale_qty(obs,item,max(0,qty-keep),day,shed_total)
        if sell>0:
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    reserve=750 if lands==1 and day<=10 else 550+55*animals+(350 if day>=24 else 0)
    meta["reserve"]=reserve; spendable=max(0.0,money-reserve)

    # Sequential land. Q4 requires a serviceable Q3 and enough cash to commission
    # crop capacity without starving feed/operations.
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9); land_ok=False
    if lands==1: land_ok=10<=day<=13 and money>=6500
    elif lands==2: land_ok=10<=day<=14 and productive>=22 and money>=7000
    elif lands==3:
        q3p=int(q3.get("productive",0) or 0); q3a=int(q3.get("animals",0) or 0); q3past=int(q3.get("pasture",0) or 0)
        land_ok=12<=day<=17 and q3p>=10 and q3past>=6 and q3a>=4 and money>=9000
    expected=max(0,horizon-3)*(1000 if lands==1 else 2100 if lands==2 else 2200)
    roi=(expected-land_cost)/max(1,land_cost); meta["ranked"].append(["land",round(roi,2)])
    bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost+300 and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; meta["land_cost"]=land_cost; bought_land=True; spendable-=land_cost

    target_cows=_cow_target(obs,day,animals)
    desired=5 if lands==1 else 9 if lands==2 else max(12,min(15,8+target_cows//2)) if lands==3 else max(14,min(16,9+target_cows//2))
    if day>=25: desired=min(desired,11)
    if day>=28: desired=min(desired,8)
    missing=max(0,desired-len(hands))
    if hour<=3 and day<=29 and missing>0 and len(orders)<10:
        add=min(missing,10-len(orders))
        while add>0 and _v25._v24._v23._hire_cost(len(hands),add)>spendable:add-=1
        if add>0:
            cost=_v25._v24._v23._hire_cost(len(hands),add); orders.extend([["HIRE"] for _ in range(add)])
            meta["hires"]=add; meta["hire_cost"]=cost; spendable-=cost

    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list): total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*5
    if animals and total_wheat<feed_target and day<29 and len(orders)<10:
        need=min(80,feed_target-total_wheat); wp=float(_b._prices(obs).get("WHEAT",25) or 25)
        affordable=max(0,int(max(0.0,spendable-300)//max(1,wp))); buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*wp

    if lands>=3 and day<=21 and not bought_land and len(orders)<10:
        pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0); total=animals+in_shed
        capacity=max(0,min(pasture-total,target_cows-total)); mp=float(_b._prices(obs).get("MILK",160) or 160)
        demand=_daily_demand(obs,"MILK"); cycles=max(0,(horizon-8)//2)
        # Demand-backed expected milk price. A zero-shop game should never build a
        # giant herd simply because the current spot price is still high.
        absorption=min(1.0,max(0.20,demand/max(1,target_cows*1.5)))
        cow_roi=(cycles*2*mp*absorption-400)/400.0; meta["ranked"].append(["cow",round(cow_roi,2)])
        affordable=max(0,int(max(0.0,spendable-600)//400)); buy=min(4,capacity,affordable)
        if buy>0 and cow_roi>0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    if not liquidate and day<=27:
        remaining=max(25,(len(hands)+1)*6); need_by:Dict[str,int]={}
        for q in range(1,lands+1):
            if remaining<=0:break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                idle=min(idle,max(0,min(5,int(z.get("unlocked",0) or 0)-target_cows)))
            take=min(idle,remaining,25); remaining-=take
            crop=_crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0); cap=25 if lands==1 and day<=9 and crop=="MELON" else 36
            need=max(0,min(cap,raw+3)-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-200)//cost)); buy=min(need,affordable)
            if buy>0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost
    return orders[:10],meta


# Install the new economic controller into the independent V33 execution engine.
_v25._crop_for=_crop_for
_b._crop_for=_crop_for
_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None): return _v25.agent(observation,configuration)
def reset_state(): return _v25.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear:bool=False): return _v25.get_telemetry(clear=clear)
