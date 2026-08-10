"""V22 frontier-clone challenger.

Goal
----
Reproduce the dominant 175k-192k public-replay frontier before attempting a
>200k mutation.  The policy is derived from the top-50 replay cohort:
- 3 bought quadrants by day 10 (two BUY_LAND actions total),
- 14 pastures with exactly 8 cows + 6 sheep by day 11,
- labour ramp 4 -> 6 -> 8 -> 10 -> 12 hands,
- crop portfolio transitions from wheat/melon into ~40 strawberries,
- late day-26 wheat replant for feed/liquidation,
- continuous animal feed/care/harvest/fertilizer collection,
- selective fertilizer use and hard terminal liquidation.

This is a challenger, not a champion.  It deliberately reuses the proven V15
V12 crop routing/watering/harvest engine, but replaces its portfolio target,
labour, land, livestock and market allocation with replay-frontier targets.
"""
from __future__ import annotations

from collections import Counter, deque
from math import ceil
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from agents import v15_champion as _v15

Position = Tuple[int, int]
MOVES: Sequence[Tuple[str, int, int]] = (
    ("NORTH", 0, -1), ("SOUTH", 0, 1), ("WEST", -1, 0), ("EAST", 1, 0)
)
SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)
ANIMAL_COST = {"COW": 400, "SHEEP": 500}
LAND_COSTS = {1: 1000, 2: 2000, 3: 4000}

# Median day-end state of the top-50 frontier trajectories.  These are targets,
# not brittle action scripts: the planner chases deficits while reacting to the
# actual board and RNG.
PROFILE: Dict[int, Dict[str, int]] = {
    0:{"hands":4,"land":1,"cow":3,"sheep":1,"WHEAT":10,"STRAWBERRY":0,"MELON":7},
    1:{"hands":5,"land":1,"cow":3,"sheep":1,"WHEAT":11,"STRAWBERRY":0,"MELON":7},
    2:{"hands":5,"land":1,"cow":3,"sheep":1,"WHEAT":11,"STRAWBERRY":0,"MELON":8},
    3:{"hands":5,"land":1,"cow":3,"sheep":1,"WHEAT":11,"STRAWBERRY":0,"MELON":8},
    4:{"hands":6,"land":1,"cow":3,"sheep":1,"WHEAT":7,"STRAWBERRY":2,"MELON":10},
    5:{"hands":6,"land":1,"cow":4,"sheep":2,"WHEAT":6,"STRAWBERRY":2,"MELON":10},
    6:{"hands":6,"land":1,"cow":4,"sheep":2,"WHEAT":6,"STRAWBERRY":2,"MELON":10},
    7:{"hands":8,"land":2,"cow":5,"sheep":2,"WHEAT":10,"STRAWBERRY":6,"MELON":11},
    8:{"hands":10,"land":2,"cow":5,"sheep":6,"WHEAT":7,"STRAWBERRY":12,"MELON":11},
    9:{"hands":11,"land":2,"cow":5,"sheep":6,"WHEAT":7,"STRAWBERRY":17,"MELON":11},
    10:{"hands":12,"land":3,"cow":6,"sheep":6,"WHEAT":8,"STRAWBERRY":21,"MELON":4},
    11:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":6,"STRAWBERRY":27,"MELON":6},
    12:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":4,"STRAWBERRY":33,"MELON":6},
    13:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":4,"STRAWBERRY":38,"MELON":9},
    14:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":4,"STRAWBERRY":40,"MELON":8},
    15:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":3,"STRAWBERRY":40,"MELON":10},
    16:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":4,"STRAWBERRY":40,"MELON":10},
    17:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":5,"STRAWBERRY":40,"MELON":9},
    18:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":4,"STRAWBERRY":40,"MELON":9},
    19:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":3,"STRAWBERRY":40,"MELON":9},
    20:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":1,"STRAWBERRY":40,"MELON":9},
    21:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":0,"STRAWBERRY":38,"MELON":8},
    22:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":0,"STRAWBERRY":38,"MELON":7},
    23:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":0,"STRAWBERRY":38,"MELON":6},
    24:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":0,"STRAWBERRY":34,"MELON":5},
    25:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":0,"STRAWBERRY":28,"MELON":3},
    26:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":30,"STRAWBERRY":22,"MELON":2},
    27:{"hands":12,"land":3,"cow":8,"sheep":6,"WHEAT":31,"STRAWBERRY":18,"MELON":0},
    28:{"hands":11,"land":3,"cow":8,"sheep":6,"WHEAT":24,"STRAWBERRY":12,"MELON":0},
    29:{"hands":12,"land":3,"cow":8,"sheep":5,"WHEAT":1,"STRAWBERRY":6,"MELON":0},
}

