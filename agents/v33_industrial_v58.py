"""V33.58 liquidity-first four-district industrial allocator.

V33.57 proved zero-invalid execution and dense two-district crop operation, but
its 24-game telemetry showed the capital trap clearly: premium/long-cycle seed
working capital consumed cash through D15, so Q3/Q4 were never commissioned.
V33.58 changes the economic mechanism, not the executor:

* Q1/Q2 use fast-turn liquidity crops through D10 (WHEAT/CARROT), avoiding
  strawberry/melon capital lock-up before industrial land is financed;
* Q3 commissioning remains ROI/reserve gated but the window follows realized
  cash rather than ending before the crop factory monetizes;
* biological capex stays staged behind operating reserve and paid-land use;
* Q4 is still explicit and requires a functioning Q3 plus positive runway.

Independent V33 architecture; V19/V32 remain reference-only.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v57 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator
_parent_crop_for = _core._crop_for


def _crop_for(day:int, district:int, obs:Mapping[str,Any])->str:
    # Liquidity bridge: before Q3 can be financed, maximize capital turns rather
    # than nominal long-cycle margin. Split products to reduce self-glut.
    if day <= 10 and district in (1,2):
        return "WHEAT" if district == 1 else "CARROT"
    return _parent_crop_for(day,district,obs)

_core._crop_for = _crop_for
_b._crop_for = _crop_for


def _quoted_sales(obs, orders):
    prices=_b._prices(obs); total=0.0
    for o in orders:
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL":
            item=str(o[1]).upper(); total += int(o[2])*float(prices.get(item,_b.VALUE.get(item,1)) or _b.VALUE.get(item,1))
    return total


def _land_packet(orders):
    out=[list(o) for o in orders if isinstance(o,list) and o and o[0]=="SELL"]
    out.append(["BUY_LAND"])
    return out[:10]


def _capital_allocator(obs,farm,stats):
    orders,meta=_parent_allocator(obs,farm,stats); meta=dict(meta)
    day=int(obs.get("day",0) or 0); horizon=max(0,30-day)
    lands=max(1,int(stats.get("lands",1) or 1)); money=float(farm.get("money",0) or 0)
    hands=len(list(farm.get("hands") or [])); qs=stats["districts"]
    q1,q2,q3,q4=(qs[i] for i in (1,2,3,4))
    prod12=int(q1.get("productive",0) or 0)+int(q2.get("productive",0) or 0)
    idle12=int(q1.get("idle",0) or 0)+int(q2.get("idle",0) or 0)
    animals=int(stats.get("animals",0) or 0)
    clean=[list(o) for o in orders if isinstance(o,list) and o and o[0] not in {"BUY_LAND"}][:10]
    realizable=money+0.90*_quoted_sales(obs,clean)
    reserve=250+35*animals
    meta["allocator_v58"]={"lands":lands,"prod12":prod12,"idle12":idle12,"hands":hands,"animals":animals,"realizable":round(realizable,1),"reserve":reserve,"horizon":horizon}

    # Q3: follow monetization. The previous D4-10 gate closed before fast crop
    # cash arrived. Require positive remaining-horizon payback and no crop crisis.
    if lands==2 and 5<=day<=18 and horizon>=12:
        need=2000+reserve
        roi_proxy=horizon*(max(0,prod12)*22.0 + 320.0)  # crop turns + first goose tranche
        if prod12>=24 and idle12<=24 and realizable>=need and roi_proxy>=need*4:
            meta["district_commission_v58"]={"district":3,"required":round(need,1),"realizable":round(realizable,1),"roi_proxy":round(roi_proxy,1)}
            return _land_packet(clean),meta
        meta["q3_gate_v58"]={"cash_gap":round(max(0.0,need-realizable),1),"productive_gap":max(0,24-prod12),"idle12":idle12}

    # Q4: only from a genuinely operating Q3 and enough runway to repay 4k land.
    if lands==3 and 11<=day<=21 and horizon>=9:
        q3_anim=int(q3.get("animals",0) or 0); q3_struct=int(q3.get("coop",0) or 0)+int(q3.get("pasture",0) or 0)
        need=4000+reserve+300
        roi_proxy=horizon*(max(0,prod12)*18.0 + q3_anim*45.0 + 500.0)
        if q3_anim>=4 and q3_struct>=4 and prod12>=26 and hands>=7 and realizable>=need and roi_proxy>=need*3:
            meta["district_commission_v58"]={"district":4,"required":round(need,1),"realizable":round(realizable,1),"q3_animals":q3_anim,"roi_proxy":round(roi_proxy,1)}
            return _land_packet(clean),meta
        meta["q4_gate_v58"]={"cash_gap":round(max(0.0,need-realizable),1),"q3_animals":q3_anim,"q3_structures":q3_struct,"prod12":prod12,"hands":hands}

    return orders[:10],meta

_b._capital_allocator=_capital_allocator


def agent(observation:Any,configuration:Any=None): return _p.agent(observation,configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear:bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
