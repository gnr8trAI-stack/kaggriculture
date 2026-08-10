"""V33.7 frontier-shaped industrial allocator.

Independent V33 architecture (no V19/V32 parent).  This revision addresses the
measured V33.6 failure mode: land unlocked too late, Q3 pasture construction
overshot target while buying no animals, and labour was badly imbalanced across
Q1/Q2/Q4.  V33.7 uses a serial pasture builder, earlier serial land capex,
frontier-like daily labour, strawberry-heavy cash districts, a Q3 wheat/feed
strip, and staged 14-cow compounding with a small operating reserve.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial as _b

_b.HIRE_COST = 1


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    if day <= 22:
        return "STRAWBERRY"
    if day <= 26:
        return "MELON"
    return "WHEAT"


def _roles(lands: int, hand_count: int) -> List[str]:
    """Explicit district staffing; one Q3 builder prevents pasture overshoot."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        # Keep a real Q2 crew instead of starving it after Q4 unlock.
        for i in range(1, min(total, 4)):
            roles[i] = "q2"
    if lands >= 3:
        # One serial builder, service crew, and a feed/crop worker.
        if total >= 5:
            roles[-1] = "livestock_builder"
            roles[-2] = "livestock_service"
            roles[-3] = "livestock_service"
            roles[-4] = "feed"
    if lands >= 4:
        # Dedicated Q4 throughput while retaining Q2.
        q4_need = 2 if hand_count < 12 else 3
        assigned = 0
        for i in range(4, max(4, total - 4)):
            if assigned >= q4_need:
                break
            roles[i] = "q4"
            assigned += 1
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    tiles = farm.get("tiles") or []
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    hands = list(farm.get("hands") or [])
    if lands >= 3 and day <= 26 and role in {"livestock_builder", "livestock_service"}:
        target = 14
        q3_cells = int(stats["districts"][3].get("unlocked", 0) or 0)
        pasture_target = min(14, max(0, q3_cells - 8))
        # Service workers are forbidden from creating more pasture; only one
        # builder can grow infrastructure, eliminating V33.6's 30+ pasture leak.
        if role == "livestock_service":
            pasture_target = len(_b._pastures(tiles))
        r = _b._livestock_action(obs, farm, idx, p, reserved, target, pasture_target)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    horizon = max(0, 30 - day)
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    seeds = _b._m(private.get("seeds"))
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = int(stats.get("lands", 1) or 1)
    animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]
    orders: List[List[Any]] = []
    meta: Dict[str, Any] = {"land": 0, "hires": 0, "cows": 0, "feed": 0,
                            "seeds": {}, "sell_qty": 0, "reserve": 0.0,
                            "ranked": []}
    liquidate = day >= 28

    # Convert output to cash every market tick; frontier agents continuously sell
    # milk/wool/fertilizer/crops rather than accumulating inventory.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 4 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Hired hands cost one coin/day.  Frontier evidence is ~9 HIRE actions/day;
    # workforce therefore scales before expensive capex, not after it.
    desired = 8 if lands == 1 else 10 if lands == 2 else 12 if lands == 3 else 14
    if day <= 27:
        for _ in range(min(10 - len(orders), max(0, desired - len(hands)))):
            if money < 20:
                break
            orders.append(["HIRE"])
            meta["hires"] += 1
            money -= 1

    # Small solvency reserve only: feed + replant + execution buffer.
    reserve = 350 + animals * 45
    meta["reserve"] = reserve

    # Serial frontier timing: aim for Q2/Q3 by days 4/6 and Q4 only while a long
    # payback horizon remains.  Do not wait for the 12k cash gate from V33.6.
    earliest = {1: 4, 2: 6, 3: 9}.get(lands, 99)
    land_cost = 1000
    if lands < 4 and horizon >= 10 and day >= earliest and money >= land_cost + reserve and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        money -= land_cost

    # Feed is an operating obligation and must precede discretionary seed/cow buys.
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_target = animals * 4
    if animals > 0 and wheat < feed_target and len(orders) < 10:
        need = min(18, feed_target - wheat)
        affordable = max(0, int(max(0.0, money - reserve) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            money -= buy * 10

    # Stage cows as soon as Q3 pasture exists.  Frontier median is 13-14 animals
    # by day 15; keep purchase batches small so feed and crop cashflow remain live.
    if lands >= 3 and day <= 22 and len(orders) < 10:
        pastures = int(qs[3].get("pasture", 0) or 0)
        cow_total = animals + int(shed.get("COW", 0) or 0)
        target = 8 if day < 10 else 12 if day < 14 else 14
        capacity = max(0, min(pastures - cow_total, target - cow_total))
        affordable = max(0, int(max(0.0, money - reserve) // 400))
        buy = min(3, capacity, affordable)
        if buy > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            money -= 400 * buy

    # Working seed pool tracks actual idle surface rather than repeatedly buying
    # large speculative batches.  Q1/Q2/Q4 are strawberry-heavy; Q3 is wheat.
    if not liquidate and day <= 26:
        needs: Dict[str, int] = {}
        for q in range(1, 5):
            if int(qs[q].get("unlocked", 0) or 0) <= 4:
                continue
            idle = int(qs[q].get("idle", 0) or 0)
            if q == 3:
                pasture_target = 14
                idle = min(idle, max(0, int(qs[q].get("unlocked", 0) or 0) - 4 - pasture_target))
            crop = _crop_for(day, q, obs)
            needs[crop] = needs.get(crop, 0) + min(18, idle)
        for crop, raw in sorted(needs.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0) + int(meta["seeds"].get(crop, 0) or 0)
            target = min(30, max(6, raw + 4))
            need = max(0, target - have)
            affordable = max(0, int(max(0.0, money - reserve) // _b.SEED_COST[crop]))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                money -= buy * _b.SEED_COST[crop]

    return orders[:10], meta


_b._crop_for = _crop_for
_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator


def reset_state(): return _b.reset_state()
def reset_telemetry(): return _b.reset_telemetry()
def get_telemetry(clear: bool = False): return _b.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any = None): return _b.agent(observation, configuration)
