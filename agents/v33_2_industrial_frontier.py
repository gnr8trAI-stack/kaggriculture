"""V33.2 Industrial Frontier Compounder.

Replay-driven allocator targeting the public frontier signature:
- 3 land by about day 10, optional 4th only when cash-rich;
- 14+ livestock by midgame, milk-first monetization;
- ~60 productive crop tiles across crop districts;
- labour treated as throughput capacity;
- continuous sale of milk, wool, fertilizer and crops;
- low idle-cash tolerance while horizon remains.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping, Tuple
from agents import v33_industrial as _v33


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _market(obs: Mapping[str, Any], farm: Mapping[str, Any], stats: Mapping[str, Any], day: int, hour: int) -> Tuple[List[List[Any]], Dict[str, int]]:
    private = _m(obs.get('private'))
    shed = _m(private.get('shed'))
    money = float(farm.get('money', 0) or 0)
    hands = list(farm.get('hands') or [])
    districts = stats['districts']
    q3 = districts[3]
    lands = int(stats.get('lands', 1) or 1)
    animals = int(q3.get('animals', 0) or 0)
    orders: List[List[Any]] = []
    meta = {'land':0,'hire':0,'animals':0,'seed_spend_proxy':0,'feed':0,'sell_qty':0}
    liquidate = day >= 28

    # Frontier agents monetize everything continuously; only preserve feed wheat.
    for product in ('MILK','WOOL','FERTILIZER','STRAWBERRY','MELON','WHEAT'):
        qty = int(shed.get(product, 0) or 0)
        keep = animals * 4 if product == 'WHEAT' and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (product in {'MILK','WOOL','FERTILIZER'} or sell >= 3 or liquidate):
            orders.append(['SELL', product, sell]); meta['sell_qty'] += sell
            if len(orders) >= 10: return orders, meta

    # Land signature from frontier: second land ~d4-6, third ~d6-10.
    next_cost = {1:1000,2:2000,3:3000}.get(lands,10**9)
    earliest = {1:3,2:5,3:8}.get(lands,99)
    reserve = 500 + 65*len(hands) + 55*animals
    # 4th quadrant is optional; only buy when strong enough not to starve the engine.
    fourth_ok = lands < 3 or money >= next_cost + reserve + 3500
    if lands < 4 and day >= earliest and day <= 18 and fourth_ok and money >= next_cost + reserve and len(orders) < 10:
        orders.append(['BUY_LAND']); meta['land']=1; money -= next_cost

    # Labour scale: enough hands to service 60 crops + 14 livestock.
    unlocked = sum(int(v.get('unlocked',0) or 0) for v in districts.values())
    desired = min(18, max(8, (unlocked+4)//5, 6 + (animals+1)//2))
    hires = min(3, max(0, desired-len(hands)))
    for _ in range(hires):
        if money < 900 or len(orders) >= 10: break
        orders.append(['HIRE']); meta['hire'] += 1; money -= 500

    # Feed first so livestock compounding never causes collapse.
    wheat = int(shed.get('WHEAT',0) or 0)
    feed_target = animals * 5
    if animals and wheat < feed_target and len(orders) < 10:
        need = feed_target-wheat
        orders.append(['BUY_PRODUCT','WHEAT',need]); meta['feed'] += need; money -= need*10

    # Frontier animal signature: ~13-14 by d15, optional 20+ on four land.
    if lands >= 3 and day <= 24:
        target_animals = 14 if lands == 3 else (22 if day <= 18 else 18)
        cow_total = animals + int(shed.get('COW',0) or 0)
        pasture = int(q3.get('pasture',0) or 0)
        capacity = max(0, pasture-cow_total)
        if cow_total < target_animals and capacity > 0 and len(orders) < 10:
            affordable = max(0, int((money-700)//400))
            buy = min(5, target_animals-cow_total, capacity, affordable)
            if buy > 0:
                orders.append(['BUY_ANIMAL','COW',buy]); meta['animals'] += buy; money -= 400*buy

    # Maintain a large crop engine. Favour strawberry midgame, melon later.
    seeds = _m(private.get('seeds'))
    crop = 'STRAWBERRY' if 8 <= day <= 21 else ('MELON' if day >= 22 else 'WHEAT')
    have = int(seeds.get(crop,0) or 0)
    crop_productive = sum(int(districts[q].get('productive',0) or 0) for q in (1,2,4))
    target_productive = 60 if lands >= 3 else 36 if lands == 2 else 22
    need = max(0, target_productive - crop_productive - have)
    if not liquidate and need > 0 and money >= 250 and len(orders) < 10:
        qty = min(24, need)
        orders.append(['BUY_SEED',crop,qty]); meta['seed_spend_proxy'] += qty

    return orders[:10], meta


_v33._market = _market

def reset_state() -> None: _v33.reset_state()
def reset_telemetry() -> None: _v33.reset_telemetry()
def get_telemetry(clear: bool=False): return _v33.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any=None): return _v33.agent(observation, configuration)
