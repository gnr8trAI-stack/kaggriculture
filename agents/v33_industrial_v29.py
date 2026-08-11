"""V33.29 mixed-livestock industrial allocator.

V33.28 proved the four-district physical architecture (4 land, ~76 productive,
zero invalids) but monetized only ~64K median because Q3 was constrained to an
8-cow milk monoculture.  This candidate keeps the independent V33 executor and
four-district crop engine, but turns Q3 into a demand-aware mixed animal plant:
cows, geese and sheep compete for structure/capital against live recurring town
absorption and product-specific glut curves.  Bought wheat is an operating input;
Q1/Q2/Q4 remain crop districts.  Terminal reward is bank cash, so D27+ liquidates.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set, Tuple
from agents import v33_industrial_v28 as _v28

_b = _v28._b
_v25 = _v28._v25

ANIMAL = {
    "COW": {"cost":400,"structure":"PASTURE","product":"MILK","first":8,"interval":2},
    "SHEEP": {"cost":500,"structure":"PASTURE","product":"WOOL","first":6,"interval":3},
    "GOOSE": {"cost":300,"structure":"COOP","product":"EGG","first":4,"interval":1},
}
BASE = dict(_v28.BASE)


def _active_animals(tiles):
    out=[]
    for y,row in enumerate(tiles or []):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            if isinstance(t,Mapping) and str(t.get("animal","")).upper() in ANIMAL:
                out.append(((x,y),t))
    return out


def _structures(tiles, kind):
    out=[]
    for y,row in enumerate(tiles or []):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            if isinstance(t,Mapping) and str(t.get("kind","")).upper()==kind:
                out.append(((x,y),t))
    return out


def _mix_target(obs: Mapping[str,Any], day:int, active:Mapping[str,int]) -> Dict[str,int]:
    """Size each product line to recurring absorption, with a profitable base mix."""
    horizon=max(0,30-day)
    if horizon < 6:
        return {k:int(active.get(k,0)) for k in ANIMAL}
    dm={"COW":_v28._daily_demand(obs,"MILK"),"GOOSE":_v28._daily_demand(obs,"EGG"),"SHEEP":_v28._daily_demand(obs,"WOOL")}
    # Approx cared output/day after startup: cow 1.5, goose 2, sheep 1.33.
    rates={"COW":1.5,"GOOSE":2.0,"SHEEP":1.33}
    caps={"COW":10,"GOOSE":7,"SHEEP":7}
    base={"COW":5,"GOOSE":3,"SHEEP":1}
    target={}
    for a in ANIMAL:
        demand_cap=int(dm[a]/rates[a])+2
        target[a]=max(base[a],min(caps[a],demand_cap))
    # Wool is quadratically fragile without a yarn store; one sheep still earns
    # fertilizer and a small amount of high-price wool, but never build a flock.
    if dm["SHEEP"] <= 1: target["SHEEP"]=1
    # Milk also has a steep linear glut; zero-shop games cap the dairy line.
    if dm["COW"] <= 1: target["COW"]=5
    # Egg glut is logarithmically mild, so geese are the safe secondary engine.
    if dm["GOOSE"] <= 1: target["GOOSE"]=4
    # Q3 has 25 cells including shed corner; reserve two maneuver/feed cells.
    total=sum(target.values())
    if total>22:
        # Trim lowest recurring-demand lines first.
        order=sorted(ANIMAL,key=lambda a:(dm[a]/rates[a],{"SHEEP":0,"COW":1,"GOOSE":2}[a]))
        while sum(target.values())>22:
            changed=False
            for a in order:
                if target[a]>base[a]: target[a]-=1; changed=True; break
            if not changed: break
    if day>=21:
        for a in target: target[a]=max(int(active.get(a,0)),min(target[a],int(active.get(a,0))+1))
    return target


def _roles(lands:int, hand_count:int)->List[str]:
    total=hand_count+1; roles=["q1"]*total
    if lands>=2:
        for i in range(1,total): roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        # Keep eight animal operators at 14 hands; remaining crew maintains Q1/Q2.
        crew=min(8,max(5,total//2))
        for i in range(max(1,total-crew),total): roles[i]="livestock"
    if lands>=4:
        moved=0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<3: roles[i]="q4"; moved+=1
    return roles


def _animal_action(obs,farm,idx,p,reserved,target):
    tiles=farm.get("tiles") or []; private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); inv=_b._inventory(private,idx)
    active=_active_animals(tiles)
    q3_active=[(pp,t) for pp,t in active if _b._quadrant(len(tiles),pp)==3]
    counts={a:sum(1 for _,t in q3_active if str(t.get("animal","")).upper()==a) for a in ANIMAL}

    # Feed survival first.
    if int(inv.get("WHEAT",0) or 0)>0:
        goals=[pp for pp,t in q3_active if not bool(t.get("fed_today",False)) and pp not in reserved]
        r=_b._nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[1]); return (["FEED"] if r[0]==0 else [r[2]]),"feed"

    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in set(ANIMAL)|{"WHEAT"})
    if output>0: return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"

    unfed=[pp for pp,t in q3_active if not bool(t.get("fed_today",False)) and pp not in reserved]
    if unfed and int(shed.get("WHEAT",0) or 0)>0:
        return _b._to_shed(tiles,p,["PICKUP","WHEAT",min(10,int(shed.get("WHEAT",0) or 0))]),"pickup_feed"

    # Harvest, care and fertilizer all have positive cash value; care precedes
    # fertilizer because it increases future animal yield.
    for pred,act,label in (
        (lambda t:int(t.get("yield_units",0) or 0)>0,["HARVEST"],"harvest_livestock"),
        (lambda t:not bool(t.get("cared_today",False)),["CARE"],"care"),
        (lambda t:bool(t.get("fertilizer_available",False)),["COLLECT_FERTILIZER"],"fertilizer"),
    ):
        goals=[pp for pp,t in q3_active if pred(t) and pp not in reserved]
        r=_b._nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[1]); return (act if r[0]==0 else [r[2]]),label

    # Place purchased animals into matching empty structures.
    for a in ("COW","GOOSE","SHEEP"):
        kind=ANIMAL[a]["structure"]
        empty=[pp for pp,t in _structures(tiles,kind) if _b._quadrant(len(tiles),pp)==3 and not t.get("animal") and pp not in reserved]
        if int(inv.get(a,0) or 0)>0 and empty:
            r=_b._nearest(tiles,p,empty)
            if r is not None:
                reserved.add(r[1]); return (["PLACE",a] if r[0]==0 else [r[2]]),"place_"+a.lower()
        if int(shed.get(a,0) or 0)>0 and empty:
            return _b._to_shed(tiles,p,["PICKUP",a,1]),"pickup_"+a.lower()

    # Commission structures only against explicit target gaps.
    pasture_need=max(0,target["COW"]+target["SHEEP"]-sum(1 for pp,t in _structures(tiles,"PASTURE") if _b._quadrant(len(tiles),pp)==3))
    coop_need=max(0,target["GOOSE"]-sum(1 for pp,t in _structures(tiles,"COOP") if _b._quadrant(len(tiles),pp)==3))
    if pasture_need or coop_need:
        goals=_b._empty_targets(tiles,{3},reserved)
        r=_b._nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[1]); op="BUILD_COOP" if coop_need>0 else "BUILD_PASTURE"
            return ([op] if r[0]==0 else [r[2]]),"build_structure"
    return None


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); lands=int(stats.get("lands",0) or 0); tiles=farm.get("tiles") or []
    private=_b._m(obs.get("private")); inv=_b._inventory(private,idx)
    if role=="livestock" and lands>=3 and day<=29:
        ac={a:0 for a in ANIMAL}
        for pp,t in _active_animals(tiles):
            if _b._quadrant(len(tiles),pp)==3: ac[str(t.get("animal","")).upper()]+=1
        target=_mix_target(obs,day,ac)
        r=_animal_action(obs,farm,idx,p,reserved,target)
        if r is not None:return r
    if role=="q4" and lands>=4: districts={4}
    elif role=="q2" and lands>=2: districts={2}
    else: districts={1}
    task=_b._best_task(tiles,p,_v25._v24._v23._tile_tasks(tiles,districts,reserved),reserved)
    if task is not None:return task
    load=_b._inv_total(inv)
    if load>=8 or (load>0 and (hour>=18 or day>=28)): return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    if day<=27 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_v28._crop_for(day,_b._quadrant(len(tiles),g),obs)
            if seed_budget.get(crop,0)<=0:continue
            rr=_b._route(tiles,p,g)
            if rr is not None:choices.append((rr[0],g[1],g[0],g,crop,rr[1]))
        if choices:
            choices.sort(); dist,_,_,target,crop,first=choices[0]; reserved.add(target)
            if dist==0:seed_budget[crop]-=1;return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_to_plant"
    if load>0:return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    return ["PASS"],"idle"


def _sale_qty(obs,item,qty,day,shed_total):
    if qty<=0:return 0
    if day>=27:return qty
    if item=="WOOL":
        demand=_v28._daily_demand(obs,"WOOL"); price=float(_b._prices(obs).get("WOOL",200) or 200)
        if demand<=1 and price<120:return min(qty,2)
        return min(qty,max(3,demand*2))
    if item=="MILK":
        demand=_v28._daily_demand(obs,"MILK"); price=float(_b._prices(obs).get("MILK",160) or 160)
        if price<70 and day<24:return min(qty,max(2,demand))
        return min(qty,max(4,demand*2))
    return _v28._sale_qty(obs,item,qty,day,shed_total)


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds")); inventories=private.get("inventories",[])
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or []); lands=max(1,int(stats.get("lands",1) or 1)); productive=int(stats.get("productive",0) or 0)
    qs=stats["districts"]; q3=qs[3]; orders=[]; meta={"land":0,"land_cost":0,"hires":0,"hire_cost":0,"cows":0,"animals_bought":{},"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate=day>=27; active_list=[(pp,t) for pp,t in _active_animals(farm.get("tiles") or []) if _b._quadrant(len(farm.get("tiles") or []),pp)==3]
    ac={a:sum(1 for _,t in active_list if str(t.get("animal","")).upper()==a) for a in ANIMAL}; animals=sum(ac.values())
    target=_mix_target(obs,day,ac)

    shed_total=sum(max(0,int(v or 0)) for v in shed.values()); keep_wheat=0 if liquidate else animals*5
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=keep_wheat if item=="WHEAT" else 0; sell=_sale_qty(obs,item,max(0,qty-keep),day,shed_total)
        if sell>0:
            orders.append(["SELL",item,sell]);meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta

    reserve=700 if lands==1 and day<=10 else 650+45*animals+(350 if day>=24 else 0);meta["reserve"]=reserve;spendable=max(0.0,money-reserve)
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9);land_ok=False
    if lands==1:land_ok=10<=day<=13 and money>=6500
    elif lands==2:land_ok=10<=day<=14 and productive>=22 and money>=7000
    elif lands==3:
        q3struct=int(q3.get("pasture",0) or 0)+sum(1 for pp,t in _structures(farm.get("tiles") or [],"COOP") if _b._quadrant(len(farm.get("tiles") or []),pp)==3)
        land_ok=12<=day<=18 and q3struct>=8 and animals>=4 and money>=9000
    expected=max(0,horizon-3)*(1000 if lands==1 else 2100 if lands==2 else 2400);roi=(expected-land_cost)/max(1,land_cost);meta["ranked"].append(["land",round(roi,2)]);bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost+300 and len(orders)<10:
        orders.append(["BUY_LAND"]);meta["land"]=1;meta["land_cost"]=land_cost;bought_land=True;spendable-=land_cost

    desired=5 if lands==1 else 9 if lands==2 else 14
    if lands>=4:desired=14
    if day>=25:desired=min(desired,11)
    if day>=28:desired=min(desired,8)
    missing=max(0,desired-len(hands))
    if hour<=3 and day<=29 and missing>0 and len(orders)<10:
        add=min(missing,10-len(orders))
        while add>0 and _v25._v24._v23._hire_cost(len(hands),add)>spendable:add-=1
        if add>0:
            cost=_v25._v24._v23._hire_cost(len(hands),add);orders.extend([["HIRE"] for _ in range(add)]);meta["hires"]=add;meta["hire_cost"]=cost;spendable-=cost

    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list):total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*6
    if animals and total_wheat<feed_target and day<29 and len(orders)<10:
        need=min(100,feed_target-total_wheat);wp=float(_b._prices(obs).get("WHEAT",25) or 25);aff=max(0,int(max(0.0,spendable-300)//max(1,wp)));buy=min(need,aff)
        if buy>0:orders.append(["BUY_PRODUCT","WHEAT",buy]);meta["feed"]=buy;spendable-=buy*wp

    # Buy against real commissioned structures, prioritizing best live marginal ROI.
    if lands>=3 and day<=21 and not bought_land and len(orders)<10:
        in_shed={a:int(shed.get(a,0) or 0) for a in ANIMAL}; candidates=[]
        prices=_b._prices(obs)
        for a,spec in ANIMAL.items():
            total=ac[a]+in_shed[a]; gap=max(0,target[a]-total)
            kind=spec["structure"]
            empty=sum(1 for pp,t in _structures(farm.get("tiles") or [],kind) if _b._quadrant(len(farm.get("tiles") or []),pp)==3 and not t.get("animal"))
            cap=min(gap,empty)
            if cap<=0:continue
            cycles=max(0,(horizon-spec["first"])//max(1,spec["interval"])); product=spec["product"]; p=float(prices.get(product,BASE[product]) or BASE[product]); demand=_v28._daily_demand(obs,product)
            # First cared yield tends to hit max-held; subsequent yields get care bonuses.
            units=max(0,6 if cycles>0 else 0)+max(0,cycles-1)*(2 if a=="GOOSE" else 3 if a=="COW" else 4)
            absorption=min(1.0,max(0.30,demand/max(1,(target[a]*({"COW":1.5,"GOOSE":2.0,"SHEEP":1.33}[a])))))
            fert_days=max(0,horizon-1);value=units*p*absorption+fert_days*55-spec["cost"]-fert_days*25;roi=value/max(1,spec["cost"])
            candidates.append((roi,a,cap))
        candidates.sort(reverse=True)
        for roi,a,cap in candidates:
            if len(orders)>=10 or spendable<ANIMAL[a]["cost"]+500:break
            buy=min(3,cap,int(max(0,spendable-500)//ANIMAL[a]["cost"]))
            if buy>0 and roi>0:
                orders.append(["BUY_ANIMAL",a,buy]);meta["animals_bought"][a]=buy;spendable-=buy*ANIMAL[a]["cost"]

    if not liquidate and day<=27:
        remaining=max(25,(len(hands)+1)*6);need_by={}
        for q in (1,2,4):
            if q>lands or remaining<=0:continue
            z=qs[q];idle=int(z.get("idle",0) or 0);take=min(idle,remaining,25);remaining-=take;crop=_v28._crop_for(day,q,obs);need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0);cap=25 if lands==1 and day<=9 and crop=="MELON" else 40;need=max(0,min(cap,raw+4)-have);cost=_b.SEED_COST[crop];aff=max(0,int(max(0.0,spendable-200)//cost));buy=min(need,aff)
            if buy>0:orders.append(["BUY_SEED",crop,buy]);meta["seeds"][crop]=buy;spendable-=buy*cost
    return orders[:10],meta


_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator

def agent(observation:Any,configuration:Any=None):return _v28.agent(observation,configuration)
def reset_state():return _v28.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _v28.get_telemetry(clear=clear)
