"""V32.2 cashflow-first challenger.

Preserves V32's state-adaptive execution but only expands when the current
farm can fund land from operating surplus after feed, seed and labor reserves.
Avoids V32.1's mistake of buying land merely because cash crossed the sticker
price.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v32_state_adaptive_frontier as _v32

_v22=_v32._v22

def _m(v:Any)->Mapping[str,Any]:
    return v if isinstance(v,Mapping) else {}

def _cashflow_market(obs:Mapping[str,Any], farm:Mapping[str,Any], base_market:List[List[Any]])->List[List[Any]]:
    day=int(obs.get('day',0) or 0); hour=int(obs.get('hour',0) or 0)
    money=float(farm.get('money',0) or 0)
    unlocked=list(farm.get('unlocked_quadrants') or ['NW']); land=len(unlocked)
    hands=list(farm.get('hands') or [])
    crops,pastures,active,empty_pastures,occupied,usable=_v32._counts(farm.get('tiles') or [])
    animals=sum(active.values())
    private=_m(obs.get('private')); shed=_m(private.get('shed'))
    raw=_v32._strict_market_orders(obs,farm,base_market)
    if day>=29 or (day==28 and hour>=12): return raw

    # Operating reserve: enough to keep production alive after any capex.
    wheat=int(shed.get('WHEAT',0) or 0)
    feed_gap=max(0,animals*3-wheat)
    feed_reserve=feed_gap*20
    replant_reserve=max(300, 12*10 + min(8,max(0,12-crops['MELON']))*80)
    labor_reserve=250 if len(hands)<6 else 100
    liquidity_reserve=max(900 if day<12 else 1500, feed_reserve+replant_reserve+labor_reserve)
    productive=crops['WHEAT']+crops['MELON']+crops['STRAWBERRY']

    # Expansion is funded only from surplus. Second land needs a functioning
    # core; third land needs a materially stronger engine.
    want_land=1
    if day>=6 and productive>=14 and animals>=4 and len(hands)>=5: want_land=2
    if day>=10 and productive>=24 and animals>=6 and len(hands)>=7: want_land=3
    pending=land<want_land
    land_cost=_v22.LAND_COSTS.get(land,1000)
    can_buy_land=pending and money>=land_cost+liquidity_reserve

    orders=[]
    # Preserve realized cash generation and feed first.
    for o in raw:
        if not isinstance(o,list) or not o: continue
        if o[0]=='SELL' or o[:2]==['BUY_PRODUCT','WHEAT']:
            if len(orders)<10: orders.append(list(o))

    if can_buy_land and len(orders)<10:
        orders.append(['BUY_LAND'])
        # On an expansion turn, only cheap replanting may accompany capex.
        for o in raw:
            if len(orders)>=10: break
            if not isinstance(o,list) or not o: continue
            if o[:2] in (['BUY_SEED','WHEAT'],['BUY_SEED','MELON']):
                orders.append(list(o))
        return orders[:10]

    # Keep V32's productive engine, but prevent capex from consuming the
    # operating reserve. Moderate herd caps until land has genuinely scaled.
    herd_cap=8 if land==1 else 11 if land==2 else 14
    current_animals=animals
    est_budget=money
    for o in raw:
        if len(orders)>=10: break
        if not isinstance(o,list) or not o: continue
        if o[0]=='SELL' or o[:2]==['BUY_PRODUCT','WHEAT']: continue
        if o[0]=='BUY_LAND': continue
        cost=0.0
        if o[0]=='BUY_ANIMAL':
            room=max(0,herd_cap-current_animals)
            if room<=0: continue
            qty=min(int(o[2]),room)
            if qty<=0: continue
            unit=_v32.ANIMAL_COST.get(str(o[1]).upper(),500)
            cost=qty*unit
            if est_budget-cost<liquidity_reserve: continue
            orders.append(['BUY_ANIMAL',o[1],qty]); current_animals+=qty; est_budget-=cost; continue
        if o[:2]==['BUY_SEED','STRAWBERRY']:
            qty=int(o[2]); cost=qty*_v32.SEED_COST['STRAWBERRY']
            # Strawberries are allowed before expansion only from genuine surplus.
            if est_budget-cost<liquidity_reserve or (land<2 and money<3000): continue
            orders.append(list(o)); est_budget-=cost; continue
        if o[0]=='HIRE':
            # No speculative labor while the engine is below six productive hands.
            if len(hands)>=8 and land<2: continue
            cost=100
            if est_budget-cost<liquidity_reserve: continue
            orders.append(list(o)); est_budget-=cost; continue
        if o[:2] in (['BUY_SEED','WHEAT'],['BUY_SEED','MELON']):
            unit=_v32.SEED_COST.get(o[1],20); cost=int(o[2])*unit
            if est_budget-cost<max(300,liquidity_reserve*0.5): continue
            orders.append(list(o)); est_budget-=cost; continue
        orders.append(list(o))
    return orders[:10]

def reset_state()->None:
    _v32.reset_state(); _v22._market_orders=_cashflow_market

def reset_telemetry()->None: reset_state()
def get_telemetry(clear:bool=False): return _v32.get_telemetry(clear=clear)

def agent(observation:Any, configuration:Any=None)->Dict[str,Any]:
    _v22._market_orders=_cashflow_market
    return _v22.agent(observation,configuration)

_v22._market_orders=_cashflow_market
