"""V32.1 land-first challenger.

Fixes V32 alpha1's benchmark failure mode: it reached the 8C+6S herd but
never bought three land quadrants. This wrapper keeps V32's state-adaptive
routing/servicing engine while reserving capital for expansion before full
herd/strawberry/labour scale.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping

from agents import v32_state_adaptive_frontier as _v32

_v22 = _v32._v22


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _land_first_market(obs: Mapping[str,Any], farm: Mapping[str,Any], base_market: List[List[Any]]) -> List[List[Any]]:
    day=int(obs.get("day",0) or 0)
    hour=int(obs.get("hour",0) or 0)
    money=float(farm.get("money",0) or 0)
    unlocked=list(farm.get("unlocked_quadrants") or ["NW"])
    land=len(unlocked)
    tiles=farm.get("tiles") or []
    crops,pastures,active,empty_pastures,occupied,usable=_v32._counts(tiles)
    animals=sum(active.values())

    # Start from V32's legal/state-aware orders, then enforce capital sequence.
    raw=_v32._strict_market_orders(obs,farm,base_market)
    if day>=29 or (day==28 and hour>=12):
        return raw

    # Replay-derived expansion targets, but state/affordability gated.
    want_land = 2 if day>=5 else 1
    if day>=8: want_land = 3
    pending_land = land < want_land
    land_cost = _v22.LAND_COSTS.get(land,1000)
    # Keep enough liquidity for feed + cheap seed recovery after purchase.
    reserve = 450 if land==1 else 900

    # Before second land, cap the herd at the successful day-0 core (3C+1S).
    # Before third land, permit moderate livestock only; full 8C+6S comes after.
    herd_cap = 4 if land < 2 else 8 if land < 3 else 14
    current_animals = animals

    orders=[]
    # Preserve sales and feed first. They keep the farm alive and can free
    # inventory, but we do not assume same-turn sale proceeds are spendable.
    for o in raw:
        if not isinstance(o,list) or not o: continue
        if o[0]=="SELL" or o[:2]==["BUY_PRODUCT","WHEAT"]:
            if len(orders)<10: orders.append(list(o))

    # Force expansion as soon as cash genuinely exists. Unlike V32 alpha1,
    # recovery mode never blocks BUY_LAND.
    if pending_land and money >= land_cost + reserve and len(orders)<10:
        orders.append(["BUY_LAND"])
        # Land is the capital priority this turn: don't simultaneously spend
        # the same cash on animals, strawberries, or speculative hires.
        for o in raw:
            if len(orders)>=10: break
            if not isinstance(o,list) or not o: continue
            if o[0] in {"SELL","BUY_LAND"} or o[:2]==["BUY_PRODUCT","WHEAT"]: continue
            if o[:2]==["BUY_SEED","WHEAT"] or o[:2]==["BUY_SEED","MELON"]:
                orders.append(list(o))
        return orders[:10]

    # If land is pending but not yet affordable, hoard capital: no expensive
    # strawberries, no extra hires beyond six hands, and no herd beyond cap.
    for o in raw:
        if len(orders)>=10: break
        if not isinstance(o,list) or not o: continue
        if o[0]=="SELL" or o[:2]==["BUY_PRODUCT","WHEAT"]: continue
        if o[0]=="BUY_LAND":
            # V32 may have generated one under its stricter occupancy gate.
            if money >= land_cost + reserve and pending_land:
                orders.append(["BUY_LAND"])
            continue
        if o[0]=="BUY_ANIMAL":
            room=max(0,herd_cap-current_animals)
            if room<=0 or pending_land: continue
            qty=min(int(o[2]),room)
            if qty>0:
                orders.append(["BUY_ANIMAL",o[1],qty]); current_animals+=qty
            continue
        if o[:2]==["BUY_SEED","STRAWBERRY"] and pending_land:
            continue
        if o[0]=="HIRE" and pending_land and len(farm.get("hands") or [])>=6:
            continue
        orders.append(list(o))

    return orders[:10]


def reset_state() -> None:
    _v32.reset_state()
    _v22._market_orders=_land_first_market


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool=False):
    return _v32.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any=None) -> Dict[str,Any]:
    # Reassert wrapper because shared modules are mutated by imported baselines
    # during paired benchmarks.
    _v22._market_orders=_land_first_market
    return _v22.agent(observation,configuration)


# Activate on import.
_v22._market_orders=_land_first_market
