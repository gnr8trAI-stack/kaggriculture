"""V33.17 measured-cost labour on the maturity-safe V33.14 architecture.

Independent V33 architecture.  V33.15 proved that harvesting merely because
`yield_units > 0` destroys crop economics; V33.17 therefore returns to V33.14's
maturity-aware service logic.  The only major economic correction is measured
labour cost: hands cost 1 coin and up to three can be hired in a market packet.
Earlier V33 allocators priced a hand at 500 and systematically starved every
unlocked district of service throughput.

V19.2 remains an external benchmark control only.
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
    if lands >= 3 and hand_count >= 10:
        crew = 4 if hand_count < 14 else 5
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        feed_i = total - crew - 1
        if feed_i >= 1:
            roles[feed_i] = "feed"
    if lands >= 4 and hand_count >= 14:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 4:
                roles[i] = "q4"; moved += 1
    return roles


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
    liquidate = day >= 27

    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 4 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (liquidate or item in {"MILK","WOOL","FERTILIZER"} or sell >= 2):
            orders.append(["SELL", item, sell]); meta["sell_qty"] += sell
            if len(orders) >= 10: return orders, meta

    # Actual hand capex is negligible; reserve is feed/reseed/runway only.
    reserve = 600 + 90 * animals
    if day >= 20: reserve += 450
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    q1,q2,q3,q4 = (qs[i] for i in (1,2,3,4))
    q2_prod = int(q2.get("productive",0) or 0); q3_prod = int(q3.get("productive",0) or 0); q3_animals = int(q3.get("animals",0) or 0)

    next_cost = {1:1000,2:2000,3:3000}.get(lands,10**9)
    setup = {1:450,2:800,3:1300}.get(lands,0)
    land_ok = False
    if lands == 1:
        land_ok = day >= 3 and horizon >= 14 and productive >= 10 and money >= reserve + next_cost + setup
    elif lands == 2:
        land_ok = day >= 6 and horizon >= 12 and q2_prod >= 10 and productive >= 28 and money >= reserve + next_cost + setup
    elif lands == 3:
        land_ok = (day >= 11 and horizon >= 9 and q3_prod >= 10 and q3_animals >= 8 and productive >= 46
                   and money >= reserve + next_cost + setup + 800)
    cycles = max(0,horizon//3); expected = cycles*(18 if lands<3 else 16)*(80 if lands<3 else 105)
    roi=(expected-next_cost-setup)/max(1,next_cost+setup); meta["ranked"].append(["land",round(roi,2)])
    if lands < 4 and land_ok and roi > 0 and len(orders) < 10:
        orders.append(["BUY_LAND"]); meta["land"]=1; spendable=max(0.0,spendable-next_cost)

    # Cheap labour is the first commissioning investment after any land order.
    desired = 8 if lands == 1 else 12 if lands == 2 else 16 if lands == 3 else 20
    hires_today = int(farm.get("hires_today",0) or 0)
    add = min(max(0,3-hires_today), max(0,desired-len(hands)), max(0,10-len(orders)))
    for _ in range(add): orders.append(["HIRE"]); meta["hires"] += 1
    spendable=max(0.0,spendable-add)
    meta["ranked"].append(["labour",float(max(0,horizon*120-1))])

    total_wheat=int(shed.get("WHEAT",0) or 0)
    if isinstance(inventories,list): total_wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in inventories)
    feed_target=animals*5
    if animals and total_wheat < feed_target and day < 27 and len(orders)<10:
        need=min(30,feed_target-total_wheat); affordable=max(0,int(max(0.0,spendable-200)//10)); buy=min(need,affordable)
        if buy>0: orders.append(["BUY_PRODUCT","WHEAT",buy]); meta["feed"]=buy; spendable-=buy*10

    if lands>=3 and day<=22 and len(orders)<10:
        pasture=int(q3.get("pasture",0) or 0); in_shed=int(shed.get("COW",0) or 0); target=8 if day<14 else 12
        total=animals+in_shed; capacity=max(0,min(pasture-total,target-total)); croi=(max(0,horizon-2)*120-400)/400.0
        meta["ranked"].append(["cow",round(croi,2)]); affordable=max(0,int(max(0.0,spendable-300)//400)); buy=min(2,capacity,affordable)
        if buy>0 and croi>0: orders.append(["BUY_ANIMAL","COW",buy]); meta["cows"]=buy; spendable-=buy*400

    if not liquidate and day<=25:
        need_by: Dict[str,int]={}; service_cap=max(12,(len(hands)+1)*4); remaining=service_cap
        for q in range(1,lands+1):
            if remaining<=0: break
            z=qs[q]; idle=int(z.get("idle",0) or 0)
            if q==3:
                pasture_target=8 if day<14 else 12
                idle=min(idle,max(0,int(z.get("unlocked",0) or 0)-4-pasture_target))
            take=min(idle,remaining,25); remaining-=take; crop=_v14._crop_for(day,q,obs); need_by[crop]=need_by.get(crop,0)+take
        for crop,raw in sorted(need_by.items(),key=lambda kv:-kv[1]):
            if len(orders)>=10: break
            have=int(seeds.get(crop,0) or 0); need=max(0,min(28,raw+4)-have); cost=_b.SEED_COST[crop]
            affordable=max(0,int(max(0.0,spendable-250)//cost)); buy=min(need,affordable)
            if buy>0: orders.append(["BUY_SEED",crop,buy]); meta["seeds"][crop]=buy; spendable-=buy*cost
    return orders[:10],meta


_b._roles=_roles
_b._capital_allocator=_capital_allocator


def agent(observation: Any, configuration: Any=None): return _v14.agent(observation,configuration)
def reset_state(): return _v14.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _v14.get_telemetry(clear=clear)