FINAL_COWS = 8
FINAL_SHEEP = 6
FINAL_PASTURES = 14
MAX_HANDS = 12

_LAST_STEP = -1
_RECORDS = deque(maxlen=4096)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        k: getattr(value, k)
        for k in ("player", "step", "day", "hour", "farms", "private", "market", "town")
        if hasattr(value, k)
    }


def _kind(tile: Any) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, Mapping):
        return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _pos(value: Any) -> Position:
    if isinstance(value, Mapping):
        value = value.get("position", value.get("pos", [0, 0]))
    try:
        return int(value[0]), int(value[1])
    except Exception:
        return (0, 0)


def _inside(tiles: Sequence[Sequence[Any]], pos: Position) -> bool:
    x, y = pos
    return 0 <= y < len(tiles) and 0 <= x < len(tiles[y])


def _route(tiles: Sequence[Sequence[Any]], start: Position, goal: Position) -> Optional[Tuple[int, str]]:
    if start == goal:
        return (0, "PASS")
    queue = deque([(start, 0, None)])
    seen = {start}
    while queue:
        (x, y), distance, first = queue.popleft()
        for action, dx, dy in MOVES:
            nxt = (x + dx, y + dy)
            if nxt in seen or not _inside(tiles, nxt):
                continue
            seen.add(nxt)
            initial = first or action
            if nxt == goal:
                return (distance + 1, initial)
            queue.append((nxt, distance + 1, initial))
    return None


def _nearest_route(
    tiles: Sequence[Sequence[Any]], start: Position, goals: Sequence[Position]
) -> Optional[Tuple[int, Position, str]]:
    candidates=[]
    for goal in goals:
        route=_route(tiles,start,goal)
        if route is not None:
            candidates.append((route[0],goal[1],goal[0],goal,route[1]))
    if not candidates:
        return None
    candidates.sort()
    d,_,_,goal,first=candidates[0]
    return d,goal,first


def _shed_cells(size: int) -> Tuple[Position, ...]:
    half=size//2
    return ((half-1,half-1),(half,half-1),(half-1,half),(half,half))


def _to_shed(tiles: Sequence[Sequence[Any]], position: Position, at_shed_action: List[Any]) -> List[Any]:
    sheds=_shed_cells(len(tiles))
    if position in sheds:
        return at_shed_action
    route=_nearest_route(tiles,position,sheds)
    return [route[2]] if route is not None else ["PASS"]


def _go(tiles: Sequence[Sequence[Any]], position: Position, target: Position, action: List[Any]) -> List[Any]:
    if position==target:
        return action
    route=_route(tiles,position,target)
    return [route[1]] if route is not None else ["PASS"]


def _inventory_total(inv: Mapping[str, Any]) -> int:
    return sum(max(0,int(v or 0)) for v in inv.values())


def _profile(day: int) -> Dict[str,int]:
    return PROFILE[max(0,min(29,int(day)))]


def _crop_counts(tiles: Any) -> Counter:
    c=Counter()
    if not isinstance(tiles,list): return c
    for row in tiles:
        if not isinstance(row,list): continue
        for tile in row:
            if isinstance(tile,Mapping) and _kind(tile)=="PLANT":
                crop=str(tile.get("crop","")).upper()
                if crop: c[crop]+=1
    return c


