"""V23 direct donor clock-policy challenger.

Source policy: the 181,274-coin public replay 90142380, seat 1, supplied in the
analysis corpus. Two independent 176k/178k public replays used the same action
schedule on 680/720 turns; remaining differences were mostly weed repairs and
SELL-order permutations. This agent executes the donor schedule directly and
only repairs obviously impossible local actions.

No opponent-private state is used.
"""
from __future__ import annotations
import base64, json, zlib
from collections import Counter, deque
from typing import Any, Dict, Mapping, List

_PAYLOAD='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'
_SCHEDULE=json.loads(zlib.decompress(base64.b64decode(_PAYLOAD)).decode("utf-8"))
_SHED_POS={(4,4),(5,4),(4,5),(5,5)}
_LAST_STEP=-1
_TELEMETRY=deque(maxlen=4096)

def _m(v: Any) -> Mapping[str,Any]:
    return v if isinstance(v,Mapping) else {}

def _obs(v: Any) -> Dict[str,Any]:
    if isinstance(v,dict): return v
    return {k:getattr(v,k) for k in ("player","step","day","hour","farms","private","market","town") if hasattr(v,k)}

def _kind(tile: Any) -> str:
    if tile is None: return "EMPTY"
    if tile=="LOCKED": return "LOCKED"
    return str(_m(tile).get("kind",_m(tile).get("type","UNKNOWN"))).upper()

def _pos(v: Any):
    if isinstance(v,Mapping): v=v.get("position",v.get("pos",[0,0]))
    try: return int(v[0]),int(v[1])
    except Exception: return (0,0)

def _tile(tiles,pos):
    x,y=pos
    try: return tiles[y][x]
    except Exception: return None

def _repair_local(action: List[Any], pos, tile, inv: Mapping[str,Any]):
    if not isinstance(action,list) or not action: return ["PASS"],"bad_action"
    op=str(action[0]).upper()
    if op in {"NORTH","SOUTH","EAST","WEST","PASS"}: return action,"scheduled"
    kind=_kind(tile)
    if kind=="WEED" and op!="DIG": return ["DIG"],"weed_repair"
    if op in {"BUILD_PASTURE","BUILD_COOP"}: return (action,"scheduled") if tile is None else (["PASS"],"build_blocked")
    if op=="DIG": return (action,"scheduled") if kind not in {"EMPTY","LOCKED"} else (["PASS"],"dig_empty")
    if op=="PLANT": return (action,"scheduled") if tile is None else (["PASS"],"plant_blocked")
    if op=="WATER": return (action,"scheduled") if kind=="PLANT" and not bool(_m(tile).get("watered_today",False)) else (["PASS"],"water_noop")
    if op=="HARVEST": return (action,"scheduled") if kind in {"PLANT","PASTURE","COOP"} and int(_m(tile).get("yield_units",0) or 0)>0 else (["PASS"],"harvest_noop")
    if op=="FERTILIZE": return (action,"scheduled") if kind=="PLANT" and int(inv.get("FERTILIZER",0) or 0)>0 else (["PASS"],"fert_noop")
    if op=="FEED":
        animal=str(_m(tile).get("animal","")).upper(); ok=kind in {"PASTURE","COOP"} and animal and not bool(_m(tile).get("fed_today",False)) and int(inv.get("WHEAT",0) or 0)>0
        return (action,"scheduled") if ok else (["PASS"],"feed_noop")
    if op=="CARE":
        animal=str(_m(tile).get("animal","")).upper(); ok=kind in {"PASTURE","COOP"} and animal and not bool(_m(tile).get("cared_today",False))
        return (action,"scheduled") if ok else (["PASS"],"care_noop")
    if op=="COLLECT_FERTILIZER":
        animal=str(_m(tile).get("animal","")).upper(); ok=kind in {"PASTURE","COOP"} and animal and bool(_m(tile).get("fertilizer_available",False))
        return (action,"scheduled") if ok else (["PASS"],"collect_noop")
    if op=="PLACE":
        item=str(action[1]).upper() if len(action)>1 else ""
        if item in {"COW","SHEEP"}:
            ok=kind=="PASTURE" and not _m(tile).get("animal") and int(inv.get(item,0) or 0)>0
            return (action,"scheduled") if ok else (["PASS"],"place_noop")
        if item=="GOOSE":
            ok=kind=="COOP" and not _m(tile).get("animal") and int(inv.get(item,0) or 0)>0
            return (action,"scheduled") if ok else (["PASS"],"place_noop")
        return (action,"scheduled") if pos in _SHED_POS else (["PASS"],"place_not_shed")
    if op=="PICKUP": return (action,"scheduled") if pos in _SHED_POS else (["PASS"],"pickup_not_shed")
    if op=="DROP": return (action,"scheduled") if pos in _SHED_POS else (["PASS"],"drop_not_shed")
    return action,"scheduled"

