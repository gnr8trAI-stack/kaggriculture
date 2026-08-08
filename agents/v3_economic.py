"""Kaggriculture v3 economic-throughput agent.

Replay-derived design:
- remain in the initial district until it is productively saturated;
- target a compact 4-cow + carrot production core;
- buy feed externally instead of dedicating land to wheat;
- aggressively service harvest/feed/care/fertilizer;
- sell output in small batches to reduce market impact;
- expand only if productive occupancy is high and maintenance backlog is low.
"""
from __future__ import annotations
from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
DIRECTIONS: Sequence[Tuple[str,int,int]] = (
    ("NORTH",0,-1),("SOUTH",0,1),("WEST",-1,0),("EAST",1,0)
)
FARMHOUSE=(4,4)
SELLABLE=("FERTILIZER","MILK","CARROT","WOOL","EGG","MELON","STRAWBERRY","TOMATO","WHEAT")
TARGET_COWS=4
TARGET_PASTURES=4
TARGET_CARROTS=4

def _d(v):
    return v if isinstance(v, Mapping) else {}

def _obs(o):
    if isinstance(o, dict): return o
    out={}
    for n in ("player","day","hour","farms","private","market","town"):
        try: out[n]=getattr(o,n)
        except Exception: pass
    return out

def _pos(v):
    if isinstance(v, Mapping): v=v.get("position",v.get("pos",[0,0]))
    try: return int(v[0]),int(v[1])
    except Exception: return (0,0)

def _kind(t):
    if not isinstance(t,Mapping): return None
    v=t.get("kind",t.get("type"))
    return str(v).upper() if v is not None else None

def _inside(tiles,p):
    x,y=p
    return 0<=y<len(tiles) and 0<=x<len(tiles[y])

def _walkable(tiles,p):
    if not _inside(tiles,p): return False
    t=tiles[p[1]][p[0]]
    return t!="LOCKED" and _kind(t)!="LOCKED"

def _neigh(tiles,p):
    x,y=p
    for a,dx,dy in DIRECTIONS:
        q=(x+dx,y+dy)
        if _walkable(tiles,q): yield a,q

def _route(tiles,start,goal):
    if start==goal: return (0,"PASS")
    q=deque([(start,0,None)]); seen={start}
    while q:
        p,d,first=q.popleft()
        for a,n in _neigh(tiles,p):
            if n in seen: continue
            seen.add(n); f=first or a
            if n==goal: return d+1,f
            q.append((n,d+1,f))
    return None

def _inventory(inv):
    return _d(inv)

def _count(tiles):
    c={"pasture":0,"cow":0,"carrot":0,"weed":0,"usable":0,"occupied":0}
    for row in tiles:
        for t in row:
            if t=="LOCKED" or _kind(t)=="LOCKED": continue
            c["usable"]+=1
            if t is not None: c["occupied"]+=1
            k=_kind(t)
            if k=="PASTURE":
                c["pasture"]+=1
                if str(_d(t).get("animal","")).upper()=="COW": c["cow"]+=1
            elif k=="PLANT" and str(_d(t).get("crop","")).upper()=="CARROT":
                c["carrot"]+=1
            elif k=="WEED":
                c["weed"]+=1
    return c

def _targets(tiles):
    out=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            k=_kind(t); td=_d(t)
            if k=="PLANT":
                if int(td.get("yield_units",td.get("yield",0)) or 0)>0:
                    out.append((0,(x,y),["HARVEST"],None))
                elif not bool(td.get("watered_today",td.get("watered",False))):
                    out.append((2,(x,y),["WATER"],None))
            elif k=="PASTURE" and td.get("animal"):
                if int(td.get("yield_units",td.get("yield",0)) or 0)>0:
                    out.append((0,(x,y),["HARVEST"],None))
                if not bool(td.get("fed_today",td.get("fed",False))):
                    out.append((1,(x,y),["FEED"],"WHEAT"))
                if not bool(td.get("cared_today",td.get("cared",False))):
                    out.append((3,(x,y),["CARE"],None))
                if bool(td.get("fertilizer_available",False)):
                    out.append((4,(x,y),["COLLECT_FERTILIZER"],None))
            elif k=="WEED":
                out.append((5,(x,y),["DIG"],None))
    return out

def _empty(tiles):
    return [(x,y) for y,row in enumerate(tiles) for x,t in enumerate(row) if t is None]

def _empty_pastures(tiles):
    out=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            if _kind(t)=="PASTURE" and not _d(t).get("animal"): out.append((x,y))
    return out

def _move_or(action,tiles,pos,target):
    r=_route(tiles,pos,target)
    if r is None: return ["PASS"]
    d,f=r
    return action if d==0 else [f]

