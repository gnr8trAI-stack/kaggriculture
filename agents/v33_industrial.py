"""V33 Industrial alpha1.

Independent four-quadrant Kaggriculture controller. V19/V32 are controls only.
Economic policy: compound productive capital, unlock all four districts while
payback remains positive, scale labour with owned capacity, dedicate SW to
livestock/feed and keep NW/NE/SE as crop districts.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (("NORTH",0,-1),("SOUTH",0,1),("WEST",-1,0),("EAST",1,0))
CROPS = ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
SELLABLE = ("MELON","STRAWBERRY","TOMATO","CARROT","WHEAT","MILK","WOOL","EGG","FERTILIZER")

_LAST_STEP = -1
_RECORDS: deque = deque(maxlen=4096)
_LAND_UNLOCK_STEPS: List[int] = []


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    out: Dict[str, Any] = {}
    for k in ("player","step","day","hour","farms","private","market","town"):
        try: out[k] = getattr(v,k)
        except Exception: pass
    return out


def _kind(tile: Any) -> str:
    if tile is None: return "EMPTY"
    if tile == "LOCKED": return "LOCKED"
    if isinstance(tile, Mapping): return str(tile.get("kind",tile.get("type","UNKNOWN"))).upper()
    return "UNKNOWN"


def _pos(v: Any) -> Position:
    if isinstance(v, Mapping): v = v.get("position",v.get("pos",[0,0]))
    try: return int(v[0]),int(v[1])
    except Exception: return (0,0)


def _inside(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    x,y=p; return 0<=y<len(tiles) and 0<=x<len(tiles[y])


def _walkable(tiles: Sequence[Sequence[Any]], p: Position) -> bool:
    return _inside(tiles,p) and _kind(tiles[p[1]][p[0]]) != "LOCKED"


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int,str]]:
    if start==goal: return (0,"PASS")
    q=deque([(start,0,None)]); seen={start}
    while q:
        p,d,first=q.popleft(); x,y=p
        for a,dx,dy in MOVES:
            n=(x+dx,y+dy)
            if n in seen or not _walkable(tiles,n): continue
            seen.add(n); f=first or a
            if n==goal: return d+1,f
            q.append((n,d+1,f))
    return None


def _nearest(tiles: Sequence[Sequence[Any]], start: Position, goals: Iterable[Position]) -> Optional[Tuple[int,Position,str]]:
    best=[]
    for g in goals:
        r=_route(tiles,start,g)
        if r is not None: best.append((r[0],g[1],g[0],g,r[1]))
    if not best: return None
    best.sort(); d,_,_,g,a=best[0]; return d,g,a


def _quadrant(size: int, p: Position) -> int:
    h=size//2; x,y=p
    return 1 if x<h and y<h else 2 if x>=h and y<h else 3 if x<h and y>=h else 4


def _shed_cells(size: int) -> Set[Position]:
    h=size//2; return {(h-1,h-1),(h,h-1),(h-1,h),(h,h)}


def _stats(tiles: Any) -> Dict[str,Any]:
    d={q:{"unlocked":0,"productive":0,"empty":0,"weeds":0,"pasture":0,"animals":0} for q in range(1,5)}
    if not isinstance(tiles,list) or not tiles: return {"districts":d,"lands":0,"productive":0,"empty":0}
    n=len(tiles)
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            k=_kind(t)
            if k=="LOCKED": continue
            q=_quadrant(n,(x,y)); z=d[q]; z["unlocked"]+=1
            if k=="EMPTY": z["empty"]+=1
            if k=="WEED": z["weeds"]+=1
            if k in {"PLANT","PASTURE","COOP"}: z["productive"]+=1
            if k=="PASTURE":
                z["pasture"]+=1
                if isinstance(t,Mapping) and t.get("animal"): z["animals"]+=1
    lands=sum(1 for q in d.values() if q["unlocked"]>4)
    return {"districts":d,"lands":lands,"productive":sum(q["productive"] for q in d.values()),"empty":sum(q["empty"] for q in d.values())}


def _crop(day:int, quadrant:int) -> str:
    # High-value crops dominate after bootstrap; Q1 retains some fast-cycle wheat.
    if day<=3: return "WHEAT"
    if day<=7: return "TOMATO" if quadrant!=1 else "CARROT"
    if day<=12: return "STRAWBERRY"
    return "MELON"


def _tile_service(tile: Any) -> Optional[List[Any]]:
    if not isinstance(tile,Mapping): return None
    k=_kind(tile)
    if k=="PLANT":
        if int(tile.get("yield_units",tile.get("yield",0)) or 0)>0: return ["HARVEST"]
        if not bool(tile.get("watered_today",tile.get("watered",False))): return ["WATER"]
    if k in {"PASTURE","COOP"} and tile.get("animal"):
        if not bool(tile.get("fed_today",tile.get("fed",False))): return ["FEED"]
        if int(tile.get("yield_units",tile.get("yield",0)) or 0)>0: return ["HARVEST"]
        if not bool(tile.get("cared_today",tile.get("cared",False))): return ["CARE"]
        if bool(tile.get("fertilizer_available",False)): return ["COLLECT_FERTILIZER"]
    if k=="WEED": return ["DIG"]
    return None


def _priority(action: List[Any]) -> int:
    return {"HARVEST":0,"FEED":0,"WATER":1,"CARE":2,"COLLECT_FERTILIZER":3,"DIG":4,"BUILD_PASTURE":5,"PLANT":6}.get(action[0],9)


def _inventory(private: Mapping[str,Any], idx:int) -> Mapping[str,Any]:
    inv=private.get("inventories",[])
    return _m(inv[idx]) if isinstance(inv,list) and idx<len(inv) else {}


def _to_shed(tiles: Sequence[Sequence[Any]], p:Position, action:List[Any]) -> List[Any]:
    sheds=_shed_cells(len(tiles))
    if p in sheds: return action
    r=_nearest(tiles,p,sheds); return [r[2]] if r else ["PASS"]


def _assign(
    tiles: Sequence[Sequence[Any]], p:Position, idx:int, day:int, private:Mapping[str,Any],
    stats:Mapping[str,Any], reserved:Set[Position], seeds:Dict[str,int]
) -> Tuple[List[Any],str]:
    n=len(tiles); inv=_inventory(private,idx); q_home=3 if (stats["lands"]>=3 and idx>=max(2, int(stats["productive"]//12))) else 0

    # Monetize carried output and place carried animals before normal work.
    if sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in set(CROPS)|{"COW"})>0:
        return _to_shed(tiles,p,["DROP"]),"drop_output"
    if int(inv.get("COW",0) or 0)>0:
        goals=[]
        for y,row in enumerate(tiles):
            for x,t in enumerate(row):
                if _quadrant(n,(x,y))==3 and isinstance(t,Mapping) and _kind(t)=="PASTURE" and not t.get("animal") and (x,y) not in reserved:
                    goals.append((x,y))
        r=_nearest(tiles,p,goals)
        if r:
            reserved.add(r[1]); return (["PLACE","COW"] if r[0]==0 else [r[2]]),"place_cow"

    tasks=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            pos=(x,y)
            if pos in reserved or _kind(t)=="LOCKED": continue
            a=_tile_service(t)
            if a is None: continue
            q=_quadrant(n,pos)
            district_penalty=0 if q_home==0 or q==q_home else 4
            r=_route(tiles,p,pos)
            if r: tasks.append((_priority(a)+district_penalty,r[0],y,x,pos,a,r[1]))
    if tasks:
        tasks.sort(); _,d,_,_,target,a,first=tasks[0]; reserved.add(target)
        return (a if d==0 else [first]),a[0].lower()

    # Build SW into a real livestock district once third land is unlocked.
    if stats["lands"]>=3 and day<=24:
        q3=stats["districts"][3]
        pasture_target=min(12, max(4, stats["productive"]//8))
        if q3["pasture"]<pasture_target:
            goals=[]
            sheds=_shed_cells(n)
            for y,row in enumerate(tiles):
                for x,t in enumerate(row):
                    pos=(x,y)
                    if _quadrant(n,pos)==3 and t is None and pos not in sheds and pos not in reserved: goals.append(pos)
            r=_nearest(tiles,p,goals)
            if r:
                reserved.add(r[1]); return (["BUILD_PASTURE"] if r[0]==0 else [r[2]]),"build_pasture"

    # Fill all crop districts, including SE. No deliberate idle unlocked acreage.
    goals=[]
    sheds=_shed_cells(n)
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            pos=(x,y); q=_quadrant(n,pos)
            if t is None and pos not in sheds and pos not in reserved and q in {1,2,4}:
                crop=_crop(day,q)
                if seeds.get(crop,0)>0:
                    r=_route(tiles,p,pos)
                    if r: goals.append((r[0],y,x,pos,crop,r[1]))
    if goals:
        goals.sort(); d,_,_,target,crop,first=goals[0]; reserved.add(target)
        if d==0:
            seeds[crop]-=1; return ["PLANT",crop],"plant_"+crop.lower()
        return [first],"move_plant"

    return ["PASS"],"idle"


def _market(obs:Mapping[str,Any], farm:Mapping[str,Any], stats:Mapping[str,Any], day:int, hour:int) -> Tuple[List[List[Any]],Dict[str,int]]:
    private=_m(obs.get("private")); shed=_m(private.get("shed")); money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    orders:List[List[Any]]=[]; meta={"land":0,"hire":0,"animals":0,"seed_spend_proxy":0,"feed":0,"sell_qty":0}
    liquidate=day>=28

    # Convert output to cash continuously. Keep a small wheat feed reserve if livestock exists.
    animal_count=stats["districts"][3]["animals"]
    for product in SELLABLE:
        qty=int(shed.get(product,0) or 0)
        keep=(animal_count*3 if product=="WHEAT" and not liquidate else 0)
        sell=max(0,qty-keep)
        if sell>0 and (liquidate or sell>=4):
            orders.append(["SELL",product,sell]); meta["sell_qty"]+=sell
            if len(orders)>=10: return orders,meta

    # Remaining-horizon capital schedule. Spend aggressively while enough cycles remain.
    lands=int(stats["lands"])
    land_cost=(1000,2000,3000,4000)[min(lands,3)]
    horizon=max(0,30-day)
    land_ok=(lands<4 and horizon>=10 and ((lands==1 and day>=3) or (lands==2 and day>=6) or (lands==3 and day>=9)))
    operating=700 + 120*len(hands) + 80*animal_count
    if land_ok and money>=land_cost+operating and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"]=1; money-=land_cost

    # Labour scales with owned capacity rather than a tiny static ceiling.
    unlocked=sum(v["unlocked"] for v in stats["districts"].values())
    desired_hands=min(16,max(3,(unlocked-4)//7))
    hires=min(2,max(0,desired_hands-len(hands)))
    for _ in range(hires):
        if money<900 or len(orders)>=10: break
        orders.append(["HIRE"]); meta["hire"]+=1; money-=500

    # Industrial livestock: populate SW pasture capacity to 10 cows while horizon supports payback.
    q3=stats["districts"][3]
    cow_total=q3["animals"]+int(shed.get("COW",0) or 0)
    if lands>=3 and day<=22 and q3["pasture"]>cow_total and money>=1200 and len(orders)<10:
        buy=min(2,q3["pasture"]-cow_total,10-cow_total)
        if buy>0:
            orders.append(["BUY_ANIMAL","COW",buy]); meta["animals"]+=buy; money-=400*buy

    wheat=int(shed.get("WHEAT",0) or 0)
    feed_need=max(0,animal_count*4-wheat)
    if animal_count and feed_need and money>=500 and len(orders)<10:
        orders.append(["BUY_PRODUCT","WHEAT",feed_need]); meta["feed"]+=feed_need

    # Seed the crop districts for sustained full-map utilization. Premium crop mix changes with phase.
    crop=_crop(day,4 if lands>=4 else 2 if lands>=2 else 1)
    seeds=_m(private.get("seeds")); have=int(seeds.get(crop,0) or 0)
    empty_crop=sum(stats["districts"][q]["empty"] for q in (1,2,4))
    target=min(28,max(6,empty_crop+len(hands)//2))
    need=max(0,target-have)
    if not liquidate and need>0 and money>=400 and len(orders)<10:
        orders.append(["BUY_SEED",crop,need]); meta["seed_spend_proxy"]+=need

    return orders[:10],meta


def reset_state() -> None:
    global _LAST_STEP,_LAND_UNLOCK_STEPS
    _LAST_STEP=-1; _LAND_UNLOCK_STEPS=[]; _RECORDS.clear()


def reset_telemetry() -> None: reset_state()


def get_telemetry(clear:bool=False):
    out=list(_RECORDS)
    if clear: _RECORDS.clear()
    return out


def agent(observation:Any, configuration:Any=None) -> Dict[str,Any]:
    global _LAST_STEP,_LAND_UNLOCK_STEPS
    obs=_obs(observation); player=int(obs.get("player",0)); farms=obs.get("farms",[])
    if player>=len(farms): return {"farmer":["PASS"],"hands":[],"market":[]}
    farm=_m(farms[player]); tiles=farm.get("tiles") or []; hands=list(farm.get("hands") or [])
    out={"farmer":["PASS"],"hands":[["PASS"] for _ in hands],"market":[]}
    if not isinstance(tiles,list) or not tiles: return out
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); step=int(obs.get("step",day*24+hour) or 0)
    st=_stats(tiles)
    if len(_LAND_UNLOCK_STEPS)<st["lands"]: _LAND_UNLOCK_STEPS.extend([step]*(st["lands"]-len(_LAND_UNLOCK_STEPS)))
    private=_m(obs.get("private")); rawseeds=_m(private.get("seeds")); seeds={c:int(rawseeds.get(c,0) or 0) for c in CROPS}
    reserved:Set[Position]=set(); units=[_pos(farm.get("farmer",[0,0]))]+[_pos(h) for h in hands]; labels=[]
    for idx,p in enumerate(units):
        a,label=_assign(tiles,p,idx,day,private,st,reserved,seeds); labels.append(label)
        if idx==0: out["farmer"]=a
        else: out["hands"][idx-1]=a
    market,meta=_market(obs,farm,st,day,hour); out["market"]=market
    if step!=_LAST_STEP:
        _LAST_STEP=step
        d=st["districts"]
        _RECORDS.append({"step":step,"day":day,"hour":hour,"money":float(farm.get("money",0) or 0),"lands":st["lands"],"land_unlock_steps":list(_LAND_UNLOCK_STEPS),"productive":st["productive"],"empty":st["empty"],"hands":len(hands),"q1":dict(d[1]),"q2":dict(d[2]),"q3":dict(d[3]),"q4":dict(d[4]),"unit_actions":labels,"market":meta})
    return out