def _frontier_choose_crop(obs: Mapping[str,Any], farm: Mapping[str,Any]):
    day=int(obs.get("day",0) or 0)
    if day>=28:
        return None, {"WHEAT":0.0,"STRAWBERRY":0.0,"MELON":0.0}
    target=_profile(day)
    current=_crop_counts(farm.get("tiles",[]))
    scores={}
    for crop in ("WHEAT","STRAWBERRY","MELON"):
        wanted=int(target[crop]); deficit=max(0,wanted-int(current[crop]))
        scores[crop]=deficit/max(1,wanted)
    if day>=26 and current["WHEAT"] < target["WHEAT"]:
        return "WHEAT",scores
    ranked=sorted(((score,crop) for crop,score in scores.items() if score>0),reverse=True)
    return (ranked[0][1] if ranked else None),scores


_V12 = _v15._v12_agent
_V12G = _V12.__globals__
_V12G["MAX_HANDS"] = MAX_HANDS
_V12G["choose_crop"] = _frontier_choose_crop
_ORIGINAL_V12_TILE_TASK = _V12G.get("_tile_task")


def _frontier_tile_task(tile: Any, day: int):
    if _kind(tile)=="WEED" and day>=26:
        return None
    return _ORIGINAL_V12_TILE_TASK(tile,day) if _ORIGINAL_V12_TILE_TASK else None


_V12G["_tile_task"] = _frontier_tile_task


def _pastures(tiles: Any):
    out=[]
    if not isinstance(tiles,list): return out
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,tile in enumerate(row):
            if isinstance(tile,Mapping) and _kind(tile)=="PASTURE":
                out.append(((x,y),tile))
    return out


def _active_animals(tiles: Any):
    return [(p,t) for p,t in _pastures(tiles) if str(t.get("animal","")).upper() in {"COW","SHEEP"}]


def _owned_animals(obs: Mapping[str,Any], farm: Mapping[str,Any]) -> Counter:
    c=Counter(str(t.get("animal","")).upper() for _,t in _active_animals(farm.get("tiles",[])))
    private=_m(obs.get("private")); shed=_m(private.get("shed"))
    for species in ("COW","SHEEP"):
        c[species]+=int(shed.get(species,0) or 0)
    invs=private.get("inventories",[])
    if isinstance(invs,list):
        for inv in invs:
            mm=_m(inv)
            for species in ("COW","SHEEP"):
                c[species]+=int(mm.get(species,0) or 0)
    return c


def _pasture_slots(tiles: Any) -> List[Position]:
    if not isinstance(tiles,list) or not tiles: return []
    sheds=set(_shed_cells(len(tiles))); out=[]
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,tile in enumerate(row):
            if tile=="LOCKED" or _kind(tile)=="LOCKED" or (x,y) in sheds:
                continue
            distance=min(abs(x-sx)+abs(y-sy) for sx,sy in sheds)
            out.append((distance,y,x,(x,y)))
    out.sort()
    return [p for _,_,_,p in out]


def _reserved_pasture_count(tiles: Any) -> int:
    usable=0
    if isinstance(tiles,list):
        for row in tiles:
            if not isinstance(row,list): continue
            for tile in row:
                if tile!="LOCKED" and _kind(tile)!="LOCKED": usable+=1
    return 4 if usable<=25 else 11 if usable<=50 else 14


def _frontier_empties(tiles: Sequence[Sequence[Any]]) -> List[Position]:
    reserve=set(_pasture_slots(tiles)[:_reserved_pasture_count(tiles)])
    return [(x,y) for y,row in enumerate(tiles) for x,tile in enumerate(row) if tile is None and (x,y) not in reserve]