def _unit_action(tiles,pos,inv,targets,reserved,counts,seeds):
    inv=_inventory(inv)
    if int(inv.get("COW",0) or 0)>0:
        cand=[]
        for t in _empty_pastures(tiles):
            if t in reserved: continue
            r=_route(tiles,pos,t)
            if r: cand.append((r[0],t,r[1]))
        if cand:
            cand.sort(); d,t,f=cand[0]; reserved.add(t)
            return ["PLACE","COW"] if d==0 else [f]
    if int(inv.get("WHEAT",0) or 0)>0:
        feed=[]
        for pri,t,a,req in targets:
            if req=="WHEAT" and t not in reserved:
                r=_route(tiles,pos,t)
                if r: feed.append((r[0],t,r[1]))
        if feed:
            feed.sort(); d,t,f=feed[0]; reserved.add(t)
            return ["FEED"] if d==0 else [f]
    carried=sum(int(v or 0) for k,v in inv.items() if k not in ("WHEAT","COW"))
    if carried:
        return _move_or(["DROP"],tiles,pos,FARMHOUSE)

    cand=[]
    for pri,t,a,req in targets:
        if t in reserved or req=="WHEAT": continue
        r=_route(tiles,pos,t)
        if r: cand.append((pri,r[0],t,a,r[1]))
    if cand:
        cand.sort(key=lambda z:(z[0],z[1],z[2][1],z[2][0]))
        _,d,t,a,f=cand[0]; reserved.add(t)
        return a if d==0 else [f]

    if any(req=="WHEAT" for _,_,_,req in targets):
        return _move_or(["PICKUP","WHEAT",1],tiles,pos,FARMHOUSE)
    if counts["cow"]<TARGET_COWS and _empty_pastures(tiles):
        return _move_or(["PICKUP","COW",1],tiles,pos,FARMHOUSE)
    if counts["pasture"]<TARGET_PASTURES:
        empt=_empty(tiles)
        if empt:
            empt.sort(key=lambda p:(abs(p[0]-4)+abs(p[1]-4),-p[1],-p[0]))
            return _move_or(["BUILD_PASTURE"],tiles,pos,empt[0])
    if counts["carrot"]<TARGET_CARROTS and int(seeds.get("CARROT",0) or 0)>0:
        empt=_empty(tiles)
        if empt:
            empt.sort(key=lambda p:(p[1],p[0]))
            return _move_or(["PLANT","CARROT"],tiles,pos,empt[0])
    return ["PASS"]

def _market(obs,farm,counts):
    private=_d(obs.get("private")); shed=_d(private.get("shed")); seeds=_d(private.get("seeds"))
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    money=float(farm.get("money",0) or 0); actions=[]
    liquidate=day>=29 or (day==28 and hour>=18)
    if liquidate:
        for p in SELLABLE:
            q=int(shed.get(p,0) or 0)
            if q>0:
                actions.append(["SELL",p,q])
                if len(actions)>=10: break
        return actions

    total_cows=counts["cow"]+int(shed.get("COW",0) or 0)
    if total_cows<TARGET_COWS and money>=400:
        actions.append(["BUY_ANIMAL","COW",TARGET_COWS-total_cows])
    carrot_need=max(0,TARGET_CARROTS-counts["carrot"]-int(seeds.get("CARROT",0) or 0))
    if carrot_need and money>=35:
        actions.append(["BUY_SEED","CARROT",carrot_need])
    wheat=int(shed.get("WHEAT",0) or 0); target_feed=max(4,counts["cow"]*3)
    if wheat<target_feed and money>=25*(target_feed-wheat):
        actions.append(["BUY_PRODUCT","WHEAT",target_feed-wheat])

    hands=len(farm.get("hands") or []); hires_today=int(farm.get("hires_today",0) or 0)
    backlog=len(_targets(farm.get("tiles") or [])); desired=2 if backlog>=3 else 1 if backlog>=2 else 0
    if hands<desired and hires_today<3 and money>=50:
        for _ in range(min(desired-hands,3-hires_today)): actions.append(["HIRE"])

    reserve={"WHEAT":target_feed}
    for p in SELLABLE:
        q=max(0,int(shed.get(p,0) or 0)-reserve.get(p,0))
        while q>0 and len(actions)<10:
            batch=min(q,2 if p=="FERTILIZER" else 4)
            actions.append(["SELL",p,batch]); q-=batch
        if len(actions)>=10: break
    return actions[:10]

def agent(observation:Any,configuration:Any=None)->Dict[str,Any]:
    obs=_obs(observation); player=int(obs.get("player",0) or 0); farms=obs.get("farms") or []
    if player>=len(farms): return {"farmer":["PASS"],"hands":[],"market":[]}
    farm=_d(farms[player]); tiles=farm.get("tiles") or []; hands=list(farm.get("hands") or [])
    if not tiles: return {"farmer":["PASS"],"hands":[["PASS"] for _ in hands],"market":[]}
    private=_d(obs.get("private")); inventories=list(private.get("inventories") or []); seeds=_d(private.get("seeds"))
    counts=_count(tiles); targets=_targets(tiles); reserved=set(); units=[farm.get("farmer",[0,0])]+hands; unit_actions=[]
    for i,u in enumerate(units):
        inv=inventories[i] if i<len(inventories) else {}
        unit_actions.append(_unit_action(tiles,_pos(u),inv,targets,reserved,counts,seeds))
    return {"farmer":unit_actions[0] if unit_actions else ["PASS"],"hands":unit_actions[1:],"market":_market(obs,farm,counts)}
