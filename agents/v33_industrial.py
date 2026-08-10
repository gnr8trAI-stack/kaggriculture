"""V33.1 Industrial: proven V19.2 operating core + explicit four-quadrant scale controller.

Fixes V33 alpha1's structural bug: do not trust a missing `unlocked_quadrants`
field. Infer owned quadrants directly from the tile grid, then use that observed
state to drive serial land expansion and workforce scaling.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping, List
from agents import v19_2_early_scale8 as _v192

_RECORDS: List[Dict[str, Any]] = []
_LAST_STEP = -1


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _kind(tile: Any) -> str:
    if tile is None: return "EMPTY"
    if tile == "LOCKED": return "LOCKED"
    if isinstance(tile, Mapping): return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _quadrant_counts(tiles: Any) -> Dict[int, Dict[str, int]]:
    out = {q:{"unlocked":0,"productive":0,"pasture":0,"animals":0} for q in range(1,5)}
    if not isinstance(tiles, list) or not tiles: return out
    n=len(tiles); h=n//2
    for y,row in enumerate(tiles):
        if not isinstance(row,list): continue
        for x,t in enumerate(row):
            k=_kind(t)
            if k=="LOCKED": continue
            q = 1 if x<h and y<h else 2 if x>=h and y<h else 3 if x<h and y>=h else 4
            z=out[q]; z["unlocked"]+=1
            if k in {"PLANT","PASTURE","COOP"}: z["productive"]+=1
            if k=="PASTURE":
                z["pasture"]+=1
                if isinstance(t,Mapping) and t.get("animal"): z["animals"]+=1
    return out


def _owned_quadrants(qs: Mapping[int, Mapping[str,int]]) -> int:
    # Central shed cells leak into adjacent quadrants. >4 distinguishes actual land.
    return sum(1 for q in qs.values() if int(q.get("unlocked",0) or 0) > 4)


def reset_state() -> None:
    global _LAST_STEP
    _LAST_STEP=-1; _RECORDS.clear(); _v192.reset_state()


def reset_telemetry() -> None: reset_state()

def get_telemetry(clear: bool=False):
    rows=list(_RECORDS)
    if clear: _RECORDS.clear()
    return rows


def agent(observation: Any, configuration: Any=None) -> Dict[str,Any]:
    global _LAST_STEP
    obs=_v192._v19._obs(observation)
    player=int(obs.get("player",0) or 0); farms=obs.get("farms") or []
    if not isinstance(farms,list) or player>=len(farms):
        return _v192.agent(observation, configuration)
    farm=_m(farms[player]); tiles=farm.get("tiles") or []
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0); step=int(obs.get("step",day*24+hour) or 0)
    if _LAST_STEP>=0 and step<=_LAST_STEP: reset_state()
    _LAST_STEP=step

    # Start from the live-proven V19.2 operational policy.
    result=dict(_v192.agent(observation, configuration))
    market=[list(o) for o in result.get("market",[]) if isinstance(o,list)]
    money=float(farm.get("money",0) or 0); hands=list(farm.get("hands") or [])
    qs=_quadrant_counts(tiles); lands=_owned_quadrants(qs)
    health=_v192._v19._farm_health(farm)

    # Serial reinvestment: thresholds intentionally lower than the failed 26k/36k
    # experiment because those gates were rarely reachable before the payback window.
    land_threshold=None
    if lands==2 and 9<=day<=18: land_threshold=15000
    elif lands==3 and 11<=day<=20: land_threshold=24000
    operating_reserve = 1800 + 180*len(hands) + 250*sum(int(q["animals"]) for q in qs.values())
    should_expand = (
        land_threshold is not None and money >= land_threshold + operating_reserve
        and int(health.get("danger",0) or 0) <= 3
        and float(health.get("weed_ratio",0.0) or 0.0) <= 0.20
    )
    if should_expand and not any(o[:1]==["BUY_LAND"] for o in market):
        market=[["BUY_LAND"]] + market

    # Industrial labour cap scales with owned land. Add at most two hires per market turn,
    # but never consume the operating reserve.
    desired_hands={1:5,2:8,3:11,4:14}.get(lands,5)
    existing_hires=sum(1 for o in market if o[:1]==["HIRE"])
    extra=max(0,min(2,desired_hands-len(hands)-existing_hires))
    spendable=max(0.0,money-operating_reserve)
    for _ in range(extra):
        if spendable < 600 or len(market)>=10: break
        market.append(["HIRE"]); spendable-=500

    result["market"]=market[:10]
    _RECORDS.append({
        "step":step,"day":day,"hour":hour,"money":money,"lands":lands,
        "hands":len(hands),"q1":dict(qs[1]),"q2":dict(qs[2]),"q3":dict(qs[3]),"q4":dict(qs[4]),
        "productive":sum(int(q["productive"]) for q in qs.values()),
        "empty":sum(max(0,int(q["unlocked"])-int(q["productive"])) for q in qs.values()),
        "land_threshold":land_threshold,"should_expand":should_expand,
    })
    return result
