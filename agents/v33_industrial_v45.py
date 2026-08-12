"""V33.45 mechanics-priced four-quadrant factory.

Independent V33 industrial strategy over the clean V33 executor/router.  This is
not a V19/V32 policy mutation.  The controller uses the verified Kaggriculture
mechanics: $1k/$2k/$4k land, daily Fibonacci labour, terminal-cash scoring,
per-unit market curves, day-workers, and animal feed/care refresh rules.

Architecture
------------
Q1: fast wheat bootstrap -> one bounded melon scarcity harvest -> short crops.
Q2: continuous marginal-price crop cash engine.
Q3: 18 coops + 6 pastures, mixed goose/cow/sheep factory.
Q4: ROI-gated 8-coop overlay + crop production.

Animal service intentionally feeds/care on alternate days (or whenever an
animal already has one unfed day), which is mechanics-safe and roughly halves
feed/service load while preserving care bonuses.  Fertilizer is collected only
while its live price justifies the worker action.  Final two days liquidate all
shed output because reward is terminal bank cash only.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Set, Tuple
from agents import v33_industrial_v23 as _v23

_b = _v23._b
GAME_DAYS = 30
SEED_COST = {"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
ANIMAL_COST = {"GOOSE":300,"COW":400,"SHEEP":500}
PRODUCT = {"GOOSE":"EGG","COW":"MILK","SHEEP":"WOOL"}
FIRST = {"GOOSE":4,"COW":8,"SHEEP":6}
INTERVAL = {"GOOSE":1,"COW":2,"SHEEP":3}

# Verified engine allows movement over locked cells.  Tile operations remain
# guarded by the environment, so using that movement rule is safe and prevents
# shed-spawn stranding / needless detours.
def _walkable(tiles, p):
    return _b._inside(tiles, p)
_b._walkable = _walkable


def _species(tile: Mapping[str, Any]) -> str:
    a = tile.get("animal")
    if isinstance(a, Mapping):
        for k in ("type","kind","name","species","animal_type"):
            if a.get(k): return str(a[k]).upper()
        return ""
    return str(a or "").upper()


def _stats(tiles: Any) -> Dict[str, Any]:
    d={q:{"unlocked":0,"productive":0,"idle":0,"plants":0,"pasture":0,"coop":0,
          "animals":0,"geese":0,"cows":0,"sheep":0,"weeds":0,"crop_counts":{}}
       for q in range(1,5)}
    if not isinstance(tiles,list) or not tiles:
        return {"districts":d,"lands":0,"productive":0,"idle":0,"animals":0,
                "geese":0,"cows":0,"sheep":0}
    n=len(tiles); sheds=_b._shed_cells(n)
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            k=_b._kind(t)
            if k=="LOCKED": continue
            q=_b._quadrant(n,(x,y)); z=d[q]; z["unlocked"]+=1
            if k=="EMPTY" and (x,y) not in sheds: z["idle"]+=1
            elif k=="WEED": z["weeds"]+=1
            if k in {"PLANT","PASTURE","COOP"}: z["productive"]+=1
            if k=="PLANT" and isinstance(t,Mapping):
                z["plants"]+=1; c=str(t.get("crop","")).upper(); z["crop_counts"][c]=z["crop_counts"].get(c,0)+1
            if k=="PASTURE": z["pasture"]+=1
            if k=="COOP": z["coop"]+=1
            if isinstance(t,Mapping):
                a=_species(t)
                if a:
                    z["animals"]+=1
                    if a=="GOOSE": z["geese"]+=1
                    elif a=="COW": z["cows"]+=1
                    elif a=="SHEEP": z["sheep"]+=1
    lands=sum(1 for z in d.values() if int(z["unlocked"])>4)
    return {"districts":d,"lands":lands,"productive":sum(z["productive"] for z in d.values()),
            "idle":sum(z["idle"] for z in d.values()),"animals":sum(z["animals"] for z in d.values()),
            "geese":sum(z["geese"] for z in d.values()),"cows":sum(z["cows"] for z in d.values()),
            "sheep":sum(z["sheep"] for z in d.values())}
_b._stats = _stats


def _age(tile: Mapping[str,Any], day:int)->int:
    try:return max(0,day-int(tile.get("planted_day",day)))
    except Exception:return 0


def _tile_tasks(tiles:Any,districts:Set[int],reserved:Set[Tuple[int,int]]):
    tasks=[]; day=int(getattr(_b,"_CURRENT_DAY",0) or 0); n=len(tiles) if isinstance(tiles,list) else 0
    maxday={"WHEAT":4,"CARROT":3,"MELON":10}
    for y,row in enumerate(tiles if isinstance(tiles,list) else []):
        if not isinstance(row,list):continue
        for x,t in enumerate(row):
            p=(x,y)
            if _b._quadrant(n,p) not in districts or p in reserved:continue
            k=_b._kind(t)
            if k=="WEED": tasks.append((2,p,["DIG"],"dig")); continue
            if k!="PLANT" or not isinstance(t,Mapping):continue
            crop=str(t.get("crop","")).upper(); watered=bool(t.get("watered_today",False)); yld=int(t.get("yield_units",0) or 0)
            danger=int(t.get("consecutive_unwatered",0) or 0)>=1
            if yld>0 and (crop not in maxday or day>=28 or _age(t,day)>=maxday[crop]):
                tasks.append((0,p,["HARVEST"],"harvest_crop"))
            elif not watered and day<29:
                tasks.append((0 if danger else 1,p,["WATER"],"water_urgent" if danger else "water"))
    return tasks
_b._tile_tasks = _tile_tasks


def _crop_score(crop:str, price:float, horizon:int)->float:
    # Expected unfertilized units under verified advanced mechanics.
    units={"WHEAT":4,"CARROT":3,"TOMATO":4,"STRAWBERRY":4}[crop]
    dur={"WHEAT":4,"CARROT":3,"TOMATO":12,"STRAWBERRY":17}[crop]
    if horizon<dur:return -1e12
    return (units*price-SEED_COST[crop])/dur


def _crop_for(day:int,district:int,obs:Mapping[str,Any])->str:
    # D0-3 fast liquidity. Q1 then consumes exactly one quadrant of melon market
    # capacity; no other district plants melon, avoiding the square-curve collapse.
    if day<=3:return "WHEAT"
    if district==1 and 4<=day<=7:return "MELON"
    horizon=max(0,GAME_DAYS-day); prices=_b._prices(obs)
    allowed=("WHEAT","CARROT","TOMATO","STRAWBERRY")
    ranked=[(_crop_score(c,float(prices.get(c,_b.VALUE.get(c,1)) or _b.VALUE.get(c,1)),horizon),c) for c in allowed]
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked and ranked[0][0]>-1e11 else "WHEAT"
_b._crop_for = _crop_for


def _animals_everywhere(farm:Mapping[str,Any], obs:Mapping[str,Any])->Dict[str,int]:
    out={a:0 for a in ANIMAL_COST}
    for row in farm.get("tiles") or []:
        if not isinstance(row,list):continue
        for t in row:
            if isinstance(t,Mapping):
                a=_species(t)
                if a in out:out[a]+=1
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed"))
    for a in out:out[a]+=int(shed.get(a,0) or 0)
    invs=private.get("inventories",[])
    if isinstance(invs,list):
        for inv in invs:
            m=_b._m(inv)
            for a in out:out[a]+=int(m.get(a,0) or 0)
    return out


def _structure_cells(tiles, district:int, kind:str):
    out=[]; n=len(tiles) if isinstance(tiles,list) else 0
    for y,row in enumerate(tiles if isinstance(tiles,list) else []):
        if not isinstance(row,list):continue
        for x,t in enumerate(row):
            if _b._quadrant(n,(x,y))==district and isinstance(t,Mapping) and str(t.get("kind","")).upper()==kind:
                out.append(((x,y),t))
    return out


def _nearest(tiles,p,goals):
    best=None
    for g in goals:
        rr=_b._route(tiles,p,g)
        if rr is None:continue
        c=(rr[0],g[1],g[0],g,rr[1])
        if best is None or c<best:best=c
    return best


def _go(tiles,p,g,act):
    if p==g:return act
    rr=_b._route(tiles,p,g)
    return [rr[1]] if rr is not None else ["PASS"]


def _livestock_action(obs,farm,idx,p,stats,reserved,district:int):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); tiles=farm.get("tiles") or []
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); inv=_b._inventory(private,idx)
    structures=[]; active=[]; empty=[]
    for kind in ("COOP","PASTURE"):
        for g,t in _structure_cells(tiles,district,kind):
            structures.append((g,t)); a=_species(t)
            if a:active.append((g,t,a))
            else:empty.append((g,kind))

    # Terminal conversion outranks optional husbandry.
    animal_items=sum(int(inv.get(a,0) or 0) for a in ANIMAL_COST)
    feed=int(inv.get("WHEAT",0) or 0)
    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in set(ANIMAL_COST)|{"WHEAT"})
    if day>=28 and output>0:return _b._to_shed(tiles,p,["DROP"]),"terminal_drop_livestock"

    # Purchased livestock: place immediately on matching structure.
    for a in ("GOOSE","COW","SHEEP"):
        if int(inv.get(a,0) or 0)<=0:continue
        kind="COOP" if a=="GOOSE" else "PASTURE"; goals=[g for g,k in empty if k==kind and g not in reserved]
        r=_nearest(tiles,p,goals)
        if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["PLACE",a]),"place_"+a.lower()

    # Feed is mandatory after one skipped day, otherwise alternate service days.
    def need_feed(t):
        if bool(t.get("fed_today",False)):return False
        if int(t.get("consecutive_unfed",0) or 0)>=1:return True
        placed=int(t.get("placed_day",day) or day)
        return ((day-placed)&1)==0
    feed_goals=[g for g,t,a in active if need_feed(t) and g not in reserved]
    if feed_goals:
        if feed>0:
            r=_nearest(tiles,p,feed_goals)
            if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["FEED"]),"feed_alt"
        if int(shed.get("WHEAT",0) or 0)>0:
            return _b._to_shed(tiles,p,["PICKUP","WHEAT",min(10,int(shed.get("WHEAT",0) or 0))]),"pickup_feed"

    # Care only after this animal was fed today; this creates a pending bonus at
    # the cheapest possible service frequency.
    care_goals=[g for g,t,a in active if bool(t.get("fed_today",False)) and not bool(t.get("cared_today",False)) and g not in reserved]
    r=_nearest(tiles,p,care_goals)
    if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["CARE"]),"care_on_feed"

    # Harvest before held-output caps are reached.
    harvest=[g for g,t,a in active if int(t.get("yield_units",0) or 0)>=2 and g not in reserved]
    if not harvest and hour>=15:harvest=[g for g,t,a in active if int(t.get("yield_units",0) or 0)>0 and g not in reserved]
    r=_nearest(tiles,p,harvest)
    if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["HARVEST"]),"harvest_livestock"

    # Fertilizer is valuable early but becomes a labour sink after its market
    # collapses; use the live price as the action opportunity-cost gate.
    fprice=float(_b._prices(obs).get("FERTILIZER",100) or 100)
    if fprice>=28 and day<=23:
        fert=[g for g,t,a in active if bool(t.get("fertilizer_available",False)) and g not in reserved]
        r=_nearest(tiles,p,fert)
        if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["COLLECT_FERTILIZER"]),"collect_fertilizer"

    if output>=6 or (output>0 and hour>=18):return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"

    # Pull waiting purchased animals from shed when capacity exists.
    for a in ("GOOSE","COW","SHEEP"):
        if int(shed.get(a,0) or 0)<=0:continue
        kind="COOP" if a=="GOOSE" else "PASTURE"
        if any(k==kind for g,k in empty):return _b._to_shed(tiles,p,["PICKUP",a,1]),"pickup_"+a.lower()

    # Commission free structures. Q3 is dense mixed livestock; Q4 is an eight
    # coop overlay and otherwise remains crop surface.
    q=stats["districts"][district]; coops=int(q.get("coop",0) or 0); past=int(q.get("pasture",0) or 0)
    coop_target=18 if district==3 else 8; pasture_target=6 if district==3 else 0
    if day<=18 and coops<coop_target:
        goals=_b._empty_targets(tiles,{district},reserved); r=_nearest(tiles,p,goals)
        if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["BUILD_COOP"]),"build_coop"
    if day<=16 and past<pasture_target:
        goals=_b._empty_targets(tiles,{district},reserved); r=_nearest(tiles,p,goals)
        if r is not None:reserved.add(r[3]);return _go(tiles,p,r[3],["BUILD_PASTURE"]),"build_pasture"
    if output>0:return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"
    return None


def _roles(lands:int,hand_count:int)->List[str]:
    total=hand_count+1; roles=["q1"]*total
    if lands>=2:
        for i in range(1,total):roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        # Six operators can service 24 Q3 structures under alternate-day feed.
        for i in range(max(1,total-6),total):roles[i]="livestock3"
    if lands>=4:
        # Two Q4 livestock operators, preserve >=6 crop operators across Q1/Q2/Q4.
        moved=0
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<3:roles[i]="q4";moved+=1
        for i in range(1,total):
            if roles[i] in {"q1","q2"} and moved<5:roles[i]="livestock4";moved+=1
    return roles
_b._roles = _roles


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); lands=int(stats.get("lands",0) or 0)
    tiles=farm.get("tiles") or []; private=_b._m(obs.get("private")); inv=_b._inventory(private,idx)
    if role=="livestock3" and lands>=3:
        r=_livestock_action(obs,farm,idx,p,stats,reserved,3)
        if r is not None:return r
        role="q2"
    if role=="livestock4" and lands>=4:
        r=_livestock_action(obs,farm,idx,p,stats,reserved,4)
        if r is not None:return r
        role="q4"
    districts={4} if role=="q4" and lands>=4 else {2} if role=="q2" and lands>=2 else {1}
    task=_b._best_task(tiles,p,_tile_tasks(tiles,districts,reserved),reserved)
    if task is not None:return task
    load=_b._inv_total(inv)
    if day>=28 and load>0:return _b._to_shed(tiles,p,["DROP"]),"terminal_drop"
    if load>=8 or (load>0 and hour>=18):return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    if day<=26 and hour<=18:
        choices=[]
        for g in _b._empty_targets(tiles,districts,reserved):
            crop=_crop_for(day,_b._quadrant(len(tiles),g),obs)
            if seed_budget.get(crop,0)<=0:continue
            rr=_b._route(tiles,p,g)
            if rr is not None:choices.append((rr[0],g[1],g[0],g,crop,rr[1]))
        if choices:
            choices.sort();dist,_,_,g,crop,first=choices[0];reserved.add(g)
            if dist==0:seed_budget[crop]-=1;return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_to_plant"
    if load>0:return _b._to_shed(tiles,p,["DROP"]),"drop_output"
    return ["PASS"],"idle"
_b._unit_action = _unit_action


def _fib0(n:int)->int:
    a,b=1,1
    for _ in range(n):a,b=b,a+b
    return a

def _hire_cost(existing:int,add:int)->int:return sum(_fib0(existing+i) for i in range(add))


def _sale_orders(obs,shed,animals:int,liquidate:bool,limit:int):
    prices=_b._prices(obs); keep_wheat=0 if liquidate else max(8,animals*2)
    ranked=[]
    for item in _b.SELLABLE:
        q=int(shed.get(item,0) or 0)-(keep_wheat if item=="WHEAT" else 0)
        if q<=0:continue
        p=float(prices.get(item,_b.VALUE.get(item,1)) or _b.VALUE.get(item,1));ranked.append((q*p,p,q,item))
    ranked.sort(reverse=True)
    return [["SELL",item,q] for _,_,q,item in ranked[:limit]]


def _animal_roi(a:str,horizon:int,prices:Mapping[str,Any],fert_price:float,wheat_price:float)->float:
    h=max(0,horizon-FIRST[a])
    if h<=0:return -1e9
    # Alternate feed/care: conservative long-run production rates.
    rate={"GOOSE":1.45,"COW":0.90,"SHEEP":0.62}[a]
    prod=float(prices.get(PRODUCT[a],_b.VALUE[PRODUCT[a]]) or _b.VALUE[PRODUCT[a]])
    fert=min(55.0,max(0.0,fert_price))*0.70  # discount future fertilizer glut/action cost
    feed=0.52*wheat_price
    profit=h*(rate*prod+fert-feed)-ANIMAL_COST[a]
    return profit/max(1,ANIMAL_COST[a])


def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0);hour=int(obs.get("hour",0) or 0);horizon=max(0,GAME_DAYS-day)
    private=_b._m(obs.get("private"));shed=_b._m(private.get("shed"));seeds=_b._m(private.get("seeds"));invs=private.get("inventories",[])
    money=float(farm.get("money",0) or 0);hands=list(farm.get("hands") or []);lands=max(1,int(stats.get("lands",1) or 1));animals=int(stats.get("animals",0) or 0)
    qs=stats["districts"];prices=_b._prices(obs);liquidate=day>=28
    meta:Dict[str,Any]={"land":0,"land_cost":0,"hires":0,"hire_cost":0,"animals_bought":{},"cows":0,"geese":0,"sheep":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[],"reinvestment":"operate"}

    # Dawn capacity is scarce because HIRE consumes one market slot each.  Build
    # daily workforce first; later turns realize sales/capex.
    desired=7 if lands==1 else 12 if lands==2 else 13 if lands==3 else 14
    if day>=25:desired=min(desired,12)
    if day>=28:desired=min(desired,9)
    orders:List[List[Any]]=[]
    if hour<=2 and len(hands)<desired:
        add=min(desired-len(hands),10)
        # Day 0 must also buy Q2 + bootstrap seed in the first market packet.
        if day==0 and hour==0:
            add=min(add,8)
            orders.append(["BUY_LAND"]);meta["land"]=1;meta["land_cost"]=1000
            orders.append(["BUY_SEED","WHEAT",50]);meta["seeds"]["WHEAT"]=50
        room=max(0,10-len(orders));add=min(add,room)
        orders.extend([["HIRE"] for _ in range(add)]);meta["hires"]=add;meta["hire_cost"]=_hire_cost(len(hands),add)
        return orders[:10],meta

    sale_slots=10 if liquidate else 5
    orders=_sale_orders(obs,shed,animals,liquidate,sale_slots);meta["sell_qty"]=sum(int(o[2]) for o in orders)
    if liquidate:return orders[:10],meta
    sale_cash=sum(int(o[2])*float(prices.get(o[1],_b.VALUE.get(o[1],1)) or _b.VALUE.get(o[1],1)) for o in orders)
    reserve=300+max(0,_hire_cost(0,desired)) + animals*18
    meta["reserve"]=reserve;spendable=max(0.0,money+0.75*sale_cash-reserve)

    # Fast land ladder: Q2 at D0; Q3 after first fast crop realization; Q4 after
    # Q3 commissioning starts and another positive crop turn.  All gates include
    # explicit remaining-horizon payback.
    land_cost={1:1000,2:2000,3:4000}.get(lands,10**9);land_roi=-1e9;land_ok=False
    if lands==2:
        land_roi=(max(0,horizon-4)*1700-land_cost)/land_cost
        land_ok=3<=day<=8 and int(stats.get("productive",0) or 0)>=35 and money+0.8*sale_cash>=land_cost+reserve+900
    elif lands==3:
        q3=qs[3]; commissioned=int(q3.get("coop",0) or 0)+int(q3.get("pasture",0) or 0)
        land_roi=(max(0,horizon-4)*1300-land_cost)/land_cost
        land_ok=5<=day<=12 and commissioned>=8 and money+0.8*sale_cash>=land_cost+reserve+900
    if lands in (2,3):meta["ranked"].append(["land",round(land_roi,2)])
    if lands<4 and land_ok and land_roi>0 and spendable>=land_cost and len(orders)<10:
        orders.append(["BUY_LAND"]);meta["land"]=1;meta["land_cost"]=land_cost;spendable-=land_cost;meta["reinvestment"]="land"

    # Feed runway is based on alternate-day feeding, not the old daily-feed
    # assumption. Bought wheat is valid operating input and also relieves market glut.
    carried=0
    if isinstance(invs,list):carried=sum(int(_b._m(x).get("WHEAT",0) or 0) for x in invs)
    total_wheat=int(shed.get("WHEAT",0) or 0)+carried;target_feed=max(12,animals*2)
    wheat_price=float(prices.get("WHEAT",25) or 25)
    if animals and total_wheat<target_feed and day<=27 and len(orders)<10:
        need=min(70,target_feed-total_wheat);aff=max(0,int(max(0.0,spendable-250)//max(1,wheat_price)));buy=min(need,aff)
        if buy>0:orders.append(["BUY_PRODUCT","WHEAT",buy]);meta["feed"]=buy;spendable-=buy*wheat_price

    # Biological capital: rank goose/cow/sheep against live product prices and
    # actual built structure capacity.  Goose is not hard-coded as the winner.
    counts=_animals_everywhere(farm,obs);fprice=float(prices.get("FERTILIZER",100) or 100)
    rois={a:_animal_roi(a,horizon,prices,fprice,wheat_price) for a in ANIMAL_COST}
    for a,r in sorted(rois.items(),key=lambda kv:-kv[1]):meta["ranked"].append([a.lower(),round(r,2)])
    if lands>=3 and day<=21 and len(orders)<10:
        coop_capacity=sum(int(qs[q].get("coop",0) or 0) for q in (3,4) if q<=lands)
        pasture_capacity=sum(int(qs[q].get("pasture",0) or 0) for q in (3,4) if q<=lands)
        open_cap={"GOOSE":max(0,coop_capacity-counts["GOOSE"]),
                  "COW":max(0,pasture_capacity-counts["COW"]-counts["SHEEP"]),
                  "SHEEP":max(0,pasture_capacity-counts["COW"]-counts["SHEEP"])}
        # At most one species order per turn; next turn re-ranks after price/cash changes.
        for a,r in sorted(rois.items(),key=lambda kv:-kv[1]):
            if r<=0 or open_cap[a]<=0:continue
            cost=ANIMAL_COST[a];aff=max(0,int(max(0.0,spendable-350)//cost));buy=min(4,open_cap[a],aff)
            if buy>0:
                orders.append(["BUY_ANIMAL",a,buy]);meta["animals_bought"][a]=buy;meta[a.lower()+"s" if a!="SHEEP" else "sheep"]=buy
                spendable-=buy*cost;meta["reinvestment"]="livestock";break

    # Crop working capital only for surface that can still complete a cycle.
    if day<=26 and len(orders)<10:
        need:Dict[str,int]={}
        for q in range(1,lands+1):
            z=qs[q];idle=int(z.get("idle",0) or 0)
            if q==3:idle=max(0,idle-max(0,24-(18+6)))  # effectively no crop reservation in Q3
            if q==4:idle=max(0,idle-8)                 # preserve eight future coop cells
            if idle<=0:continue
            crop=_crop_for(day,q,obs);need[crop]=need.get(crop,0)+idle
        for crop,raw in sorted(need.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:break
            have=int(seeds.get(crop,0) or 0);want=max(0,min(40,raw+4)-have);cost=SEED_COST[crop]
            aff=max(0,int(max(0.0,spendable-180)//cost));buy=min(want,aff)
            if buy>0:orders.append(["BUY_SEED",crop,buy]);meta["seeds"][crop]=buy;spendable-=buy*cost

    return orders[:10],meta
_b._capital_allocator = _capital_allocator

# Enriched mechanics-correct telemetry layered on the executor's existing
# per-step records.  The executor still supplies unlock timing, district crops,
# utilization, roles and action labels.
_TELEM_CAPEX={"land":0.0,"labour":0.0,"crop":0.0,"livestock":0.0,"feed":0.0}
_TELEM_REVENUE=0.0

def _enrich(out,obs,farm,stats):
    global _TELEM_REVENUE
    market=out.get("market",[]) if isinstance(out,dict) else [];prices=_b._prices(obs);lands=int(stats.get("lands",1) or 1);hands=len(farm.get("hands") or [])
    for o in market:
        if not isinstance(o,list) or not o:continue
        op=o[0]
        if op=="BUY_LAND":_TELEM_CAPEX["land"]+={1:1000,2:2000,3:4000}.get(lands,0);lands+=1
        elif op=="HIRE":_TELEM_CAPEX["labour"]+=_fib0(hands);hands+=1
        elif op=="BUY_SEED" and len(o)>=3:_TELEM_CAPEX["crop"]+=SEED_COST.get(o[1],0)*int(o[2])
        elif op=="BUY_ANIMAL" and len(o)>=3:_TELEM_CAPEX["livestock"]+=ANIMAL_COST.get(o[1],0)*int(o[2])
        elif op=="BUY_PRODUCT" and len(o)>=3 and o[1]=="WHEAT":_TELEM_CAPEX["feed"]+=float(prices.get("WHEAT",25) or 25)*int(o[2])
        elif op=="SELL" and len(o)>=3:_TELEM_REVENUE+=float(prices.get(o[1],_b.VALUE.get(o[1],1)) or 1)*int(o[2])
    if _b._RECORDS:
        r=_b._RECORDS[-1];r["v45_true_capex_proxy"]=dict(_TELEM_CAPEX);r["v45_sale_revenue_quote"]=_TELEM_REVENUE
        r["geese"]=int(stats.get("geese",0) or 0);r["cows"]=int(stats.get("cows",0) or 0);r["sheep"]=int(stats.get("sheep",0) or 0)
        r["shed_snapshot"]=dict(_b._m(_b._m(obs.get("private")).get("shed")));r["market_prices"]=dict(prices)
        cap=sum(_TELEM_CAPEX.values());r["v45_reinvestment_ratio"]=cap/max(1.0,cap+_TELEM_REVENUE)

_base_agent=_b.agent

def agent(observation:Any,configuration:Any=None):
    obs=_b._obs(observation);_b._CURRENT_DAY=int(obs.get("day",0) or 0);player=int(obs.get("player",0) or 0);farms=obs.get("farms") or []
    out=_base_agent(observation,configuration)
    if isinstance(farms,list) and player<len(farms):
        farm=_b._m(farms[player]);_enrich(out,obs,farm,_stats(farm.get("tiles") or []))
    return out

def reset_state():
    global _TELEM_CAPEX,_TELEM_REVENUE
    _TELEM_CAPEX={"land":0.0,"labour":0.0,"crop":0.0,"livestock":0.0,"feed":0.0};_TELEM_REVENUE=0.0;_b._CURRENT_DAY=0;return _b.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _b.get_telemetry(clear=clear)
def industrial_peaks():
    rows=get_telemetry(False)
    return {k:max([int(r.get(k,0) or 0) for r in rows] or [0]) for k in ("lands","productive","hands","animals","geese","cows","sheep")}
