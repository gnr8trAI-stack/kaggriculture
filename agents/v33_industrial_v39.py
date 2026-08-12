"""V33.39 market-slot-arbitrated industrial compounding.

Independent V33 architecture on the strongest clean V33.25 economic controller,
not on V19/V32.  This revision fixes an allocator-level throughput bottleneck:
SELL orders and dawn HIRE orders could consume all ten market slots before Q3
animal/feed capex or Q4 land could execute.  V33.39 explicitly arbitrates scarce
market-order slots across realized sales, operating feed, labour, livestock,
land and crop capital, while preserving a cash reserve.  It also adds a strict
terminal realization mode because Kaggriculture scores terminal bank cash only.

District plan:
  Q1 demand-aware crop cash engine.
  Q2 second crop engine.
  Q3 16-pasture mixed livestock factory (10 cows / 6 sheep) with bought wheat.
  Q4 crop district only when realized Q3 commissioning and remaining-horizon ROI
     support the $4k land purchase.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set, Tuple
from agents import v33_industrial_v25 as _p

_b = _p._b

COW_TARGET = 10
SHEEP_TARGET = 6
PASTURE_TARGET = 16
ANIMAL_COST = {"COW": 400, "SHEEP": 500}


def _animal_record(tile: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = tile.get("animal")
    if isinstance(raw, Mapping):
        merged = dict(tile); merged.update(raw); return merged
    return tile


def _animal_type(tile: Mapping[str, Any]) -> str:
    raw = tile.get("animal")
    if isinstance(raw, Mapping):
        for k in ("type", "kind", "name", "animal_type", "species"):
            v = raw.get(k)
            if v: return str(v).upper()
    elif raw:
        return str(raw).upper()
    for k in ("animal_type", "species"):
        v = tile.get(k)
        if v: return str(v).upper()
    return ""


def _animal_counts(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0}
    for row in farm.get("tiles") or []:
        if not isinstance(row, list): continue
        for tile in row:
            if not isinstance(tile, Mapping): continue
            a = _animal_type(tile)
            if a in counts: counts[a] += 1
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    for a in counts: counts[a] += int(shed.get(a, 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        for inv in invs:
            m = _b._m(inv)
            for a in counts: counts[a] += int(m.get(a, 0) or 0)
    return counts


def _q3_pastures(tiles):
    out=[]; n=len(tiles) if isinstance(tiles,list) else 0; h=n//2
    for y,row in enumerate(tiles if isinstance(tiles,list) else []):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            if x < h and y >= h and isinstance(t,Mapping) and str(t.get("kind","")).upper()=="PASTURE":
                out.append(((x,y),t))
    return out


def _nearest(tiles,p,goals):
    best=None
    for g in goals:
        rr=_b._route(tiles,p,g)
        if rr is None: continue
        cand=(rr[0],g[1],g[0],g)
        if best is None or cand < best: best=cand
    return None if best is None else best[3]


def _go(tiles,p,g,action):
    if p==g: return action
    rr=_b._route(tiles,p,g)
    return [rr[1]] if rr is not None else ["PASS"]


def _roles(lands:int, hand_count:int)->List[str]:
    total=hand_count+1
    roles=["q1"]*total
    if lands>=2:
        for i in range(1,total): roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        crew=min(6,max(4,total//3))
        for i in range(max(1,total-crew),total): roles[i]="livestock"
        fi=total-crew-1
        if fi>=1: roles[fi]="feed"
    if lands>=4:
        moved=0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<3:
                roles[i]="q4"; moved+=1
    return roles


def _livestock_action(obs,farm,idx,p,stats,reserved):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    tiles=farm.get("tiles") or []; private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); inv=_b._inventory(private,idx)
    q3=_q3_pastures(tiles); active=[]; empty=[]
    for g,t in q3:
        a=_animal_type(t)
        if a in {"COW","SHEEP"}: active.append((g,t,_animal_record(t)))
        elif not t.get("animal"): empty.append(g)

    # On the final two days cash conversion outranks all optional service.
    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","COW","SHEEP"})
    if day>=28 and output>0:
        return _b._to_shed(tiles,p,["DROP"]),"terminal_drop_livestock"

    # Place purchased animals immediately so biological payback clock starts.
    for a in ("COW","SHEEP"):
        if int(inv.get(a,0) or 0)>0 and empty:
            g=_nearest(tiles,p,[x for x in empty if x not in reserved])
            if g is not None: reserved.add(g); return _go(tiles,p,g,["PLACE",a]),"place_"+a.lower()

    # Survival first: feed every active animal daily.
    if int(inv.get("WHEAT",0) or 0)>0:
        g=_nearest(tiles,p,[g for g,t,a in active if not bool(a.get("fed_today",a.get("fed",False))) and g not in reserved])
        if g is not None: reserved.add(g); return _go(tiles,p,g,["FEED"]),"feed"
    unfed=[g for g,t,a in active if not bool(a.get("fed_today",a.get("fed",False))) and g not in reserved]
    if unfed and int(shed.get("WHEAT",0) or 0)>0:
        return _b._to_shed(tiles,p,["PICKUP","WHEAT",min(12,int(shed.get("WHEAT",0) or 0))]),"pickup_feed"

    # Harvest monetizable output before care/fertilizer.  Fertilizer is then
    # collected every day; it is either sold or can be used by future revisions.
    g=_nearest(tiles,p,[g for g,t,a in active if int(a.get("yield_units",a.get("yield",0)) or 0)>0 and g not in reserved])
    if g is not None: reserved.add(g); return _go(tiles,p,g,["HARVEST"]),"harvest_livestock"
    g=_nearest(tiles,p,[g for g,t,a in active if bool(a.get("fertilizer_available",False)) and g not in reserved])
    if g is not None: reserved.add(g); return _go(tiles,p,g,["COLLECT_FERTILIZER"]),"collect_fertilizer"
    if day<=27:
        g=_nearest(tiles,p,[g for g,t,a in active if not bool(a.get("cared_today",a.get("cared",False))) and g not in reserved])
        if g is not None: reserved.add(g); return _go(tiles,p,g,["CARE"]),"care"

    if output>=4 or (output>0 and hour>=16):
        return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"

    counts=_animal_counts(obs,farm)
    for a,target in (("COW",COW_TARGET),("SHEEP",SHEEP_TARGET)):
        if counts[a] < target and int(shed.get(a,0) or 0)>0 and empty:
            return _b._to_shed(tiles,p,["PICKUP",a,1]),"pickup_"+a.lower()

    if day<=17 and len(q3)<PASTURE_TARGET:
        g=_nearest(tiles,p,[x for x in _b._empty_targets(tiles,{3},reserved)])
        if g is not None: reserved.add(g); return _go(tiles,p,g,["BUILD_PASTURE"]),"build_pasture"

    if output>0: return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"
    return None


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); lands=int(stats.get("lands",0) or 0)
    tiles=farm.get("tiles") or []; private=_b._m(obs.get("private")); inv=_b._inventory(private,idx)
    load=_b._inv_total(inv)

    # Terminal cash realization: carried harvest is worthless until it reaches
    # the shed and is sold.  From D28 onward, unload before taking new field work.
    if day>=28 and load>0:
        return _b._to_shed(tiles,p,["DROP"]),"terminal_drop"

    if role=="livestock" and lands>=3:
        r=_livestock_action(obs,farm,idx,p,stats,reserved)
        if r is not None: return r
        role="feed"

    if role=="feed" and lands>=3: districts={3}
    elif role=="q4" and lands>=4: districts={4}
    elif role=="q2" and lands>=2: districts={2}
    else: districts={1}

    task=_b._best_task(tiles,p,_p._v24._v23._tile_tasks(tiles,districts,reserved),reserved)
    if task is not None: return task

    load=_b._inv_total(inv)
    if load>=8 or (load>0 and (hour>=17 or day>=28)):
        return _b._to_shed(tiles,p,["DROP"]),"drop_output"

    if day<=26 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_p._crop_for(day,_b._quadrant(len(tiles),g),obs)
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


def _hire_cost(existing:int,add:int)->int:
    return _p._v24._v23._hire_cost(existing,add)


def _sale_orders(obs, shed, animals:int, liquidate:bool, max_slots:int):
    prices=_b._prices(obs); candidates=[]
    keep_wheat=0 if liquidate else animals*3
    for item in _b.SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=keep_wheat if item=="WHEAT" else 0
        sell=max(0,qty-keep)
        if sell<=0: continue
        p=float(prices.get(item,_b.VALUE.get(item,1)) or _b.VALUE.get(item,1))
        candidates.append((sell*p,p,sell,item))
    candidates.sort(reverse=True)
    return [["SELL",item,qty] for _,_,qty,item in candidates[:max_slots]]


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); horizon=max(0,30-day)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); seeds=_b._m(private.get("seeds")); invs=private.get("inventories",[])
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or []); lands=max(1,int(stats.get("lands",1) or 1))
    animals=int(stats.get("animals",0) or 0); productive=int(stats.get("productive",0) or 0); qs=stats["districts"]; q1,q2,q3,q4=(qs[i] for i in (1,2,3,4))
    counts=_animal_counts(obs,farm); prices=_b._prices(obs)
    liquidate=day>=27
    meta:Dict[str,Any]={"land":0,"land_cost":0,"hires":0,"hire_cost":0,"cows":0,"sheep":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[],"cow_total":counts["COW"],"sheep_total":counts["SHEEP"]}

    # Reserve market slots for operations.  Previous revisions could fill all ten
    # slots with SELL/HIRE orders and starve the herd/land allocator indefinitely.
    sale_slots=10 if liquidate else (3 if hour<=3 else 5)
    orders=_sale_orders(obs,shed,animals,liquidate,sale_slots)
    meta["sell_qty"]=sum(int(o[2]) for o in orders)
    if liquidate:
        return orders[:10],meta

    # Estimate proceeds from queued sales conservatively so realized inventory can
    # finance same-turn industrial capex while preserving a true operating reserve.
    sale_cash=0.0
    for o in orders:
        sale_cash += int(o[2])*float(prices.get(o[1],_b.VALUE.get(o[1],1)) or _b.VALUE.get(o[1],1))
    reserve=650+animals*90
    if day>=23: reserve+=500
    meta["reserve"]=reserve
    spendable=max(0.0,money+0.80*sale_cash-reserve)

    # Land ladder: Q4 is explicitly available when Q3 is actually commissioned,
    # not merely owned.  Generic q3 animal count is authoritative for the gate.
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9); land_ok=False
    if lands==1:
        land_ok=10<=day<=13 and money+0.8*sale_cash>=6500
    elif lands==2:
        land_ok=10<=day<=14 and productive>=22 and money+0.8*sale_cash>=7000
    elif lands==3:
        q3a=int(q3.get("animals",0) or 0); q3p=int(q3.get("pasture",0) or 0); q3prod=int(q3.get("productive",0) or 0)
        projected=max(0,horizon-3)*2300-land_cost
        land_ok=day<=17 and horizon>=12 and q3a>=6 and q3p>=10 and q3prod>=12 and productive>=48 and money+0.8*sale_cash>=9000 and projected>=6000
    expected=max(0,horizon-3)*(1000 if lands==1 else 2100 if lands==2 else 3000)
    roi=(expected-land_cost)/max(1,land_cost); meta["ranked"].append(["land",round(roi,2)])
    bought_land=False
    if lands<4 and land_ok and roi>0 and spendable>=land_cost and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; meta["land_cost"]=land_cost; spendable-=land_cost; bought_land=True

    # Labour: use the true daily Fibonacci curve and reserve order slots for feed
    # and animals.  14 hands costs only $986/day and is enough to commission Q3/Q4.
    desired=5 if lands==1 else 9 if lands==2 else 14
    if lands>=4: desired=14
    if day>=27: desired=12
    missing=max(0,desired-len(hands))
    if hour<=3 and missing>0 and len(orders)<8:
        # Leave two market slots for feed / animal or seed capex.
        add=min(missing,8-len(orders))
        while add>0 and _hire_cost(len(hands),add)>spendable: add-=1
        if add>0:
            cost=_hire_cost(len(hands),add); orders.extend([["HIRE"] for _ in range(add)]); meta["hires"]=add; meta["hire_cost"]=cost; spendable-=cost

    # Existing herd survival comes before new biological capex.
    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(invs,list): total_wheat+=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in invs)
    feed_target=max(0,animals*3)
    if animals and total_wheat<feed_target and day<29 and len(orders)<10:
        need=min(60,feed_target-total_wheat); live=float(prices.get("WHEAT",25) or 25)
        affordable=max(0,int(max(0.0,spendable-350)//max(1.0,live))); buy=min(need,affordable)
        if buy>0:
            orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*live

    # Q3 biological factory.  Animal capex gets a protected market slot before
    # discretionary crop seeds.  Buy only against built empty pasture.
    if lands>=3 and day<=18 and not bought_land and len(orders)<10:
        empty_slots=sum(1 for _,t in _q3_pastures(farm.get("tiles") or []) if not t.get("animal"))
        slots=empty_slots
        for a,target in (("COW",COW_TARGET),("SHEEP",SHEEP_TARGET)):
            if slots<=0 or len(orders)>=10: break
            deficit=max(0,target-counts[a]); cost=ANIMAL_COST[a]
            first_yield=8 if a=="COW" else 6; interval=2 if a=="COW" else 3; base_price=float(prices.get("MILK" if a=="COW" else "WOOL",160 if a=="COW" else 200) or 1)
            # Daily care banks approximately interval bonus units per production.
            cycles=max(0,(horizon-first_yield)//interval); units_per_cycle=interval+1
            animal_roi=(cycles*units_per_cycle*base_price-cost)/cost
            meta["ranked"].append([a.lower(),round(animal_roi,2)])
            affordable=max(0,int(max(0.0,spendable-450)//cost)); buy=min(deficit,slots,affordable,4)
            if buy>0 and animal_roi>0:
                orders.append(["BUY_ANIMAL",a,buy]); meta["cows" if a=="COW" else "sheep"]=buy; spendable-=buy*cost; slots-=buy

    # Crop capital fills serviceable idle land after land/labour/feed/animal slots.
    if day<=26 and len(orders)<10:
        remaining=max(25,(len(hands)+1)*6); need_by:Dict[str,int]={}
        for q in range(1,lands+1):
            if remaining<=0: break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                idle=min(idle,max(0,int(z.get("unlocked",0) or 0)-PASTURE_TARGET))
            take=min(idle,remaining,25); remaining-=take
            crop=_p._crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10: break
            have=int(seeds.get(crop,0) or 0); cap=25 if lands==1 and day<=9 and crop=="MELON" else 40
            need=max(0,min(cap,raw+3)-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-250)//cost)); buy=min(need,affordable)
            if buy>0:
                orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost

    return orders[:10],meta


# Patch the clean V33 executor.  V19 remains external benchmark-only.
_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any, configuration:Any=None):
    return _p.agent(observation,configuration)

def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear:bool=False): return _p.get_telemetry(clear=clear)
