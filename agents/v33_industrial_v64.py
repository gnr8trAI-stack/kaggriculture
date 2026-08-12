"""V33.64 closed-loop fertilizer industrial farm.

Independent V33 architecture over the proven V33.28 four-district control.
Instead of treating animal fertilizer only as a $100 by-product, reserve a
bounded amount and route it back into Q1/Q2/Q4 crops when the expected extra
harvest is worth more than the fertilizer sale plus worker action.  One day-
worker is a fertilizer runner; Q3 remains demand-sized dairy/feed.  This tests a
true cross-district industrial synergy rather than another threshold mutation.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v28 as _p

_b=_p._b
_parent_roles=_p._roles
_parent_unit=_p._unit_action
_parent_alloc=_p._capital_allocator


def _roles(lands:int,hand_count:int):
    roles=list(_parent_roles(lands,hand_count))
    # Re-purpose one crop worker only when the staffed factory is large enough.
    if lands>=3 and len(roles)>=11:
        for i in range(1,len(roles)):
            if roles[i] in {"q1","q2","q4"}:
                roles[i]="fertilizer";break
    return roles


def _fert_targets(obs,farm,reserved):
    day=int(obs.get("day",0) or 0); tiles=farm.get("tiles") or []; out=[]
    prices=_b._prices(obs)
    for y,row in enumerate(tiles):
        if not isinstance(row,list):continue
        for x,t in enumerate(row):
            p=(x,y)
            if p in reserved or not isinstance(t,Mapping) or str(t.get("kind","")).upper()!="PLANT":continue
            q=_b._quadrant(len(tiles),p)
            if q==3:continue
            crop=str(t.get("crop","")).upper()
            if int(t.get("fertilized_until_day",-1) or -1)>=day:continue
            if bool(t.get("watered_today",False)):continue
            # Fertilizer doubles a watered production/bonus increment.  Premium
            # recurring crops get first claim, then short crops at strong quotes.
            price=float(prices.get(crop,_p.BASE.get(crop,1)) or _p.BASE.get(crop,1))
            pri=0 if crop in {"STRAWBERRY","TOMATO"} else 1 if price>=_p.BASE.get(crop,1) else 2
            out.append((pri,-price,y,x,p))
    out.sort();return [r[-1] for r in out]


def _unit_action(obs,farm,idx,p,stats,reserved,seed_budget,role):
    if role=="fertilizer":
        day=int(obs.get("day",0) or 0); private=_b._m(obs.get("private"));shed=_b._m(private.get("shed"));inv=_b._inventory(private,idx);tiles=farm.get("tiles") or []
        if day<=25 and int(inv.get("FERTILIZER",0) or 0)>0:
            goals=_fert_targets(obs,farm,reserved);r=_b._nearest(tiles,p,goals)
            if r is not None:
                reserved.add(r[1]);return (["FERTILIZE"] if r[0]==0 else [r[2]]),"fertilize_crop_v64"
        if day<=25 and int(shed.get("FERTILIZER",0) or 0)>0:
            return _b._to_shed(tiles,p,["PICKUP","FERTILIZER",min(4,int(shed.get("FERTILIZER",0) or 0))]),"pickup_fertilizer_v64"
        role="q1"
    return _parent_unit(obs,farm,idx,p,stats,reserved,seed_budget,role)


def _capital_allocator(obs,farm,stats):
    orders,meta=_parent_alloc(obs,farm,stats);meta=dict(meta)
    day=int(obs.get("day",0) or 0);lands=int(stats.get("lands",1) or 1);animals=int(stats.get("animals",0) or 0);money=float(farm.get("money",0) or 0)
    private=_b._m(obs.get("private"));shed=_b._m(private.get("shed"));fert=int(shed.get("FERTILIZER",0) or 0)
    keep=0 if day>=26 or lands<3 or animals<4 or money<1000 else min(16,max(6,animals))
    clean=[];retained=0
    for o in orders:
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and str(o[1]).upper()=="FERTILIZER" and keep>0:
            q=max(0,int(o[2])-keep);retained=min(int(o[2]),keep)
            if q>0:clean.append(["SELL","FERTILIZER",q])
        else:clean.append(list(o) if isinstance(o,list) else o)
    meta["fertilizer_loop_v64"]={"shed":fert,"keep":keep,"retained":retained,"animals":animals,"lands":lands}
    return clean[:10],meta


_p._roles=_roles
_p._unit_action=_unit_action
_p._capital_allocator=_capital_allocator
_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None):return _p.agent(observation,configuration)
def reset_state():return _p.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _p.get_telemetry(clear=clear)
