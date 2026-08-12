"""V33.47 land-before-luxury industrial priority.

Replay/telemetry from V33.45/46 showed the first wheat cycle *did* commission
~47 crop cells, but Q1 immediately reinvested the realized cash into a bounded
melon cycle before Q3.  Current productive tiles simultaneously dip during the
harvest/replant transition, so a current-productivity land gate never fired.

This revision fixes the allocator, not a cosmetic threshold: productive land is
senior capital.  Q3 is purchased from the first realizable post-bootstrap cash
packet before new long-cycle crop/animal/feed capex.  The single Q1 melon
scarcity cycle is deferred until Q3 exists.  Q4 remains gated by actual Q3
structure commissioning and remaining horizon.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v45 as _p

_b=_p._b
_parent_allocator=_p._capital_allocator
_base_crop=_p._crop_for


def _current_lands(obs:Mapping[str,Any])->int:
    try:
        player=int(obs.get("player",0) or 0);farm=(obs.get("farms") or [])[player]
        return max(1,int(_p._stats(_b._m(farm).get("tiles") or []).get("lands",1) or 1))
    except Exception:return 1


def _crop_for(day:int,district:int,obs:Mapping[str,Any])->str:
    # Keep all bootstrap capital fast-turn until Q3 is owned.  Only then spend
    # $80/seed on the one finite high-value melon market tranche.
    if day<=3:return "WHEAT"
    if district==1 and 4<=day<=9 and _current_lands(obs)>=3:return "MELON"
    return _base_crop(day,district,obs) if not (district==1 and 4<=day<=9) else "WHEAT"

# V45 functions resolve their module globals at call time.
_p._crop_for=_crop_for
_b._crop_for=_crop_for


def _quoted_sales(obs,orders):
    prices=_b._prices(obs);v=0.0
    for o in orders:
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL":v+=int(o[2])*float(prices.get(o[1],_b.VALUE.get(o[1],1)) or _b.VALUE.get(o[1],1))
    return v


def _capital_allocator(obs,farm,stats):
    orders,meta=_parent_allocator(obs,farm,stats)
    day=int(obs.get("day",0) or 0);hour=int(obs.get("hour",0) or 0);lands=max(1,int(stats.get("lands",1) or 1))
    if hour<=2 or day>=28 or lands>=4:return orders,meta
    if any(isinstance(o,list) and o and o[0]=="BUY_LAND" for o in orders):return orders,meta
    money=float(farm.get("money",0) or 0);realizable=money+0.84*_quoted_sales(obs,orders);horizon=max(0,30-day)
    buy=False;cost=0
    if lands==2 and 3<=day<=18 and horizon>=11 and realizable>=2350:
        buy=True;cost=2000
    elif lands==3:
        q3=stats["districts"][3];commissioned=int(q3.get("coop",0) or 0)+int(q3.get("pasture",0) or 0)
        # Four free structures prove labour has begun commissioning Q3. Q4 then
        # wins over more animal/seed capex while >=14 days remain.
        if day<=16 and horizon>=14 and commissioned>=4 and realizable>=4450:
            buy=True;cost=4000
    if not buy:return orders,meta
    sales=[o for o in orders if isinstance(o,list) and o and o[0]=="SELL"]
    sales.append(["BUY_LAND"])
    meta=dict(meta);meta["land"]=1;meta["land_cost"]=cost;meta["reinvestment"]="senior_land";meta["land_realizable_cash"]=round(realizable,2)
    return sales[:10],meta

_b._capital_allocator=_capital_allocator

def agent(observation:Any,configuration:Any=None):return _p.agent(observation,configuration)
def reset_state():return _p.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _p.get_telemetry(clear=clear)
def industrial_peaks():return _p.industrial_peaks()
