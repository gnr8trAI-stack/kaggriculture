"""V32 state-adaptive frontier challenger.

Uses the replay-derived V22 frontier profile as a *target state*, never as an
action clock. Every economic action is recomputed from observed state with
strict affordability, infrastructure, feed-runway and workload gates.
"""
from __future__ import annotations
from collections import Counter
from math import ceil
from typing import Any, Dict, List, Mapping

from agents import v22_frontier_clone as _v22

WEALTH_TARGET = {0: 0, 5: 700, 8: 1000, 10: 3200, 12: 15000, 15: 25000, 20: 58000, 25: 120000, 29: 180000}
SEED_COST = {"WHEAT":10,"STRAWBERRY":100,"MELON":80}
ANIMAL_COST = {"COW":400,"SHEEP":500}
HIRE_FIB = (1,1,2,3,5,8,13,21,34,55,89,144,233,377)


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _wealth_floor(day: int) -> float:
    keys=sorted(WEALTH_TARGET)
    if day<=keys[0]: return float(WEALTH_TARGET[keys[0]])
    if day>=keys[-1]: return float(WEALTH_TARGET[keys[-1]])
    lo=max(k for k in keys if k<=day); hi=min(k for k in keys if k>=day)
    if lo==hi: return float(WEALTH_TARGET[lo])
    f=(day-lo)/(hi-lo)
    return WEALTH_TARGET[lo]+f*(WEALTH_TARGET[hi]-WEALTH_TARGET[lo])


def _counts(tiles: Any):
    crops=Counter(); pastures=0; active=Counter(); empty_pastures=0; occupied=0; usable=0
    if isinstance(tiles,list):
        for row in tiles:
            if not isinstance(row,list): continue
            for tile in row:
                if tile=="LOCKED" or _v22._kind(tile)=="LOCKED": continue
                usable+=1
                if tile is not None: occupied+=1
                if isinstance(tile,Mapping):
                    kind=_v22._kind(tile)
                    if kind=="PLANT":
                        crop=str(tile.get("crop","")).upper(); crops[crop]+=1
                    elif kind=="PASTURE":
                        pastures+=1
                        animal=str(tile.get("animal","")).upper()
                        if animal in {"COW","SHEEP"}: active[animal]+=1
                        else: empty_pastures+=1
    return crops,pastures,active,empty_pastures,occupied,usable


def _recovery_mode(day: int, money: float, land: int, animals: int) -> bool:
    # Do not panic during the intentional day-0 investment trough.
    if day < 8: return False
    floor=_wealth_floor(day)
    structural_lag=(day>=10 and land<2) or (day>=12 and animals<4)
    return money < max(1000.0, floor*0.28) or structural_lag


def _choose_crop(obs: Mapping[str,Any], farm: Mapping[str,Any]):
    day=int(obs.get("day",0) or 0); money=float(farm.get("money",0) or 0)
    tiles=farm.get("tiles") or []
    crops,_,active,_,_,_=_counts(tiles)
    land=len(farm.get("unlocked_quadrants") or ["NW"])
    recovery=_recovery_mode(day,money,land,sum(active.values()))
    if day>=28: return None,{"WHEAT":0.0,"STRAWBERRY":0.0,"MELON":0.0}
    if recovery:
        # Rebuild cheap feed/cash capacity before expensive strawberries.
        if crops["WHEAT"] < max(8,2*sum(active.values())): return "WHEAT",{"WHEAT":1.0,"STRAWBERRY":0.0,"MELON":0.5}
        return "MELON",{"WHEAT":0.2,"STRAWBERRY":0.0,"MELON":1.0}
    return _v22._frontier_choose_crop(obs,farm)


