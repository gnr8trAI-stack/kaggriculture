"""V33.18 horizon-priced industrial allocator.

Independent V33 architecture.  Builds on the maturity-safe district execution
of V33.14, but replaces the allocator with a remaining-horizon capital policy.
The measured V33.17 result showed that four-district utilization can be reached
without translating enough terminal capital back into cash.  V33.18 therefore
front-loads commissioning, prices every late investment by remaining harvest
cycles, limits livestock to a feed-solvent Q3 core, and hard-switches from
reinvestment to cash conversion late in the episode.

V19.2 is benchmark control only and is not imported.
"""
from __future__ import annotations
from typing import Any, Dict, List
from agents import v33_industrial_v14 as _v14

_b = _v14._b
_b.HIRE_COST = 1


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # Keep livestock deliberately compact; crop acreage is the main cash engine.
        crew = 3 if hand_count < 15 else 4
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 5:
                roles[i] = "q4"
                moved += 1
    return roles


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, 30 - day)
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    seeds = _b._m(private.get("seeds"))
    inventories = private.get("inventories", [])
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = max(1, int(stats.get("lands", 1) or 1))
    animals = int(stats.get("animals", 0) or 0)
    productive = int(stats.get("productive", 0) or 0)
    qs = stats["districts"]
    q1,q2,q3,q4 = (qs[i] for i in (1,2,3,4))
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}

    # Continuous monetization.  Only feed wheat is retained before liquidation.
    liquidate = day >= 24
    keep_wheat = 0 if liquidate else animals * 3
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = keep_wheat if item == "WHEAT" else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Small operating reserve only; late game converts rather than reinvests.
    reserve = 350 + 55 * animals + (250 if day < 20 else 500)
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q2_prod = int(q2.get("productive",0) or 0)
    q3_prod = int(q3.get("productive",0) or 0)
    q4_prod = int(q4.get("productive",0) or 0)
    q3_animals = int(q3.get("animals",0) or 0)

    # Land ROI is based on usable remaining crop cycles.  Expansion is early and
    # sequential; Q4 must still have enough horizon for at least one melon cycle.
    next_cost = {1:1000,2:2000,3:3000}.get(lands,10**9)
    setup = {1:350,2:650,3:900}.get(lands,0)
    land_ok = False
    if lands == 1:
        land_ok = day <= 7 and productive >= 9 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day <= 10 and q2_prod >= 8 and productive >= 24 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = day <= 13 and q3_prod >= 8 and productive >= 42 and money >= reserve + next_cost + setup
    cycles = max(0, horizon // 3)
    expected = cycles * (20 if lands < 3 else 18) * (95 if lands < 3 else 120)
    roi = (expected-next_cost-setup)/max(1,next_cost+setup)
    meta["ranked"].append(["land",round(roi,2)])
    if lands < 4 and land_ok and roi > 0.35 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable = max(0.0, spendable-next_cost)

    # Labour costs one coin in measured mechanics.  Hire early enough to commission
    # all districts, but stop adding bodies when remaining useful-action horizon is low.
    desired = 7 if lands == 1 else 11 if lands == 2 else 15 if lands == 3 else 18
    if day <= 16 and len(hands) < desired:
        add = min(3, desired-len(hands), 10-len(orders))
        for _ in range(add):
            orders.append(["HIRE"])
            meta["hires"] += 1
        spendable = max(0.0, spendable-add)
    meta["ranked"].append(["labour",float(max(0,horizon*150-1))])

    # Feed runway first.  Count carried wheat as well as shed stock.
    total_wheat = int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list):
        total_wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target = animals * 4
    if animals and total_wheat < feed_target and day < 26 and len(orders) < 10:
        need = min(24, feed_target-total_wheat)
        affordable = max(0,int(max(0.0,spendable-150)//10))
        buy = min(need,affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT","WHEAT",buy])
            meta["feed"] = buy
            spendable -= buy*10

    # Compact herd: six cows are enough to prove/use Q3 while preserving crop cash.
    if lands >= 3 and day <= 15 and len(orders) < 10:
        pasture = int(q3.get("pasture",0) or 0)
        in_shed = int(shed.get("COW",0) or 0)
        total = animals + in_shed
        target = 6
        capacity = max(0,min(pasture-total,target-total))
        croi = (max(0,horizon-2)*120-400)/400.0
        affordable = max(0,int(max(0.0,spendable-250)//400))
        buy = min(2,capacity,affordable)
        meta["ranked"].append(["cow",round(croi,2)])
        if buy > 0 and croi > 1.0:
            orders.append(["BUY_ANIMAL","COW",buy])
            meta["cows"] = buy
            spendable -= buy*400

    # Seed only crops that can mature before the conversion window.  Q1/Q2/Q4
    # are cash districts; Q3 spare acreage remains feed wheat.
    if day <= 20:
        need_by: Dict[str,int] = {}
        service_cap = max(16,(len(hands)+1)*5)
        remaining = service_cap
        for q in range(1,lands+1):
            if remaining <= 0:
                break
            z = qs[q]
            idle = int(z.get("idle",0) or 0)
            if q == 3:
                idle = min(idle,max(0,int(z.get("unlocked",0) or 0)-10))
            take = min(idle,remaining,24)
            remaining -= take
            crop = "WHEAT" if q == 3 else ("MELON" if day <= 14 else "WHEAT")
            need_by[crop] = need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10:
                break
            have = int(seeds.get(crop,0) or 0)
            need = max(0,min(30,raw+3)-have)
            cost = _b.SEED_COST[crop]
            affordable = max(0,int(max(0.0,spendable-180)//cost))
            buy = min(need,affordable)
            if buy > 0:
                orders.append(["BUY_SEED",crop,buy])
                meta["seeds"][crop] = buy
                spendable -= buy*cost

    # No discretionary capex after day 20; day 24+ is pure cash conversion.
    return orders[:10], meta


_b._roles = _roles
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any=None):
    return _v14.agent(observation,configuration)

def reset_state():
    return _v14.reset_state()

def reset_telemetry():
    return reset_state()

def get_telemetry(clear: bool=False):
    return _v14.get_telemetry(clear=clear)
