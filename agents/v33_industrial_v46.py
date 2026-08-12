"""V33.46 cash-realized industrial land ladder.

V33.45 proved the new mechanics-priced executor is stable but its Q3 threshold
was economically mistimed: fast-crop proceeds arrive in the shed after the
initial gate window, so profitable land stayed locked while cash compounded in
only two quadrants.  This revision makes land compete on *same-turn realizable
cash*: queued sales execute before BUY_LAND, and a land turn suppresses lower
priority seed/feed/animal capex.  The V33.45 district, mixed-species, alternate
feed/care, market and telemetry architecture is otherwise retained.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v45 as _p

_b=_p._b
_parent=_p._capital_allocator


def _quoted_sales(obs,orders):
    prices=_b._prices(obs);v=0.0
    for o in orders:
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL":
            v+=int(o[2])*float(prices.get(o[1],_b.VALUE.get(o[1],1)) or _b.VALUE.get(o[1],1))
    return v


def _capital_allocator(obs,farm,stats):
    orders,meta=_parent(obs,farm,stats)
    day=int(obs.get("day",0) or 0);hour=int(obs.get("hour",0) or 0);lands=max(1,int(stats.get("lands",1) or 1))
    if hour<=2 or day>=28 or any(isinstance(o,list) and o and o[0]=="BUY_LAND" for o in orders):return orders,meta
    money=float(farm.get("money",0) or 0);realizable=money+0.82*_quoted_sales(obs,orders);productive=int(stats.get("productive",0) or 0)
    q3=stats["districts"][3];commissioned=int(q3.get("coop",0) or 0)+int(q3.get("pasture",0) or 0)
    buy=False;cost=0
    if lands==2 and 4<=day<=14 and productive>=30 and realizable>=2850:
        buy=True;cost=2000
    elif lands==3 and 5<=day<=16 and commissioned>=6 and productive>=38 and realizable>=4850:
        buy=True;cost=4000
    if not buy:return orders,meta

    # Sales finance land in the same lockstep market packet. Lower-priority capex
    # waits one turn so it cannot consume the cash before the atomic land order.
    kept=[o for o in orders if isinstance(o,list) and o and o[0]=="SELL"]
    kept.append(["BUY_LAND"])
    meta=dict(meta);meta["land"]=1;meta["land_cost"]=cost;meta["reinvestment"]="land_realized";meta["land_realizable_cash"]=round(realizable,2)
    return kept[:10],meta

_b._capital_allocator=_capital_allocator

def agent(observation:Any,configuration:Any=None):return _p.agent(observation,configuration)
def reset_state():return _p.reset_state()
def reset_telemetry():return reset_state()
def get_telemetry(clear:bool=False):return _p.get_telemetry(clear=clear)
def industrial_peaks():return _p.industrial_peaks()
