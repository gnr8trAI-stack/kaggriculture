"""V33.63 absorption-matched animal/feed factory.

Independent V33 architecture.  V33.28 showed four-land physical scale and V33.29
showed that an unconditional mixed herd loses money.  V33.63 makes Q3 a demand-
matched animal factory and Q4 its low-cost wheat feed plant.  Animal lines are
sized from exact recurring shop absorption and cared production rates; products
with no shop absorption receive only a tiny speculative line.  Q1/Q2 retain the
proven demand-aware crop cash engine.  V19/V32 are controls only.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial_v29 as _p

_b=_p._b
_v28=_p._v28
_parent_mix=_p._mix_target
_parent_crop=_v28._crop_for

RATES={"COW":1.5,"GOOSE":2.0,"SHEEP":4.0/3.0}
PRODUCT={"COW":"MILK","GOOSE":"EGG","SHEEP":"WOOL"}
CAP={"COW":12,"GOOSE":12,"SHEEP":10}


def _mix_target(obs: Mapping[str,Any], day:int, active:Mapping[str,int])->Dict[str,int]:
    horizon=max(0,30-day)
    if horizon<6:
        return {a:int(active.get(a,0) or 0) for a in RATES}
    prices=_b._prices(obs)
    target={}
    for a,rate in RATES.items():
        item=PRODUCT[a]; demand=_v28._daily_demand(obs,item)
        # Capacity equals recurring absorption plus one buffering animal.  With
        # center-only demand, keep only a small line that the initial market can
        # absorb without a destructive glut.
        if demand<=1:
            want={"COW":2,"GOOSE":3,"SHEEP":0}[a]
        else:
            want=int((demand+rate-1e-9)//rate)+1
        base=float(_v28.BASE[item]); live=float(prices.get(item,base) or base)
        if live<0.55*base: want=min(want,int(active.get(a,0) or 0))
        elif live<0.80*base: want=min(want,int(active.get(a,0) or 0)+1)
        # Startup runway: do not add animals whose first yield cannot repay.
        first=_p.ANIMAL[a]["first"]
        if horizon<=first+3: want=int(active.get(a,0) or 0)
        target[a]=max(int(active.get(a,0) or 0),min(CAP[a],want))

    # Q3 usable surface: cap the combined factory at 20 structures.  Preserve
    # lines with the highest recurring revenue absorption first.
    while sum(target.values())>20:
        candidates=[]
        for a in target:
            act=int(active.get(a,0) or 0)
            if target[a]<=act: continue
            item=PRODUCT[a]; d=_v28._daily_demand(obs,item); p=float(prices.get(item,_v28.BASE[item]) or _v28.BASE[item])
            candidates.append((d*p,a))
        if not candidates: break
        _,a=min(candidates); target[a]-=1
    return target


def _crop_for(day:int,district:int,obs:Mapping[str,Any])->str:
    # Once Q3 is operating, Q4 becomes a feed factory.  Wheat seed costs $10 for
    # ~4 units vs ~$25 live market feed, a large recurring operating-margin gain.
    if district==4:
        farms=obs.get("farms") or []; player=int(obs.get("player",0) or 0)
        farm=farms[player] if isinstance(farms,list) and player<len(farms) else {}
        animals=0
        for row in (farm.get("tiles") or []):
            if isinstance(row,list):
                for t in row:
                    if isinstance(t,Mapping) and t.get("animal"): animals+=1
        if animals>=4 and day<=24: return "WHEAT"
        if day>=18: return "WHEAT"
    return _parent_crop(day,district,obs)


_p._mix_target=_mix_target
_v28._crop_for=_crop_for


def agent(observation:Any,configuration:Any=None): return _p.agent(observation,configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear:bool=False): return _p.get_telemetry(clear=clear)
