"""V33.2 Industrial four-quadrant capital allocator.

Independent architecture for Kaggriculture. It owns land, labour, crop,
livestock/feed and reserve decisions directly; V19/V32 are benchmark controls
only and are not imported.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (("NORTH",0,-1),("SOUTH",0,1),("WEST",-1,0),("EAST",1,0))
CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
SELLABLE=("MELON","STRAWBERRY","TOMATO","CARROT","WHEAT","MILK","WOOL","EGG","FERTILIZER")
BASE_PRICE={"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"MILK":160,"WOOL":200,"EGG":50,"FERTILIZER":100}
SEED_COST={"WHEAT":10,"CARROT":20,"TOMATO":40,"STRAWBERRY":60,"MELON":80}
FIRST_YIELD={"WHEAT":2,"CARROT":2,"TOMATO":8,"STRAWBERRY":10,"MELON":10}
LAND_COST=1000; HIRE_COST=500; COW_COST=400
_LAST_STEP=-1; _PREV_MONEY=None; _CUM_REVENUE=0.0
_CUM_CAPEX={"land":0.0,"labour":0.0,"crop":0.0,"livestock":0.0,"feed":0.0}
_UNLOCK_STEP: Dict[int,int]={}; _RECORDS: deque=deque(maxlen=8192)

def _m(v): return v if isinstance(v,Mapping) else {}
def _obs(v):
    if isinstance(v,dict): return v
    out={}
    for k in ("player","step","day","hour","farms","private","market","town"):
        try: out[k]=getattr(v,k)
        except Exception: pass
    return out

def _kind(t):
    if t is None:return "EMPTY"
    if t=="LOCKED":return "LOCKED"
    if isinstance(t,Mapping):return str(t.get("kind",t.get("type","UNKNOWN"))).upper()
    return "UNKNOWN"

def _pos(v):
    if isinstance(v,Mapping):v=v.get("position",v.get("pos",[0,0]))
    try:return int(v[0]),int(v[1])
    except Exception:return (0,0)

def _inside(tiles,p):
    x,y=p; return 0<=y<len(tiles) and 0<=x<len(tiles[y])

def _route(tiles,start,goal):
    if start==goal:return (0,"PASS")
    q=deque([(start,0,None)]); seen={start}
    while q:
        (x,y),d,first=q.popleft()
        for a,dx,dy in MOVES:
            n=(x+dx,y+dy)
            if n in seen or not _inside(tiles,n):continue
            seen.add(n); f=first or a
            if n==goal:return d+1,f
            q.append((n,d+1,f))
    return None

def _nearest(tiles,start,goals):
    best=[]
    for g in goals:
        r=_route(tiles,start,g)
        if r is not None:best.append((r[0],g[1],g[0],g,r[1]))
    if not best:return None
    best.sort(); d,_,_,g,a=best[0]; return d,g,a

def _shed_cells(n):
    h=n//2; return {(h-1,h-1),(h,h-1),(h-1,h),(h,h)}
def _quadrant(n,p):
    h=n//2; x,y=p
    return 1 if x<h and y<h else 2 if x>=h and y<h else 3 if x<h and y>=h else 4

def _age(tile,day):
    raw=tile.get("planted_day",day); planted=day if raw is None else int(raw); return day-planted

def _inventory(private,idx):
    inv=private.get("inventories",[]); return _m(inv[idx]) if isinstance(inv,list) and idx<len(inv) else {}
def _inventory_total(inv): return sum(max(0,int(v or 0)) for v in inv.values())

def _farm_stats(tiles):
    d={q:{"unlocked":0,"empty":0,"productive":0,"plants":0,"pasture":0,"animals":0,"weeds":0,"crop_counts":{}} for q in range(1,5)}
    if not isinstance(tiles,list) or not tiles:return {"districts":d,"lands":0,"productive":0,"idle":0,"animals":0}
    n=len(tiles)
    for y,row in enumerate(tiles):
        if not isinstance(row,list):continue
        for x,t in enumerate(row):
            k=_kind(t)
            if k=="LOCKED":continue
            z=d[_quadrant(n,(x,y))]; z["unlocked"]+=1
            if k=="EMPTY":z["empty"]+=1
            elif k=="WEED":z["weeds"]+=1
            if k in {"PLANT","PASTURE","COOP"}:z["productive"]+=1
            if k=="PLANT":
                z["plants"]+=1; c=str(_m(t).get("crop","")).upper(); z["crop_counts"][c]=z["crop_counts"].get(c,0)+1
            if k=="PASTURE":
                z["pasture"]+=1
                if _m(t).get("animal"):z["animals"]+=1
    lands=sum(1 for z in d.values() if z["unlocked"]>4)
    return {"districts":d,"lands":lands,"productive":sum(z["productive"] for z in d.values()),"idle":sum(z["empty"] for z in d.values()),"animals":sum(z["animals"] for z in d.values())}

def _market_prices(obs):return _m(_m(obs.get("market")).get("prices"))
def _crop_score(c,day,p):return (p/max(1,SEED_COST[c]))*max(0.0,(29-day)/max(1,FIRST_YIELD[c]))
def _best_crop(obs,day,district):
    prices=_market_prices(obs); candidates=("TOMATO","STRAWBERRY","MELON") if day<=17 else ("WHEAT","CARROT","TOMATO")
    scored=[]
    for c in candidates:
        p=float(prices.get(c,BASE_PRICE[c]) or BASE_PRICE[c]); score=_crop_score(c,day,p)
        if district==2 and c=="STRAWBERRY":score*=1.08
        if district==4 and c=="MELON":score*=1.08
        scored.append((score,c))
    scored.sort(reverse=True); return scored[0][1]

def _plant_targets(tiles,districts):
    n=len(tiles); sheds=_shed_cells(n); out=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            p=(x,y)
            if t is None and p not in sheds and _quadrant(n,p) in districts:out.append(p)
    return out

def _pastures(tiles):
    out=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            if isinstance(t,Mapping) and _kind(t)=="PASTURE":out.append(((x,y),t))
    return out

def _return_shed(tiles,p,final):
    sheds=_shed_cells(len(tiles))
    if p in sheds:return final
    r=_nearest(tiles,p,sheds); return [r[2]] if r else ["PASS"]

def _crop_tasks(tiles,day,districts,reserved):
    out=[]; n=len(tiles)
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            p=(x,y)
            if _quadrant(n,p) not in districts or p in reserved:continue
            k=_kind(t)
            if k=="WEED":out.append((1,p,["DIG"]))
            elif k=="PLANT" and isinstance(t,Mapping):
                watered=bool(t.get("watered_today",False)); danger=int(t.get("consecutive_unwatered",0) or 0)>=1
                yld=int(t.get("yield_units",0) or 0); crop=str(t.get("crop","")).upper(); age=_age(t,day)
                if not watered and danger:out.append((0,p,["WATER"]))
                elif yld>0 and age>=FIRST_YIELD.get(crop,2):out.append((1,p,["HARVEST"]))
                elif not watered:out.append((2,p,["WATER"]))
    return out

def _best_task(tiles,p,tasks,reserved):
    choices=[]
    for pr,target,act in tasks:
        if target in reserved:continue
        r=_route(tiles,p,target)
        if r:choices.append((pr,r[0],target[1],target[0],target,act,r[1]))
    if not choices:return None
    choices.sort(); _,d,_,_,target,act,first=choices[0]; reserved.add(target); return act if d==0 else [first]

def _livestock_action(obs,farm,idx,p,reserved,target_cows):
    tiles=farm.get("tiles") or []; private=_m(obs.get("private")); shed=_m(private.get("shed")); inv=_inventory(private,idx)
    ps=_pastures(tiles); active=[(pp,t) for pp,t in ps if str(t.get("animal","")).upper()=="COW"]; empty=[pp for pp,t in ps if not t.get("animal")]
    if int(inv.get("WHEAT",0) or 0)>0:
        r=_nearest(tiles,p,[pp for pp,t in active if not bool(t.get("fed_today",False)) and pp not in reserved])
        if r:reserved.add(r[1]); return (["FEED"] if r[0]==0 else [r[2]]),"feed"
    if any(not bool(t.get("fed_today",False)) for _,t in active) and int(shed.get("WHEAT",0) or 0)>0:return _return_shed(tiles,p,["PICKUP","WHEAT",min(6,int(shed.get("WHEAT",0) or 0))]),"pickup_feed"
    if int(inv.get("COW",0) or 0)>0 and empty:
        r=_nearest(tiles,p,[x for x in empty if x not in reserved])
        if r:reserved.add(r[1]); return (["PLACE","COW"] if r[0]==0 else [r[2]]),"place_cow"
    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","COW"})
    if output>0:return _return_shed(tiles,p,["DROP"]),"drop_livestock"
    for pred,act,label in [(lambda t:int(t.get("yield_units",0) or 0)>0,["HARVEST"],"harvest_livestock"),(lambda t:not bool(t.get("cared_today",False)),["CARE"],"care"),(lambda t:bool(t.get("fertilizer_available",False)),["COLLECT_FERTILIZER"],"fertilizer")]:
        r=_nearest(tiles,p,[pp for pp,t in active if pred(t) and pp not in reserved])
        if r:reserved.add(r[1]); return (act if r[0]==0 else [r[2]]),label
    if int(shed.get("COW",0) or 0)>0 and empty:return _return_shed(tiles,p,["PICKUP","COW",1]),"pickup_cow"
    if len(ps)<target_cows:
        n=len(tiles); sheds=_shed_cells(n); goals=[]
        for y,row in enumerate(tiles):
            for x,t in enumerate(row):
                pp=(x,y)
                if t is None and pp not in sheds and _quadrant(n,pp)==3 and pp not in reserved:goals.append(pp)
        r=_nearest(tiles,p,goals)
        if r:reserved.add(r[1]); return (["BUILD_PASTURE"] if r[0]==0 else [r[2]]),"build_pasture"
    return None,"idle_livestock"

def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,livestock_worker):
    tiles=farm.get("tiles") or []; day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); private=_m(obs.get("private")); inv=_inventory(private,idx); lands=int(stats.get("lands",0) or 0)
    target_cows=0 if lands<3 or day>23 else min(16,max(6,2*max(1,len(farm.get("hands") or [])//3)))
    if livestock_worker and target_cows:
        a,label=_livestock_action(obs,farm,idx,p,reserved,target_cows)
        if a is not None:return a,label
    districts={1};
    if lands>=2:districts.add(2)
    if lands>=4:districts.add(4)
    a=_best_task(tiles,p,_crop_tasks(tiles,day,districts,reserved),reserved)
    if a is not None:return a,"crop_task"
    load=_inventory_total(inv)
    if load>=5 or (load>0 and hour>=20):return _return_shed(tiles,p,["DROP"]),"drop_crop"
    if day<=19:
        choices=[]
        for g in _plant_targets(tiles,districts):
            if g in reserved:continue
            q=_quadrant(len(tiles),g); crop=_best_crop(obs,day,q)
            if seed_budget.get(crop,0)<=0:continue
            r=_route(tiles,p,g)
            if r:choices.append((r[0],g[1],g[0],g,crop,r[1]))
        if choices:
            choices.sort(); d,_,_,g,crop,first=choices[0]; reserved.add(g)
            if d==0:seed_budget[crop]-=1; return ["PLANT",crop],"plant_"+crop.lower()
            return [first],"move_plant"
    if load>0:return _return_shed(tiles,p,["DROP"]),"drop_crop"
    return ["PASS"],"idle"

def _capital_allocator(obs,farm,stats):
    day=int(obs.get("day",0) or 0); horizon=max(0,30-day); private=_m(obs.get("private")); shed=_m(private.get("shed")); seeds=_m(private.get("seeds")); money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    lands=int(stats.get("lands",0) or 0); animals=int(stats.get("animals",0) or 0); qs=stats["districts"]; orders=[]; meta={"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}; liquidate=day>=28
    for item in SELLABLE:
        qty=int(shed.get(item,0) or 0); keep=(animals*4 if item=="WHEAT" and not liquidate else 0); sell=max(0,qty-keep)
        if sell>0 and (liquidate or sell>=3):
            orders.append(["SELL",item,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10:return orders,meta
    reserve=600+140*len(hands)+80*animals; meta["reserve"]=reserve; spendable=max(0.0,money-reserve)
    if lands<4 and horizon>=11:
        land_roi=((21*max(1,horizon//10)*6*BASE_PRICE["MELON"])-LAND_COST)/LAND_COST; meta["ranked"].append(["land",round(land_roi,2)]); min_day={1:2,2:5,3:7}.get(lands,2)
        if day>=min_day and spendable>=LAND_COST+1200 and len(orders)<10:orders.append(["BUY_LAND"]); meta["land"]=1; spendable-=LAND_COST
    owned_cells=sum(int(z["unlocked"]) for z in qs.values()); desired=min(18,max(4,(owned_cells-4+5)//6))
    if lands>=3:desired=max(desired,10)
    if lands>=4:desired=max(desired,14)
    meta["ranked"].append(["labour",round(max(0.0,(horizon*150-HIRE_COST)/HIRE_COST),2)])
    for _ in range(min(3,max(0,desired-len(hands)))):
        if spendable<HIRE_COST+300 or len(orders)>=10:break
        orders.append(["HIRE"]); meta["hires"]+=1; spendable-=HIRE_COST
    q3=qs[3]; pastures=int(q3["pasture"]); cow_total=animals+int(shed.get("COW",0) or 0); meta["ranked"].append(["cow",round(max(0.0,(horizon*120-COW_COST)/COW_COST),2)])
    if lands>=3 and day<=21 and pastures>cow_total and cow_total<16 and spendable>=COW_COST+500 and len(orders)<10:
        buy=min(3,pastures-cow_total,16-cow_total,int((spendable-300)//COW_COST))
        if buy>0:orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=COW_COST*buy
    wheat=int(shed.get("WHEAT",0) or 0); need=max(0,animals*5-wheat)
    if need>0 and spendable>=200 and len(orders)<10:orders.append(["BUY_PRODUCT","WHEAT",need]); meta["feed"]=need
    if not liquidate and day<=19:
        crop_need={}
        for q in (1,2,4):
            if q==4 and lands<4:continue
            if q==2 and lands<2:continue
            crop=_best_crop(obs,day,q); crop_need[crop]=crop_need.get(crop,0)+int(qs[q]["empty"])
        for crop,need0 in sorted(crop_need.items(),key=lambda kv:-kv[1]):
            have=int(seeds.get(crop,0) or 0); need=max(0,min(30,need0+4-have))
            if need<=0 or len(orders)>=10:continue
            affordable=max(0,int(max(0,spendable-300)//SEED_COST[crop])); buy=min(need,affordable)
            if buy>0:orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*SEED_COST[crop]
    return orders[:10],meta

def reset_state():
    global _LAST_STEP,_PREV_MONEY,_CUM_REVENUE,_CUM_CAPEX,_UNLOCK_STEP
    _LAST_STEP=-1; _PREV_MONEY=None; _CUM_REVENUE=0.0; _CUM_CAPEX={"land":0.0,"labour":0.0,"crop":0.0,"livestock":0.0,"feed":0.0}; _UNLOCK_STEP={}; _RECORDS.clear()
def reset_telemetry():reset_state()
def get_telemetry(clear=False):
    out=list(_RECORDS)
    if clear:_RECORDS.clear()
    return out

def agent(observation,configuration=None):
    global _LAST_STEP,_PREV_MONEY,_CUM_REVENUE,_CUM_CAPEX,_UNLOCK_STEP
    obs=_obs(observation); player=int(obs.get("player",0) or 0); farms=obs.get("farms") or []
    if not isinstance(farms,list) or player>=len(farms):return {"farmer":["PASS"],"hands":[],"market":[]}
    farm=_m(farms[player]); tiles=farm.get("tiles") or []; hands=list(farm.get("hands") or []); out={"farmer":["PASS"],"hands":[["PASS"] for _ in hands],"market":[]}
    if not isinstance(tiles,list) or not tiles:return out
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); step=int(obs.get("step",day*24+hour) or 0)
    if _LAST_STEP>=0 and step<=_LAST_STEP:reset_state()
    _LAST_STEP=step; stats=_farm_stats(tiles); lands=int(stats["lands"])
    for q,z in stats["districts"].items():
        if int(z["unlocked"])>4 and q not in _UNLOCK_STEP:_UNLOCK_STEP[q]=step
    private=_m(obs.get("private")); rawseeds=_m(private.get("seeds")); seed_budget={c:int(rawseeds.get(c,0) or 0) for c in CROPS}; livestock_start=max(1,int(len(hands)*0.62)) if lands>=3 else 10**6; reserved=set(); units=[_pos(farm.get("farmer",[0,0]))]+[_pos(h) for h in hands]; labels=[]
    for idx,p in enumerate(units):
        a,label=_unit_action(obs,farm,idx,p,stats,reserved,seed_budget,(idx>0 and idx>=livestock_start)); labels.append(label)
        if idx==0:out["farmer"]=a
        else:out["hands"][idx-1]=a
    market,meta=_capital_allocator(obs,farm,stats); out["market"]=market
    if meta.get("land"):_CUM_CAPEX["land"]+=LAND_COST
    _CUM_CAPEX["labour"]+=HIRE_COST*int(meta.get("hires",0) or 0); _CUM_CAPEX["livestock"]+=COW_COST*int(meta.get("cows",0) or 0); _CUM_CAPEX["feed"]+=25*int(meta.get("feed",0) or 0); _CUM_CAPEX["crop"]+=sum(SEED_COST.get(c,0)*int(q) for c,q in meta.get("seeds",{}).items())
    money=float(farm.get("money",0) or 0)
    if _PREV_MONEY is not None and money>_PREV_MONEY:_CUM_REVENUE+=money-_PREV_MONEY
    _PREV_MONEY=money; total_capex=sum(_CUM_CAPEX.values()); reinvest=total_capex/max(1.0,total_capex+_CUM_REVENUE); productive=int(stats["productive"]); idle=int(stats["idle"]); util=productive/max(1,productive+idle)
    _RECORDS.append({"step":step,"day":day,"hour":hour,"money":money,"estimated_net_worth":money+productive*100+stats["animals"]*COW_COST,"lands":lands,"land_unlock_steps":dict(_UNLOCK_STEP),"productive":productive,"idle":idle,"utilization":util,"hands":len(hands),"animals":int(stats["animals"]),"q1":dict(stats["districts"][1]),"q2":dict(stats["districts"][2]),"q3":dict(stats["districts"][3]),"q4":dict(stats["districts"][4]),"unit_actions":labels,"market_actions":[list(x) for x in market],"allocator":meta,"cumulative_capex":dict(_CUM_CAPEX),"cumulative_revenue_proxy":_CUM_REVENUE,"reinvestment_ratio":reinvest})
    return out