def _strict_market_orders(obs: Mapping[str,Any], farm: Mapping[str,Any], base_market: List[List[Any]]) -> List[List[Any]]:
    day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
    money=float(farm.get("money",0) or 0); budget=money
    hands=list(farm.get("hands") or []); unlocked=list(farm.get("unlocked_quadrants") or ["NW"])
    tiles=farm.get("tiles") or []
    crops,pastures,active,empty_pastures,occupied,usable=_counts(tiles)
    animals=sum(active.values())
    private=_m(obs.get("private")); shed=_m(private.get("shed")); seeds=_m(private.get("seeds"))
    invs=private.get("inventories",[])
    carried_wheat=sum(int(_m(x).get("WHEAT",0) or 0) for x in invs) if isinstance(invs,list) else 0
    orders=[]

    # Preserve valid sale orders from the proven routing engine.
    for raw in base_market:
        if isinstance(raw,list) and raw[:1]==["SELL"] and len(orders)<10:
            orders.append(list(raw))

    liquidate=day>=29 or (day==28 and hour>=12)
    if liquidate:
        out=[]
        for item in _v22.SELLABLE:
            qty=int(shed.get(item,0) or 0)
            if qty>0: out.append(["SELL",item,qty])
            if len(out)>=10: break
        return out

    target=_v22._profile(day)
    recovery=_recovery_mode(day,money,len(unlocked),animals)
    reserve=50 if day==0 else 300 if day<7 else 800 if day<12 else 1500

    def can_spend(cost: float) -> bool:
        return budget-cost >= reserve
    def spend(order: List[Any], cost: float=0.0) -> bool:
        nonlocal budget
        if len(orders)>=10 or not can_spend(cost): return False
        orders.append(order); budget-=cost; return True

    # 1) Feed runway is non-negotiable. Count shed + carried wheat.
    wheat_total=int(shed.get("WHEAT",0) or 0)+carried_wheat
    feed_target=max(0,animals*3)
    if animals and wheat_total<feed_target:
        qty=min(12,feed_target-wheat_total)
        # product price is dynamic; use observed price when available, otherwise conservative 20.
        price=float(_m(_m(obs.get("market")).get("prices")).get("WHEAT",20) or 20)
        afford=max(0,int((budget-reserve)//max(1,price)))
        qty=min(qty,afford)
        if qty>0: spend(["BUY_PRODUCT","WHEAT",qty],qty*price)

    # 2) Land only when the current district is genuinely saturated and the
    # purchase leaves operating liquidity. Never emit an unaffordable order.
    occ=occupied/max(1,usable)
    target_land=int(target["land"])
    if len(unlocked)<target_land and not recovery:
        cost=_v22.LAND_COSTS.get(len(unlocked),1000)
        min_occ=0.72 if len(unlocked)==1 else 0.62
        if occ>=min_occ and budget>=cost+reserve:
            spend(["BUY_LAND"],cost)

    # 3) Animals require a real empty pasture and feed runway. Buy at most two
    # per decision so the farm can absorb servicing load.
    owned=_v22._owned_animals(obs,farm)
    available_slots=empty_pastures
    if available_slots>0 and not recovery:
        for species,key in (("COW","cow"),("SHEEP","sheep")):
            if available_slots<=0: break
            missing=max(0,int(target[key])-int(owned[species]))
            if missing<=0: continue
            qty=min(missing,available_slots,2)
            cost=qty*ANIMAL_COST[species]
            if spend(["BUY_ANIMAL",species,qty],cost): available_slots-=qty

    # 4) Seeds follow productive deficits, but expensive strawberry expansion
    # is suppressed in recovery mode.
    crop,_=_choose_crop(obs,farm)
    if crop:
        wanted=int(target.get(crop,0))
        if recovery and crop=="STRAWBERRY": wanted=0
        deficit=max(0,wanted-int(crops[crop])-int(seeds.get(crop,0) or 0))
        if recovery and crop in {"WHEAT","MELON"}: deficit=max(deficit,6)
        if deficit>0:
            unit=SEED_COST[crop]; qty=min(deficit,12,max(0,int((budget-reserve)//unit)))
            if qty>0: spend(["BUY_SEED",crop,qty],qty*unit)

    # 5) Labor is workload-driven, not replay-count driven. Roughly one worker
    # per 7 service-points, bounded by the elite profile and current liquidity.
    workload=sum(crops.values()) + 2*animals + max(0,pastures-animals)
    desired=min(int(target["hands"]), max(4,ceil(workload/7)))
    if recovery: desired=min(desired,6)
    missing=max(0,desired-len(hands))
    # Conservative daily hire budgeting: even if prior hires already occurred,
    # reserve enough for the steeper part of the Fibonacci schedule.
    for i in range(min(missing,4)):
        est=HIRE_FIB[min(len(hands)+i, len(HIRE_FIB)-1)]
        if not spend(["HIRE"],est): break

    return orders[:10]


# Patch V22's shared V12 hooks and market planner.
_v22._V12G["choose_crop"]=_choose_crop
_v22._market_orders=_strict_market_orders


def reset_state() -> None:
    _v22.reset_state()
    _v22._V12G["choose_crop"]=_choose_crop
    _v22._market_orders=_strict_market_orders


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool=False):
    return _v22.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any=None) -> Dict[str,Any]:
    return _v22.agent(observation,configuration)
