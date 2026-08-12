"""V33.43 goose-dominant industrial livestock.

Mechanism under test: replace the V33.39 cow/sheep Q3 factory with a
remaining-horizon goose factory and permit Q4 to become a second goose district.
This is still the independent V33 architecture; V19.2 remains benchmark-only.

Why geese: Kaggriculture's published mechanics make eggs the fastest livestock
cash cycle (first yield day 4, then daily) and the egg market is much more glut-
resistant than milk/wool. Every surviving animal also creates one fertilizer per
day, so well-serviced geese compound two monetizable streams. Q3 is commissioned
first; Q4 unlocks only when Q3 is materially commissioned and the remaining
horizon covers land + goose + feed capital.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping, Set, Tuple
from agents import v33_industrial_v42 as _p

_v39 = _p._p
_b = _p._b
_parent_allocator = _p._capital_allocator
_parent_stats = _b._stats

GOOSE_COST = 300
GOOSE_PER_DISTRICT = 18
Q3_COOP_TARGET = 18
Q4_COOP_TARGET = 18
MAX_GEESE_3LAND = 18
MAX_GEESE_4LAND = 36

_PEAK = {"geese": 0, "coops": 0, "q3_coops": 0, "q4_coops": 0, "lands": 0}


def _quadrant(n: int, p: Tuple[int, int]) -> int:
    return _b._quadrant(n, p)


def _coop_state(tiles):
    coops=[]; geese=[]
    n=len(tiles) if isinstance(tiles,list) else 0
    for y,row in enumerate(tiles if isinstance(tiles,list) else []):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            if not isinstance(t,Mapping) or str(t.get("kind","")).upper()!="COOP": continue
            q=_quadrant(n,(x,y)); coops.append(((x,y),t,q))
            if str(t.get("animal","")).upper()=="GOOSE": geese.append(((x,y),t,q))
    return coops,geese


def _stats(tiles):
    """Correct the clean V33 telemetry so COOP animals count as animals."""
    global _PEAK
    s=_parent_stats(tiles)
    coops,geese=_coop_state(tiles)
    # The original clean V33 stats counted animals only on PASTURE tiles.
    byq={1:0,2:0,3:0,4:0}
    cq={1:0,2:0,3:0,4:0}
    for _,_,q in coops: cq[q]+=1
    for _,_,q in geese: byq[q]+=1
    for q,n in byq.items():
        try:s["districts"][q]["animals"] = int(s["districts"][q].get("animals",0) or 0) + n
        except Exception: pass
    s["animals"] = int(s.get("animals",0) or 0) + len(geese)
    _PEAK["geese"]=max(_PEAK["geese"],len(geese))
    _PEAK["coops"]=max(_PEAK["coops"],len(coops))
    _PEAK["q3_coops"]=max(_PEAK["q3_coops"],cq[3])
    _PEAK["q4_coops"]=max(_PEAK["q4_coops"],cq[4])
    _PEAK["lands"]=max(_PEAK["lands"],int(s.get("lands",0) or 0))
    return s


def _roles(lands:int, hand_count:int):
    """Protect crop throughput while giving industrial geese enough service."""
    total=hand_count+1
    roles=["q1"]*total
    if lands>=2:
        # Four crop operators remain after livestock commissioning; split them Q1/Q2.
        for i in range(1,total): roles[i]="q2" if i%2 else "q1"
    if lands>=3:
        crew=min(8,max(5,total-4))
        for i in range(total-crew,total):
            if i>=1: roles[i]="livestock"
    return roles


def _nearest(tiles,p,goals):
    best=None
    for g in goals:
        rr=_b._route(tiles,p,g)
        if rr is None: continue
        cand=(rr[0],g[1],g[0],g,rr[1])
        if best is None or cand<best: best=cand
    return best


def _go(tiles,p,g,action):
    if p==g: return action
    rr=_b._route(tiles,p,g)
    return [rr[1]] if rr is not None else ["PASS"]


def _livestock_action(obs,farm,idx,p,stats,reserved:Set[Tuple[int,int]]):
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    tiles=farm.get("tiles") or []; lands=int(stats.get("lands",0) or 0)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); inv=_b._inventory(private,idx)
    coops,geese=_coop_state(tiles)
    allowed={3} | ({4} if lands>=4 else set())
    coops=[z for z in coops if z[2] in allowed]; geese=[z for z in geese if z[2] in allowed]
    empty=[g for g,t,q in coops if not t.get("animal")]

    # Endgame: move monetizable output to the shed; market allocator liquidates it.
    output=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","GOOSE"})
    if day>=27 and output>0:
        return _b._to_shed(tiles,p,["DROP"]),"terminal_drop_goose"

    # Place purchased geese immediately so their four-day first-yield clock starts.
    if int(inv.get("GOOSE",0) or 0)>0 and empty:
        r=_nearest(tiles,p,[g for g in empty if g not in reserved])
        if r is not None:
            reserved.add(r[3]); return _go(tiles,p,r[3],["PLACE","GOOSE"]),"place_goose"

    # Feed is the hard survival invariant. A second missed day loses all invested capital.
    if int(inv.get("WHEAT",0) or 0)>0:
        goals=[]
        for g,t,q in geese:
            if not bool(t.get("fed_today",t.get("fed",False))) and g not in reserved: goals.append(g)
        r=_nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles,p,r[3],["FEED"]),"feed_goose"
    unfed=[g for g,t,q in geese if not bool(t.get("fed_today",t.get("fed",False))) and g not in reserved]
    if unfed and int(shed.get("WHEAT",0) or 0)>0:
        return _b._to_shed(tiles,p,["PICKUP","WHEAT",min(18,int(shed.get("WHEAT",0) or 0))]),"pickup_goose_feed"

    # Egg harvest is daily after maturity. Harvest before optional care/fertilizer
    # so max_held never blocks the next production tick.
    goals=[g for g,t,q in geese if int(t.get("yield_units",t.get("yield",0)) or 0)>0 and g not in reserved]
    r=_nearest(tiles,p,goals)
    if r is not None:
        reserved.add(r[3]); return _go(tiles,p,r[3],["HARVEST"]),"harvest_egg"

    # CARE banks bonus egg yield; with daily geese this turns into rapid recurring cash.
    if day<=26:
        goals=[g for g,t,q in geese if not bool(t.get("cared_today",t.get("cared",False))) and g not in reserved]
        r=_nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles,p,r[3],["CARE"]),"care_goose"

    # Fertilizer is a second independent daily revenue stream.
    goals=[g for g,t,q in geese if bool(t.get("fertilizer_available",False)) and g not in reserved]
    r=_nearest(tiles,p,goals)
    if r is not None:
        reserved.add(r[3]); return _go(tiles,p,r[3],["COLLECT_FERTILIZER"]),"collect_goose_fertilizer"

    if output>=6 or (output>0 and hour>=15):
        return _b._to_shed(tiles,p,["DROP"]),"drop_goose_output"

    # Pull geese from shed into worker inventory for placement.
    target_total=MAX_GEESE_4LAND if lands>=4 else MAX_GEESE_3LAND
    if len(geese)<target_total and int(shed.get("GOOSE",0) or 0)>0 and empty:
        return _b._to_shed(tiles,p,["PICKUP","GOOSE",1]),"pickup_goose"

    # Commission Q3 first, then Q4. Coops are action-capex, not coin-capex.
    q3c=sum(1 for _,_,q in coops if q==3); q4c=sum(1 for _,_,q in coops if q==4)
    target_q=None
    if day<=22 and lands>=3 and q3c<Q3_COOP_TARGET: target_q=3
    elif day<=22 and lands>=4 and q4c<Q4_COOP_TARGET: target_q=4
    if target_q is not None:
        goals=_b._empty_targets(tiles,{target_q},reserved)
        r=_nearest(tiles,p,goals)
        if r is not None:
            reserved.add(r[3]); return _go(tiles,p,r[3],["BUILD_COOP"]),"build_coop_q"+str(target_q)

    if output>0: return _b._to_shed(tiles,p,["DROP"]),"drop_goose_output"
    return None


def _capital_allocator(obs,farm,stats):
    """V33.42 allocator plus goose commissioning and an ROI-based Q4 unlock."""
    orders,meta=_parent_allocator(obs,farm,stats)
    if not isinstance(meta,dict): meta={}
    else: meta=dict(meta)
    day=int(obs.get("day",0) or 0); horizon=max(0,30-day)
    money=float(farm.get("money",0) or 0); lands=max(1,int(stats.get("lands",1) or 1))
    tiles=farm.get("tiles") or []; coops,geese=_coop_state(tiles)
    private=_b._m(obs.get("private")); shed=_b._m(private.get("shed")); invs=private.get("inventories",[])
    carried=0
    if isinstance(invs,list):
        for inv in invs: carried+=int(_b._m(inv).get("GOOSE",0) or 0)
    goose_total=len(geese)+int(shed.get("GOOSE",0) or 0)+carried
    q3c=sum(1 for _,_,q in coops if q==3); q4c=sum(1 for _,_,q in coops if q==4)
    capacity=q3c+q4c
    target=MAX_GEESE_4LAND if lands>=4 else (MAX_GEESE_3LAND if lands>=3 else 0)

    # Strip inherited cow/sheep capex; this revision tests goose economics cleanly.
    kept=[]
    for o in orders:
        if isinstance(o,list) and o and str(o[0]).upper()=="BUY_ANIMAL" and len(o)>1 and str(o[1]).upper() in {"COW","SHEEP"}:
            continue
        kept.append(o)
    orders=kept

    # Q4 has to be an economic decision, not a fixed schedule. Use conservative
    # egg-only payback; fertilizer upside is deliberately excluded from the gate.
    q3_geese=sum(1 for _,_,q in geese if q==3)
    q4_roi=-1.0
    if lands==3 and horizon>=9:
        remaining=max(0,horizon-4)  # four days to first egg yield
        per_goose_net=max(0.0,remaining*(50.0-30.0)-GOOSE_COST)
        projected=GOOSE_PER_DISTRICT*per_goose_net-4000.0
        q4_roi=projected/4000.0
        if day<=18 and q3c>=14 and q3_geese>=10 and money>=7000 and q4_roi>0 and not any(isinstance(o,list) and o and str(o[0]).upper()=="BUY_LAND" for o in orders):
            # Reserve a market slot for the industrial expansion order.
            orders=[o for o in orders if not (isinstance(o,list) and o and str(o[0]).upper()=="BUY_SEED")]
            if len(orders)>=10: orders=orders[:9]
            orders.append(["BUY_LAND"])
            meta["land"]=1; meta["land_cost"]=4000

    # Buy only against built coop capacity, so no goose sits idle in the shed.
    open_capacity=max(0,capacity-goose_total)
    need=max(0,target-goose_total)
    if lands>=3 and day<=23 and open_capacity>0 and need>0:
        # Parent orders can include sales before buys; keep a robust cash floor.
        reserve=1800+120*len(geese)
        affordable=max(0,int(max(0.0,money-reserve)//GOOSE_COST))
        buy=min(4,open_capacity,need,affordable)
        if buy>0:
            if len(orders)>=10:
                # Seed working capital yields to already-built livestock capacity.
                for i in range(len(orders)-1,-1,-1):
                    if isinstance(orders[i],list) and orders[i] and str(orders[i][0]).upper()=="BUY_SEED":
                        orders.pop(i); break
            if len(orders)<10:
                orders.append(["BUY_ANIMAL","GOOSE",buy]); meta["geese"]=buy

    meta["goose_total"]=goose_total
    meta["coop_capacity"]=capacity
    meta["q3_coops"]=q3c; meta["q4_coops"]=q4c; meta["q4_roi"]=round(q4_roi,3)
    return orders[:10],meta


# Patch the independent V33 executor used by V33.39/V33.42.
_b._stats=_stats
_b._roles=_roles
_v39._livestock_action=_livestock_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None):
    return _p.agent(observation,configuration)


def reset_state():
    global _PEAK
    _PEAK={"geese":0,"coops":0,"q3_coops":0,"q4_coops":0,"lands":0}
    return _p.reset_state()


def reset_telemetry(): return reset_state()
def get_telemetry(clear:bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return dict(_PEAK)
