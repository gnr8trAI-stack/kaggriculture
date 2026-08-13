"""V19.4 staged challenger: correct feed accounting + third crop district.

Fresh Aug-8 frontier replays converge on three unlocked districts, 14 animals,
about 42 strawberries and 61 peak crops. V19 can unlock only one extra district
because its base expansion gate requires len(unlocked)==1. This candidate tests
the next structural bottleneck without simultaneously jumping livestock from 4
to 14.

Changes versus V19:
- crew-only carried-feed accounting (same correction as V19.3);
- first expansion may begin on day 8 with a slightly lower saturation gate;
- adaptive crop mode is forced by day 16;
- a second BUY_LAND is added for the third district on days 13-18 only when
  four cows are active, crop health is safe, productive occupancy >=30 and cash
  >=8,000, leaving substantial working capital after the 2,000 land cost;
- seven hands are targeted with an eight-hand cap once livestock is active.

Cow target remains exactly four. The experiment isolates land/crop throughput
before increasing herd service load.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from agents import v19_livestock_compound as _v19

# Earlier but still guarded first scale step.
_v19.EXPAND_MIN_DAY=8
_v19.EXPAND_MAX_DAY=18
_v19.MIN_PEAK_NW_PRODUCTIVE=18
_v19.MIN_CASH_TO_EXPAND=3500
_v19.FORCE_ADAPTIVE_DAY=16
_v19.MIN_HANDS_WITH_COWS=7
_v19.MAX_HANDS_WITH_COWS=8

THIRD_LAND_MIN_DAY=13
THIRD_LAND_MAX_DAY=18
THIRD_LAND_MIN_CASH=8000
THIRD_LAND_MIN_PRODUCTIVE=30
THIRD_LAND_MAX_WEEDS=4
THIRD_LAND_MAX_DANGER=1


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v,Mapping) else {}


def _crew_indices(farm: Mapping[str, Any], active: int, target: int, pastures: int) -> List[int]:
    hands=list(farm.get("hands") or [])
    n=min(2,len(hands)) if (active or target>0 or pastures>0) else 0
    return list(range(1+len(hands)-n,1+len(hands))) if n else []


def _inject_market_orders(
    base_orders: Sequence[Any], *, expansion_eligible: bool, land_injected: bool,
    obs: Mapping[str, Any], farm: Mapping[str, Any], target_cows: int,
) -> Tuple[List[List[Any]], Dict[str,int]]:
    private=_m(obs.get("private")); shed=_m(private.get("shed")); invs=private.get("inventories",[])
    tiles=farm.get("tiles") or []; hands=list(farm.get("hands") or [])
    active=len(_v19._active_cows(tiles)); cows=_v19._cow_count(obs,farm)
    empties=len(_v19._empty_pastures(tiles)); pastures=len(_v19._pastures(tiles))
    clean=[]
    for raw in base_orders:
        if not isinstance(raw,list) or not raw: continue
        if str(raw[0]).upper() in {"BUY_LAND","BUY_ANIMAL"}: continue
        clean.append(list(raw))
    critical=[]
    if expansion_eligible and land_injected: critical.append(["BUY_LAND"])

    usable=int(shed.get("WHEAT",0) or 0)
    if isinstance(invs,list):
        for idx in _crew_indices(farm,active,target_cows,pastures):
            if idx < len(invs): usable += int(_m(invs[idx]).get("WHEAT",0) or 0)
    target_feed=active*_v19.FEED_BUFFER_PER_COW
    if active>0 and usable<target_feed:
        critical.append(["BUY_PRODUCT","WHEAT",target_feed-usable])

    need=min(empties,max(0,target_cows-cows))
    if need>0:
        affordable=max(0,int((float(farm.get("money",0) or 0)-1200)//_v19.ANIMAL_COST))
        buy=min(need,affordable)
        if buy>0: critical.append(["BUY_ANIMAL",_v19.ANIMAL,buy])

    hires_in_clean=sum(1 for o in clean if o[:1]==["HIRE"])
    desired=min(_v19.MAX_HANDS_WITH_COWS,_v19.MIN_HANDS_WITH_COWS if (active or target_cows>0) else len(hands))
    extra=max(0,desired-len(hands)-hires_in_clean)
    critical.extend([["HIRE"] for _ in range(extra)])
    return (critical+clean)[:10],{
        "wheat_bought":sum(int(o[2]) for o in critical if o[:2]==["BUY_PRODUCT","WHEAT"]),
        "cows_bought":sum(int(o[2]) for o in critical if o[:2]==["BUY_ANIMAL",_v19.ANIMAL]),
        "extra_hires":extra,
    }


_v19._inject_market_orders=_inject_market_orders


def _obs(value: Any) -> Dict[str,Any]:
    if isinstance(value,dict): return value
    return {k:getattr(value,k) for k in ("player","step","day","hour","farms","private","market","town") if hasattr(value,k)}


def reset_state() -> None: _v19.reset_state()
def reset_telemetry() -> None: _v19.reset_telemetry()
def get_telemetry(clear: bool=False): return _v19.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any=None):
    obs=_obs(observation)
    result=dict(_v19.agent(observation,configuration))
    player=int(obs.get("player",0) or 0); farms=obs.get("farms") or []
    if not isinstance(farms,list) or player>=len(farms): return result
    farm=_m(farms[player]); tiles=farm.get("tiles") or []
    day=int(obs.get("day",0) or 0); money=float(farm.get("money",0) or 0)
    unlocked=list(farm.get("unlocked_quadrants") or ["NW"])
    health=_v19._farm_health(farm)
    active=len(_v19._active_cows(tiles))

    third_land=(
        len(unlocked)==2 and THIRD_LAND_MIN_DAY<=day<=THIRD_LAND_MAX_DAY
        and money>=THIRD_LAND_MIN_CASH and active>=_v19.MAX_COW_TARGET
        and int(health.get("productive",0) or 0)>=THIRD_LAND_MIN_PRODUCTIVE
        and int(health.get("weeds",0) or 0)<=THIRD_LAND_MAX_WEEDS
        and int(health.get("danger",0) or 0)<=THIRD_LAND_MAX_DANGER
    )
    if not third_land: return result

    orders=[list(o) for o in result.get("market",[]) if isinstance(o,list) and o]
    if any(str(o[0]).upper()=="BUY_LAND" for o in orders): return result

    # Keep survival/setup orders ahead of land. Insert before ordinary crop/sell
    # traffic while preserving the ten-order contract.
    critical_ops={"BUY_PRODUCT","BUY_ANIMAL","HIRE"}
    cut=0
    while cut<len(orders) and str(orders[cut][0]).upper() in critical_ops:
        cut+=1
    orders.insert(cut,["BUY_LAND"])
    result["market"]=orders[:10]
    return result
