"""V33.37 demand-aware mixed livestock industrial factory.

Independent V33 architecture built on the best clean V33.25 economic control,
not on V19 and not on the disproven batch-sale branch. V33.25's 24-game median
was ~75k with 0 invalids but only ~7 cows / 8 Q3 pastures. This revision keeps
its demand-aware crop portfolio and realized-sales policy, while turning Q3 into
a fixed-capacity 14-pasture 8-cow/6-sheep factory and explicitly services the
fertilizer by-product. Q4 remains conditional on realized Q3 commissioning and
remaining-horizon ROI.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial_v25 as _p

_b = _p._b
_base_allocator = _p._capital_allocator
_base_unit_action = _p._unit_action

COW_TARGET = 8
SHEEP_TARGET = 6
PASTURE_TARGET = 14
ANIMAL_COST = {"COW": 400, "SHEEP": 500}


def _animal_counts(obs: Mapping[str, Any], farm: Mapping[str, Any]) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0}
    for row in farm.get("tiles") or []:
        if not isinstance(row, list): continue
        for tile in row:
            if not isinstance(tile, Mapping): continue
            a = str(tile.get("animal", "") or "").upper()
            if a in counts: counts[a] += 1
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    for a in counts: counts[a] += int(shed.get(a, 0) or 0)
    inventories = private.get("inventories", [])
    if isinstance(inventories, list):
        for inv in inventories:
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


def _nearest(tiles,p,poss):
    best=None
    for g in poss:
        rr=_b._route(tiles,p,g)
        if rr is None: continue
        cand=(rr[0],g[1],g[0],g)
        if best is None or cand < best: best=cand
    return None if best is None else best[3]


def _go(tiles,p,g,action):
    if p==g: return action
    rr=_b._route(tiles,p,g)
    return [rr[1]] if rr is not None else ["PASS"]


def _livestock_action(obs,farm,idx,p,stats,reserved):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    tiles=farm.get("tiles") or []; private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); inv=_b._inventory(private,idx)
    q3=_q3_pastures(tiles); active=[(g,t) for g,t in q3 if str(t.get("animal","") or "").upper() in {"COW","SHEEP"}]
    empty=[g for g,t in q3 if not t.get("animal")]
    for a in ("COW","SHEEP"):
        if int(inv.get(a,0) or 0)>0 and empty:
            g=_nearest(tiles,p,[x for x in empty if x not in reserved])
            if g is not None: reserved.add(g); return _go(tiles,p,g,["PLACE",a]),"place_"+a.lower()
    if int(inv.get("WHEAT",0) or 0)>0:
        g=_nearest(tiles,p,[g for g,t in active if not bool(t.get("fed_today",False)) and g not in reserved])
        if g is not None: reserved.add(g); return _go(tiles,p,g,["FEED"]),"feed"
    unfed=[g for g,t in active if not bool(t.get("fed_today",False)) and g not in reserved]
    if unfed and int(shed.get("WHEAT",0) or 0)>0:
        return _b._to_shed(tiles,p,["PICKUP","WHEAT",min(10,int(shed.get("WHEAT",0) or 0))]),"pickup_feed"
    g=_nearest(tiles,p,[g for g,t in active if bool(t.get("fertilizer_available",False)) and g not in reserved])
    if g is not None: reserved.add(g); return _go(tiles,p,g,["COLLECT_FERTILIZER"]),"collect_fertilizer"
    g=_nearest(tiles,p,[g for g,t in active if int(t.get("yield_units",0) or 0)>0 and g not in reserved])
    if g is not None: reserved.add(g); return _go(tiles,p,g,["HARVEST"]),"harvest_livestock"
    g=_nearest(tiles,p,[g for g,t in active if not bool(t.get("cared_today",False)) and g not in reserved])
    if g is not None: reserved.add(g); return _go(tiles,p,g,["CARE"]),"care"
    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","COW","SHEEP"})
    if output>=5 or (output>0 and hour>=17): return _b._to_shed(tiles,p,["DROP"]),"drop_livestock"
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
    if role=="livestock" and int(stats.get("lands",0) or 0)>=3:
        r=_livestock_action(obs,farm,idx,p,stats,reserved)
        if r is not None: return r
        role="feed"
    return _base_unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role)


def _capital_allocator(obs,farm,stats):
    orders,meta=_base_allocator(obs,farm,stats)
    day=int(obs.get("day",0) or 0); horizon=max(0,30-day); money=float(farm.get("money",0) or 0)
    lands=max(1,int(stats.get("lands",1) or 1)); productive=int(stats.get("productive",0) or 0); q3=stats.get("districts",{}).get(3,{})
    counts=_animal_counts(obs,farm); tiles=farm.get("tiles") or []
    clean=[o for o in orders if not (isinstance(o,list) and o and str(o[0]).upper()=="BUY_ANIMAL")]
    if lands==3:
        q3a=int(q3.get("animals",0) or 0); q3p=int(q3.get("pasture",0) or 0); q3prod=int(q3.get("productive",0) or 0)
        projected=max(0,horizon-3)*2100-4000
        q4_ok=day<=17 and horizon>=12 and q3a>=12 and q3p>=14 and q3prod>=14 and productive>=50 and money>=14000 and projected>=8000
        if not q4_ok:
            clean=[o for o in clean if not (isinstance(o,list) and o and str(o[0]).upper()=="BUY_LAND")]
            meta=dict(meta); meta["land"]=0; meta["land_cost"]=0; meta.setdefault("ranked",[]).append(["q4_realized_roi",-1.0])
        else: meta.setdefault("ranked",[]).append(["q4_realized_roi",1.0])
    if lands>=3 and day<=18 and len(clean)<10:
        empty_slots=sum(1 for _,t in _q3_pastures(tiles) if not t.get("animal"))
        if empty_slots>0:
            prices=_b._prices(obs); reserve=900+int(stats.get("animals",0) or 0)*170; spend=max(0.0,money-reserve)
            if any(o and o[0]=="BUY_LAND" for o in clean): spend-=4000
            for o in clean:
                if isinstance(o,list) and len(o)>=3 and o[0]=="BUY_PRODUCT" and o[1]=="WHEAT": spend-=int(o[2])*float(prices.get("WHEAT",25) or 25)
            deficits={"COW":max(0,COW_TARGET-counts["COW"]),"SHEEP":max(0,SHEEP_TARGET-counts["SHEEP"])}; slots=empty_slots
            for a in ("COW","SHEEP"):
                if slots<=0 or len(clean)>=10: break
                cost=ANIMAL_COST[a]; affordable=max(0,int(max(0.0,spend)//cost)); buy=min(deficits[a],slots,affordable,4)
                if buy>0:
                    clean.append(["BUY_ANIMAL",a,buy]); spend-=buy*cost; slots-=buy; meta.setdefault("mixed_animals",{})[a]=buy
    meta=dict(meta); meta["cow_total"]=counts["COW"]; meta["sheep_total"]=counts["SHEEP"]; meta["mixed_target"]=[8,6]
    return clean[:10],meta


_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation: Any, configuration: Any=None): return _p.agent(observation,configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
