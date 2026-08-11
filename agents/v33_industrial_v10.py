"""V33.10 bootstrap-to-frontier industrial allocator.

Independent V33 architecture.  This iteration fixes V33.9's largest measured
economic mistake: expensive strawberry working capital was being committed from
day zero, before the cheap wheat cash engine had financed land, labour and Q3.
The policy now bootstraps on wheat, converts Q1/Q2 to strawberry only after the
second land is productive, gives Q3 a fixed four-hand service floor, and buys Q4
only from realized surplus while remaining-horizon ROI is positive.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial as _b


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    # Cheap high-turn bootstrap first; frontier replay has large strawberry stock
    # by d15, not necessarily expensive strawberry seed spend at d0.
    if day <= 6:
        return "WHEAT"
    if day <= 20:
        return "STRAWBERRY"
    if day <= 23:
        return "MELON"
    return "WHEAT"


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3 and hand_count >= 7:
        # V34 isolation proved four active livestock workers can fully service
        # eight cows.  Use the same measured service ratio without importing its
        # V19 architecture.
        crew = min(5, max(4, hand_count // 3))
        for i in range(total - crew, total):
            roles[i] = "livestock"
        if total - crew - 1 >= 1:
            roles[total - crew - 1] = "feed"
    if lands >= 4 and hand_count >= 11:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 4:
                roles[i] = "q4"; moved += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    if role == "livestock" and lands >= 3 and day <= 26:
        q3 = stats["districts"][3]
        active = int(stats.get("animals", 0) or 0)
        target = 8 if day < 11 else 12 if day < 16 else 14
        target = max(active, target)
        q3_cells = int(q3.get("unlocked", 0) or 0)
        pasture_target = min(target, max(0, q3_cells - 8))
        r = _b._livestock_action(obs, farm, idx, p, reserved, target, pasture_target)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, 30 - day)
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed")); seeds = _b._m(private.get("seeds"))
    inventories = private.get("inventories", [])
    money = float(farm.get("money", 0) or 0); hands = list(farm.get("hands") or [])
    lands = max(1, int(stats.get("lands", 1) or 1)); animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]; productive = int(stats.get("productive", 0) or 0)
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}
    liquidate = day >= 28

    # Monetize continuously; preserve only one-day feed runway.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 3 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or item in {"MILK","WOOL","FERTILIZER"} or sell >= 2):
            orders.append(["SELL", item, sell]); meta["sell_qty"] += sell
            if len(orders) >= 10: return orders, meta

    # Only mandatory operating reserve.  Early bootstrap must reinvest aggressively.
    reserve = 350 + 45 * len(hands) + 55 * animals
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    # Serial land ladder.  Q2/Q3 are core industrial capital; Q4 remains surplus/ROI gated.
    next_cost = {1:1000,2:2000,3:3000}.get(lands,10**9)
    earliest = {1:3,2:5,3:9}.get(lands,99)
    min_prod = {1:10,2:22,3:38}.get(lands,10**9)
    setup = {1:500,2:900,3:1500}.get(lands,0)
    cycles = max(0, horizon // 3)
    expected = cycles * 16 * (55 if lands < 3 else 85)
    roi = (expected-next_cost-setup)/max(1,next_cost+setup); meta["ranked"].append(["land",round(roi,2)])
    fourth_surplus_ok = lands < 3 or money >= next_cost + reserve + setup + 2500
    if lands < 4 and day >= earliest and horizon >= 8 and productive >= min_prod and roi > 0 and fourth_surplus_ok and spendable >= next_cost + setup and len(orders)<10:
        orders.append(["BUY_LAND"]); meta["land"] = 1; spendable -= next_cost

    # Labour follows actual productive base, with enough Q3 service capacity.
    desired = 5 if lands == 1 else 8 if lands == 2 else 12 if lands == 3 else 16
    if lands >= 3: desired = max(desired, 8 + max(0, animals-6)//2)
    desired = min(17, desired)
    lroi = (horizon*135-500)/500.0; meta["ranked"].append(["labour",round(lroi,2)])
    if day <= 24 and lroi > 0:
        for _ in range(min(2,max(0,desired-len(hands)))):
            if spendable < 650 or len(orders)>=10: break
            orders.append(["HIRE"]); meta["hires"] += 1; spendable -= 500

    # Feed includes carried wheat.
    total_wheat = int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list): total_wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target = animals * 4
    if animals and total_wheat < feed_target and day < 28 and len(orders)<10:
        need = min(36, feed_target-total_wheat)
        affordable = max(0,int(max(0.0,spendable-100)//10)); buy=min(need,affordable)
        if buy>0: orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*10

    # Q3 cow batches against already-built pasture.  Four-worker floor keeps activation caught up.
    if lands>=3 and day<=23 and len(orders)<10:
        q3=qs[3]; pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0)
        target=8 if day<11 else 12 if day<16 else 14; total=animals+in_shed
        capacity=max(0,min(pasture-total,target-total)); croi=(max(0,horizon-2)*120-400)/400.0; meta["ranked"].append(["cow",round(croi,2)])
        affordable=max(0,int(max(0.0,spendable-250)//400)); buy=min(4,capacity,affordable)
        if buy>0 and croi>0: orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    # Seed working capital after structural investments.  Cheap wheat bootstrap avoids V33.9's
    # early strawberry cash sink; then Q1/Q2/Q4 converge toward replay-like strawberry density.
    if not liquidate and day<=26:
        need_by: Dict[str,int] = {}
        for q in range(1,5):
            z=qs[q]
            if int(z.get("unlocked",0) or 0)<=4: continue
            idle=int(z.get("idle",0) or 0)
            if q==3:
                pt=8 if day<11 else 12 if day<16 else 14
                idle=min(idle,max(0,int(z.get("unlocked",0) or 0)-4-pt))
            crop=_crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+min(28,idle)
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10: break
            have=int(seeds.get(crop,0) or 0); pool=min(36,max(6,raw+4)); need=max(0,pool-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-75)//cost)); buy=min(need,affordable)
            if buy>0: orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost
    return orders[:10],meta


_b._crop_for=_crop_for
_b._roles=_roles
_b._unit_action=_unit_action
_b._capital_allocator=_capital_allocator

def reset_state(): return _b.reset_state()
def reset_telemetry(): return _b.reset_telemetry()
def get_telemetry(clear: bool=False): return _b.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any=None): return _b.agent(observation, configuration)
