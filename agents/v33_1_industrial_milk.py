"""V33.1 Industrial Milk Compounder.

Replay-driven correction to V33 alpha1:
- fixes the off-by-one land cost ladder (1 owned -> next land costs 1000);
- treats land, labour and cows as one compounding capacity system;
- scales to all four quadrants while sufficient horizon remains;
- builds SW as an industrial cow/milk district;
- raises labour/cow ceilings substantially versus V19/V32 boutique operation;
- continuously converts milk/output to cash and reinvests.

The routing/service engine remains V33 Industrial; this module replaces the
capital allocator only so the economic experiment is isolated and measurable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple
from agents import v33_industrial as _v33


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _market(obs: Mapping[str, Any], farm: Mapping[str, Any], stats: Mapping[str, Any], day: int, hour: int) -> Tuple[List[List[Any]], Dict[str, int]]:
    private = _m(obs.get("private"))
    shed = _m(private.get("shed"))
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    orders: List[List[Any]] = []
    meta = {"land": 0, "hire": 0, "animals": 0, "seed_spend_proxy": 0, "feed": 0, "sell_qty": 0}
    liquidate = day >= 28

    q3 = stats["districts"][3]
    animal_count = int(q3.get("animals", 0) or 0)

    # 1) Revenue first. Milk is the industrial cash engine; sell in small batches
    # rather than letting output sit idle. Keep only feed wheat runway.
    for product in _v33.SELLABLE:
        qty = int(shed.get(product, 0) or 0)
        keep = animal_count * 4 if product == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        threshold = 1 if product == "MILK" else 3
        if sell >= threshold or (liquidate and sell > 0):
            orders.append(["SELL", product, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    lands = int(stats.get("lands", 1) or 1)
    horizon = max(0, 30 - day)

    # Correct next-land costs. V33 alpha1 incorrectly charged one tier too high.
    next_land_cost = {1: 1000, 2: 2000, 3: 3000}.get(lands, 10**9)

    # Operating reserve is deliberately modest early; idle land has a very high
    # opportunity cost when 10+ days remain. Expansion target: Q2 by ~d5, Q3 by
    # ~d9, Q4 by ~d13 if cash flow supports it.
    operating = 450 + 90 * len(hands) + 65 * animal_count
    earliest = {1: 3, 2: 6, 3: 9}.get(lands, 99)
    min_horizon = {1: 18, 2: 14, 3: 10}.get(lands, 99)
    if lands < 4 and day >= earliest and horizon >= min_horizon and money >= next_land_cost + operating and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        money -= next_land_cost

    # Labour is productive capacity, not a cost to minimize. Scale by unlocked
    # acreage and livestock burden. Cap 20 to remain manageable by router.
    unlocked = sum(int(v.get("unlocked", 0) or 0) for v in stats["districts"].values())
    acreage_need = max(4, (unlocked + 4) // 6)
    livestock_need = (animal_count + 1) // 2
    desired_hands = min(20, max(acreage_need, 5 + livestock_need))
    hire_budget_floor = 700 + max(0, next_land_cost if lands < 4 and horizon >= min_horizon else 0)
    hires = min(3, max(0, desired_hands - len(hands)))
    for _ in range(hires):
        if money < hire_budget_floor or len(orders) >= 10:
            break
        orders.append(["HIRE"])
        meta["hire"] += 1
        money -= 500

    # Feed survival before more animals.
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_target = animal_count * 5
    feed_need = max(0, feed_target - wheat)
    if animal_count > 0 and feed_need > 0 and money >= 350 and len(orders) < 10:
        orders.append(["BUY_PRODUCT", "WHEAT", feed_need])
        meta["feed"] += feed_need
        money -= feed_need * 10  # conservative budgeting proxy only

    # Industrial cow ladder. Once SW exists, convert available pastures into milk
    # capacity aggressively. Target grows with land and remaining horizon.
    cow_target = 0
    if lands >= 3 and day <= 24:
        cow_target = 10 if lands == 3 else 16
        if day <= 16 and lands >= 4:
            cow_target = 20
    cow_total = animal_count + int(shed.get("COW", 0) or 0)
    pasture_count = int(q3.get("pasture", 0) or 0)
    empty_capacity = max(0, pasture_count - cow_total)
    if cow_target > cow_total and empty_capacity > 0 and len(orders) < 10:
        affordable = max(0, int((money - 700) // 400))
        buy = min(4, cow_target - cow_total, empty_capacity, affordable)
        if buy > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["animals"] += buy
            money -= 400 * buy

    # Keep all crop districts seeded; once 4 lands are owned favour MELON for the
    # late high-value crop engine while Q3 produces milk.
    crop = _v33._crop(day, 4 if lands >= 4 else 2 if lands >= 2 else 1)
    seeds = _m(private.get("seeds"))
    have = int(seeds.get(crop, 0) or 0)
    empty_crop = sum(int(stats["districts"][q].get("empty", 0) or 0) for q in (1, 2, 4))
    target = min(40, max(8, empty_crop + len(hands)))
    need = max(0, target - have)
    if not liquidate and need > 0 and money >= 300 and len(orders) < 10:
        orders.append(["BUY_SEED", crop, need])
        meta["seed_spend_proxy"] += need

    return orders[:10], meta


_v33._market = _market


def reset_state() -> None:
    _v33.reset_state()


def reset_telemetry() -> None:
    _v33.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v33.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    return _v33.agent(observation, configuration)