def _repair_market(orders, obs):
    shed=_m(_m(obs.get("private")).get("shed")); out=[]; changes=0
    for raw in orders if isinstance(orders,list) else []:
        if not isinstance(raw,list) or not raw: continue
        order=list(raw); op=str(order[0]).upper()
        if op=="SELL" and len(order)>=3:
            item=str(order[1]).upper(); have=max(0,int(shed.get(item,0) or 0)); want=max(0,int(order[2] or 0)); qty=min(have,want)
            if qty<=0: changes+=1; continue
            if qty!=want: changes+=1
            order=["SELL",item,qty]
        out.append(order)
        if len(out)>=10: break
    return out,changes

def _state_summary(farm):
    crops=Counter(); animals=Counter(); pastures=0; weeds=0
    for row in farm.get("tiles") or []:
        if not isinstance(row,list): continue
        for t in row:
            k=_kind(t)
            if k=="PLANT": crops[str(_m(t).get("crop","")).upper()]+=1
            elif k=="PASTURE":
                pastures+=1; a=str(_m(t).get("animal","")).upper()
                if a: animals[a]+=1
            elif k=="WEED": weeds+=1
    return crops,animals,pastures,weeds

def reset_state():
    global _LAST_STEP
    _LAST_STEP=-1; _TELEMETRY.clear()

def get_telemetry(clear=False):
    rows=list(_TELEMETRY)
    if clear: _TELEMETRY.clear()
    return rows

def agent(observation: Any, configuration: Any=None):
    global _LAST_STEP
    obs=_obs(observation); step=int(obs.get("step",0) or 0)
    if _LAST_STEP>=0 and step<=_LAST_STEP: reset_state()
    _LAST_STEP=step
    player=int(obs.get("player",0) or 0); farms=obs.get("farms") or []
    if not isinstance(farms,list) or player>=len(farms): return {"farmer":["PASS"],"hands":[],"market":[]}
    farm=_m(farms[player]); invs=_m(obs.get("private")).get("inventories") or []
    planned=_SCHEDULE[min(max(step,0),len(_SCHEDULE)-1)]
    positions=[_pos(farm.get("farmer",[0,0]))]+[_pos(x) for x in farm.get("hands") or []]
    planned_actions=[list(planned.get("farmer",["PASS"]))]+[list(x) for x in planned.get("hands",[])]
    actions=[]; repairs=Counter()
    for i,pos in enumerate(positions):
        raw=planned_actions[i] if i<len(planned_actions) else ["PASS"]
        inv=_m(invs[i]) if isinstance(invs,list) and i<len(invs) else {}
        fixed,reason=_repair_local(raw,pos,_tile(farm.get("tiles") or [],pos),inv); actions.append(fixed); repairs[reason]+=1
    market,market_repairs=_repair_market(planned.get("market",[]),obs)
    crops,animals,pastures,weeds=_state_summary(farm)
    _TELEMETRY.append({"step":step,"day":int(obs.get("day",0) or 0),"hour":int(obs.get("hour",0) or 0),"money":float(farm.get("money",0) or 0),"hands":len(farm.get("hands") or []),"land":len(farm.get("unlocked_quadrants") or ["NW"]),"pastures":pastures,"cows":int(animals["COW"]),"sheep":int(animals["SHEEP"]),"weeds":weeds,"strawberries":int(crops["STRAWBERRY"]),"wheat":int(crops["WHEAT"]),"melon":int(crops["MELON"]),"local_repairs":sum(v for k,v in repairs.items() if k!="scheduled"),"repair_reasons":dict(repairs),"market_repairs":market_repairs})
    return {"farmer":actions[0] if actions else ["PASS"],"hands":actions[1:],"market":market}
