"""V33.4 Industrial execution/economics correction.

This candidate layers only execution/economic corrections on the independent
V33 industrial core.  It does not import V19/V32.  The corrections are based on
the first clean V33.3 gate: capital intents were recorded but hires did not
execute after an immediate land purchase, and harvested inventory was repeatedly
revisited instead of being deposited/monetized.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial as _b

# Preserve independent core helpers before patching.
_base_unit_action = _b._unit_action


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    """Replay-informed production schedule.

    Earlier high-performing lineage used MELON through the main compounding
    window; late game switches to fast-turn crops.  Q3 remains wheat/feed.
    """
    if district == 3:
        return "WHEAT"
    if day <= 18:
        return "MELON"
    if day <= 24:
        return "CARROT"
    return "WHEAT"


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    private = _b._m(obs.get("private"))
    inv = _b._inventory(private, idx)
    load = _b._inv_total(inv)
    # The first V33.3 gate showed hundreds of repeated harvest attempts with no
    # realized revenue.  Monetize carried output before accepting another task.
    if load > 0:
        return _b._to_shed(farm.get("tiles") or [], p, ["DROP"]), "drop_inventory"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, _b.GAME_DAYS - day)
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    seeds = _b._m(private.get("seeds"))
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = int(stats.get("lands", 0) or 0)
    animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]
    orders = []
    meta: Dict[str, Any] = {"land": 0, "hires": 0, "cows": 0, "feed": 0,
                            "seeds": {}, "sell_qty": 0, "reserve": 0.0,
                            "ranked": []}

    liquidate = day >= 28
    # Convert all meaningful shed output to cash immediately; compounding is
    # more valuable than inventory batching during the growth window.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 3 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0:
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    reserve = 500 + 60 * len(hands) + 90 * animals
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)

    # Bootstrap labour BEFORE land.  V33.3 bought Q2 on step 1 and then never
    # successfully hired; four workers in Q1 create the first compounding engine.
    desired = {0: 3, 1: 4, 2: 7, 3: 11, 4: 15}.get(lands, 4)
    if horizon >= 3:
        for _ in range(min(2, max(0, desired - len(hands)))):
            if spendable < _b.HIRE_COST + 250 or len(orders) >= 10:
                break
            orders.append(["HIRE"])
            meta["hires"] += 1
            spendable -= _b.HIRE_COST

    # Seed working capital follows the role schedule.  Keep enough seeds for all
    # active workers so the farm does not stall between market turns.
    crop = _crop_for(day, 1, obs)
    target_seed = max(8, 3 * (len(hands) + meta["hires"] + 1))
    have = int(seeds.get(crop, 0) or 0)
    need = max(0, target_seed - have)
    affordable = max(0, int(max(0.0, spendable - 250) // _b.SEED_COST[crop]))
    buy = min(need, affordable)
    if buy > 0 and len(orders) < 10:
        orders.append(["BUY_SEED", crop, buy])
        meta["seeds"][crop] = buy
        spendable -= buy * _b.SEED_COST[crop]

    # Expansion is gated by an operating engine, but thresholds remain far below
    # the conservative V19/V32 cash gates because land costs only 1k and has a
    # long remaining payback window.
    q1p = int(qs[1]["productive"] or 0)
    q2p = int(qs[2]["productive"] or 0)
    thresholds = {1: 3200, 2: 5200, 3: 7800}
    productive_gate = (lands == 1 and q1p >= 10) or (lands == 2 and q2p >= 8) or (lands == 3 and int(qs[3]["productive"] or 0) >= 6)
    if lands < 4 and horizon >= 8 and productive_gate and money >= thresholds.get(lands, 999999) and spendable >= _b.LAND_COST + 350 and len(orders) < 10:
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        spendable -= _b.LAND_COST

    # Q3 livestock: pasture capacity is created by dedicated workers; cows are
    # purchased only against actual free pasture and sufficient reserve.
    if lands >= 3 and horizon >= 5:
        pastures = int(qs[3]["pasture"] or 0)
        cow_total = animals + int(shed.get("COW", 0) or 0)
        target_cows = min(14, max(6, (len(hands) + 1) // 2 + 2))
        cap = max(0, min(pastures - cow_total, target_cows - cow_total))
        affordable_cows = max(0, int(max(0.0, spendable - 300) // _b.COW_COST))
        cows = min(2, cap, affordable_cows)
        if cows > 0 and len(orders) < 10:
            orders.append(["BUY_ANIMAL", "COW", cows])
            meta["cows"] = cows
            spendable -= cows * _b.COW_COST

    # Mandatory feed reserve until Q3 wheat strip becomes self-sufficient.
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_need = max(0, animals * 3 - wheat)
    if feed_need > 0 and len(orders) < 10:
        feed_buy = min(feed_need, max(0, int(max(0.0, spendable - 150) // 25)))
        if feed_buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", feed_buy])
            meta["feed"] = feed_buy
            spendable -= 25 * feed_buy

    # Secondary seed pools for Q3 feed and Q4 late-scale production.
    for q in (2, 3, 4):
        if q > lands:
            continue
        district_crop = _crop_for(day, q, obs)
        idle = int(qs[q]["idle"] or 0)
        if q == 3:
            idle = min(idle, 10)  # rest of Q3 reserved for pasture
        have = int(seeds.get(district_crop, 0) or 0) + int(meta["seeds"].get(district_crop, 0) or 0)
        need = max(0, min(24, idle + 4 - have))
        affordable = max(0, int(max(0.0, spendable - 150) // _b.SEED_COST[district_crop]))
        buy = min(need, affordable)
        if buy > 0 and len(orders) < 10:
            orders.append(["BUY_SEED", district_crop, buy])
            meta["seeds"][district_crop] = int(meta["seeds"].get(district_crop, 0)) + buy
            spendable -= buy * _b.SEED_COST[district_crop]

    return orders[:10], meta


# Install corrections into the independent V33 core; its telemetry and role
# architecture remain the source of truth.
_b._crop_for = _crop_for
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator


def reset_state():
    return _b.reset_state()


def reset_telemetry():
    return _b.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _b.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None):
    return _b.agent(observation, configuration)
