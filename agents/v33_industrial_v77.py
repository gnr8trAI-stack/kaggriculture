"""V33.77: replay-timed land expansion over V33.76."""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v76 as _p

_b = _p._b
_parent = _p._capital_allocator

def _capital_allocator(obs, farm, stats):
    orders, meta = _parent(obs, farm, stats)
    orders = [list(o) if isinstance(o, list) else o for o in orders]
    meta = dict(meta)
    day = int(obs.get('day', 0) or 0)
    lands = max(1, int(stats.get('lands', 1) or 1))
    money = float(farm.get('money', 0) or 0)
    productive = int(stats.get('productive', 0) or 0)
    idle = int(stats.get('idle', 0) or 0)
    animals = int(stats.get('animals', 0) or 0)
    qs = stats.get('districts') or {}
    orders = [o for o in orders if not (isinstance(o, list) and o and str(o[0]).upper() == 'BUY_LAND')]
    cost = {1:1000, 2:2000, 3:4000}.get(lands, 10**9)
    reserve = 1200 + 90 * animals
    post = money - cost
    buy = False
    tag = ''
    if lands == 1:
        buy = 6 <= day <= 9 and productive >= 16 and post >= reserve
        tag = 'q2_d7'
    elif lands == 2:
        q12 = int((qs.get(1) or {}).get('productive',0) or 0) + int((qs.get(2) or {}).get('productive',0) or 0)
        buy = 9 <= day <= 12 and q12 >= 24 and post >= max(2500, reserve)
        tag = 'q3_d10'
    elif lands == 3:
        q3 = qs.get(3) or {}
        util = productive / max(1, productive + idle)
        buy = (15 <= day <= 19 and int(q3.get('productive',0) or 0) >= 12 and
               int(q3.get('animals',0) or 0) >= 8 and util >= 0.72 and
               post >= max(10000, reserve + 4000))
        tag = 'q4_roi'
    if buy:
        idx = next((i for i,o in enumerate(orders) if isinstance(o,list) and o and str(o[0]).upper()=='BUY_SEED'), len(orders))
        orders.insert(idx, ['BUY_LAND'])
        if len(orders) > 10:
            for j in range(len(orders)-1, -1, -1):
                if isinstance(orders[j],list) and orders[j] and str(orders[j][0]).upper()=='BUY_SEED':
                    orders.pop(j); break
        meta['land']=1; meta['land_cost']=cost; meta['v77_land']=tag
    else:
        meta['v77_land']=''
    return orders[:10], meta

_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_p._p._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator

def agent(observation: Any, configuration: Any=None): return _p.agent(observation, configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