def _pasture_build_candidates(tiles: Any, target_structures: int=FINAL_PASTURES) -> List[Position]:
    slots=_pasture_slots(tiles)[:max(0,target_structures)]
    out=[]
    for x,y in slots:
        try: tile=tiles[y][x]
        except Exception: continue
        if tile is None: out.append((x,y))
    if not out:
        sheds=set(_shed_cells(len(tiles))) if isinstance(tiles,list) and tiles else set()
        for y,row in enumerate(tiles if isinstance(tiles,list) else []):
            for x,tile in enumerate(row if isinstance(row,list) else []):
                if tile is None and (x,y) not in sheds: out.append((x,y))
    return out


_V12G["_empties"] = _frontier_empties


def _fertilize_targets(tiles: Any, day: int) -> List[Position]:
    targets=[]
    if not isinstance(tiles,list): return targets
    priority={"MELON":0,"WHEAT":1,"STRAWBERRY":2}
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,tile in enumerate(row):
            if not isinstance(tile,Mapping) or _kind(tile)!="PLANT": continue
            crop=str(tile.get("crop","")).upper()
            if crop not in priority: continue
            planted=int(tile.get("planted_day",day) if tile.get("planted_day") is not None else day)
            age=day-planted
            until=int(tile.get("fertilized_until_day",-1) or -1)
            if until>=day: continue
            useful=(crop=="MELON" and 4<=age<=8) or (crop=="WHEAT" and 0<=age<=2)
            useful=useful or (crop=="STRAWBERRY" and 6<=age<=10)
            if useful:
                targets.append((priority[crop],y,x,(x,y)))
    targets.sort()
    return [p for *_,p in targets]


def _livestock_crew_size(active_count: int, structure_count: int, unit_count: int) -> int:
    if max(active_count,structure_count)==0: return 0
    desired=max(1,ceil(max(active_count,structure_count)/3))
    crop_preserving_capacity=max(1,unit_count-2)
    return min(5,crop_preserving_capacity,desired)


def _livestock_action(
    obs: Mapping[str,Any], farm: Mapping[str,Any], unit_index: int,
    reserved: Set[Position], target_structures: int,
) -> Tuple[Optional[List[Any]],str]:
    tiles=farm.get("tiles") or []
    hands=list(farm.get("hands") or [])
    positions=[_pos(farm.get("farmer",[0,0]))]+[_pos(h) for h in hands]
    if unit_index>=len(positions) or not isinstance(tiles,list) or not tiles:
        return None,"no_unit"
    position=positions[unit_index]
    private=_m(obs.get("private")); shed=_m(private.get("shed"))
    invs=private.get("inventories",[])
    inv=_m(invs[unit_index]) if isinstance(invs,list) and unit_index<len(invs) else {}
    day=int(obs.get("day",0) or 0)
    active=_active_animals(tiles)
    pastures=_pastures(tiles)
    empty=[p for p,t in pastures if not t.get("animal")]

    for species in ("COW","SHEEP"):
        if int(inv.get(species,0) or 0)>0 and empty:
            choices=[p for p in empty if p not in reserved]
            route=_nearest_route(tiles,position,choices)
            if route is not None:
                _,target,_=route; reserved.add(target)
                return _go(tiles,position,target,["PLACE",species]),"place_"+species.lower()

    if int(inv.get("WHEAT",0) or 0)>0:
        goals=[p for p,t in active if not bool(t.get("fed_today",False)) and p not in reserved]
        route=_nearest_route(tiles,position,goals)
        if route is not None:
            _,target,_=route; reserved.add(target)
            return _go(tiles,position,target,["FEED"]),"feed"

    if int(inv.get("FERTILIZER",0) or 0)>0 and day<27:
        goals=[p for p in _fertilize_targets(tiles,day) if p not in reserved]
        route=_nearest_route(tiles,position,goals)
        if route is not None:
            _,target,_=route; reserved.add(target)
            return _go(tiles,position,target,["FERTILIZE"]),"fertilize"

    output_load=sum(int(v or 0) for k,v in inv.items() if str(k).upper() not in {"WHEAT","COW","SHEEP"})
    if output_load>0:
        return _to_shed(tiles,position,["DROP"]),"return_output"

    unfed=[p for p,t in active if not bool(t.get("fed_today",False)) and p not in reserved]
    if unfed:
        wheat=int(shed.get("WHEAT",0) or 0)
        if wheat>0:
            return _to_shed(tiles,position,["PICKUP","WHEAT",min(6,wheat)]),"pickup_feed"

    harvest=[p for p,t in active if int(t.get("yield_units",0) or 0)>0 and p not in reserved]
    route=_nearest_route(tiles,position,harvest)
    if route is not None:
        _,target,_=route; reserved.add(target)
        return _go(tiles,position,target,["HARVEST"]),"animal_harvest"

    uncared=[p for p,t in active if not bool(t.get("cared_today",False)) and p not in reserved]
    route=_nearest_route(tiles,position,uncared)
    if route is not None:
        _,target,_=route; reserved.add(target)
        return _go(tiles,position,target,["CARE"]),"care"

    fert=[p for p,t in active if bool(t.get("fertilizer_available",False)) and p not in reserved]
    route=_nearest_route(tiles,position,fert)
    if route is not None:
        _,target,_=route; reserved.add(target)
        return _go(tiles,position,target,["COLLECT_FERTILIZER"]),"collect_fertilizer"

    if empty:
        for species in ("COW","SHEEP"):
            if int(shed.get(species,0) or 0)>0:
                return _to_shed(tiles,position,["PICKUP",species,1]),"pickup_"+species.lower()

    if len(pastures)<target_structures:
        goals=[p for p in _pasture_build_candidates(tiles,target_structures) if p not in reserved]
        route=_nearest_route(tiles,position,goals)
        if route is not None:
            _,target,_=route; reserved.add(target)
            return _go(tiles,position,target,["BUILD_PASTURE"]),"build_pasture"

    return None,"idle"


def _shed_total(obs: Mapping[str,Any]) -> int:
    return _inventory_total(_m(_m(obs.get("private")).get("shed")))


def _market_orders(obs: Mapping[str,Any], farm: Mapping[str,Any], base_market: List[List[Any]]) -> List[List[Any]]:
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    profile=_profile(day); private=_m(obs.get("private")); shed=_m(private.get("shed")); seeds=_m(private.get("seeds"))
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    unlocked=list(farm.get("unlocked_quadrants") or ["NW"])
    tiles=farm.get("tiles") or []
    owned=_owned_animals(obs,farm); active=_active_animals(tiles)
    invs=private.get("inventories",[])

    sells=[]
    for order in base_market:
        if isinstance(order,list) and order[:1]==["SELL"]:
            sells.append(order)
    orders=sells[:]

    def add(order: List[Any], reserve: int=10):
        if len(orders)<reserve:
            orders.append(order); return True
        return False

    liquidate=day>=29 or (day==28 and hour>=12)

    if not liquidate:
        carried_wheat=0
        if isinstance(invs,list):
            carried_wheat=sum(int(_m(inv).get("WHEAT",0) or 0) for inv in invs)
        active_count=len(active)
        desired_wheat=max(8,active_count*2)
        available_wheat=int(shed.get("WHEAT",0) or 0)+carried_wheat
        if active_count and available_wheat<desired_wheat:
            buy=min(8,desired_wheat-available_wheat)
            add(["BUY_PRODUCT","WHEAT",buy])

        target_land=int(profile["land"])
        if len(unlocked)<target_land:
            cost=LAND_COSTS.get(len(unlocked),1000)
            if money>=cost+100:
                add(["BUY_LAND"])

        for species,key in (("COW","cow"),("SHEEP","sheep")):
            missing=max(0,int(profile[key])-int(owned[species]))
            if missing>0 and money>=ANIMAL_COST[species]+100:
                add(["BUY_ANIMAL",species,min(missing,3)])

        crop,_=_frontier_choose_crop(obs,farm)
        if crop:
            current=_crop_counts(tiles)[crop]
            deficit=max(0,int(profile[crop])-int(current)-int(seeds.get(crop,0) or 0))
            if deficit>0:
                seed_cost={"WHEAT":10,"STRAWBERRY":100,"MELON":80}[crop]
                affordable=max(0,int(money//seed_cost))
                buy=min(deficit,affordable,16)
                if buy>0: add(["BUY_SEED",crop,buy])

        missing_hands=max(0,int(profile["hands"])-len(hands))
        for _ in range(missing_hands):
            if not add(["HIRE"]): break

    if liquidate:
        orders=[]
        for item in SELLABLE:
            qty=int(shed.get(item,0) or 0)
            if qty>0 and len(orders)<10:
                orders.append(["SELL",item,qty])
    return orders[:10]


def reset_state() -> None:
    global _LAST_STEP
    _LAST_STEP=-1
    _RECORDS.clear()
    if callable(getattr(_v15,"reset_state",None)):
        _v15.reset_state()
    _V12G["MAX_HANDS"]=MAX_HANDS
    _V12G["choose_crop"]=_frontier_choose_crop
    _V12G["_tile_task"]=_frontier_tile_task
    _V12G["_empties"]=_frontier_empties


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool=False):
    rows=list(_RECORDS)
    if clear: _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any=None) -> Dict[str,Any]:
    global _LAST_STEP
    obs=_obs(observation)
    player=int(obs.get("player",0) or 0); farms=obs.get("farms",[])
    if not isinstance(farms,list) or player>=len(farms):
        return {"farmer":["PASS"],"hands":[],"market":[]}
    farm=_m(farms[player]); day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    step=int(obs.get("step",day*24+hour) or 0)
    if _LAST_STEP>=0 and step<=_LAST_STEP: reset_state()
    _LAST_STEP=step

    base=dict(_V12(obs,configuration))
    hands=list(farm.get("hands") or []); unit_count=1+len(hands)
    actions=[list(base.get("farmer",["PASS"]))]+[list(a) for a in base.get("hands",[])]
    while len(actions)<unit_count: actions.append(["PASS"])
    if len(actions)>unit_count: actions=actions[:unit_count]

    profile=_profile(day); target_structures=min(FINAL_PASTURES,int(profile["cow"])+int(profile["sheep"]))
    active_count=len(_active_animals(farm.get("tiles",[])))
    crew=_livestock_crew_size(active_count,max(len(_pastures(farm.get("tiles",[]))),target_structures),unit_count)
    reserved:set[Position]=set(); stages=[]
    for unit_index in range(max(0,unit_count-crew),unit_count):
        override,stage=_livestock_action(obs,farm,unit_index,reserved,target_structures)
        if override is not None: actions[unit_index]=override
        stages.append(stage)

    legal={
        "farmer":actions[0],
        "hands":actions[1:],
        "market":_market_orders(obs,farm,list(base.get("market",[]))),
    }
    counts=_crop_counts(farm.get("tiles",[])); owned=_owned_animals(obs,farm)
    _RECORDS.append({
        "step":step,"day":day,"hour":hour,"money":float(farm.get("money",0) or 0),
        "hands":len(hands),"land":len(farm.get("unlocked_quadrants") or ["NW"]),
        "cows":int(owned["COW"]),"sheep":int(owned["SHEEP"]),
        "pastures":len(_pastures(farm.get("tiles",[]))),"active_animals":active_count,
        "crop_wheat":int(counts["WHEAT"]),"crop_strawberry":int(counts["STRAWBERRY"]),"crop_melon":int(counts["MELON"]),
        "target":dict(profile),"livestock_crew":crew,"livestock_stages":stages,
        "shed_total":_shed_total(obs),"market_orders":legal["market"],
    })
    return legal
