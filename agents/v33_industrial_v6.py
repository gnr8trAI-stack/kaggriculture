"""V33.6 staged-cashflow industrial architecture.

Independent V33 core, tuned from frontier replay economics rather than V19/V32.
The policy bootstraps with fast wheat, transitions Q1/Q2 into the replay-observed
strawberry-heavy midgame, reserves Q3 for pasture plus feed wheat, and treats Q4
as surplus-funded optional scale rather than an automatic purchase.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_industrial_v5 as _v5

_b = _v5._b
_b.HIRE_COST = 1


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    if district == 3:
        return "WHEAT"
    if day <= 5:
        return "WHEAT"
    if day <= 16:
        return "MELON" if district == 4 else "STRAWBERRY"
    if day <= 20:
        return "STRAWBERRY" if district in (1, 2) else "MELON"
    if day <= 25:
        return "CARROT"
    return "WHEAT"


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, _b.GAME_DAYS - day)
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    seeds = _b._m(private.get("seeds"))
    inventories = private.get("inventories", [])
    money = float(farm.get("money", 0) or 0)
    hands = list(farm.get("hands") or [])
    lands = int(stats.get("lands", 1) or 1)
    animals = int(stats.get("animals", 0) or 0)
    qs = stats["districts"]
    liquidate = day >= 26
    orders = []
    meta: Dict[str, Any] = {"land":0,"hires":0,"cows":0,"feed":0,"seeds":{},"sell_qty":0,"reserve":0.0,"ranked":[]}

    # Convert every realized output to cash immediately, retaining only feed wheat.
    total_carried_wheat = 0
    if isinstance(inventories, list):
        total_carried_wheat = sum(int(_b._m(inv).get("WHEAT", 0) or 0) for inv in inventories)
    keep_wheat = max(0, animals * 3 - total_carried_wheat) if not liquidate else 0
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        sell = max(0, qty - (keep_wheat if item == "WHEAT" else 0))
        if sell > 0:
            orders.append(["SELL", item, sell]); meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # Frontier action density is roughly 9 hires/day. Hires are one coin and temporary.
    desired = {1:7, 2:9, 3:11, 4:12}.get(lands, 7)
    reserve = 450 + 45 * animals
    meta["reserve"] = reserve
    spendable = max(0.0, money - reserve)
    if day <= 27 and len(hands) < desired:
        for _ in range(min(6, desired - len(hands))):
            if spendable < 2 or len(orders) >= 9:
                break
            orders.append(["HIRE"]); meta["hires"] += 1; spendable -= 1

    # Frontier land timing: first expansion ~d4-6, third land ~d6-10.
    # Q4 is rare in the replay frontier, so require genuine retained surplus.
    land_ok = False
    if lands == 1:
        land_ok = day >= 4 and int(qs[1]["productive"] or 0) >= 12 and money >= 2300
    elif lands == 2:
        land_ok = day >= 6 and (int(qs[1]["productive"] or 0) + int(qs[2]["productive"] or 0)) >= 26 and money >= 3200
    elif lands == 3:
        land_ok = day >= 10 and money >= 16000 and (int(qs[1]["productive"] or 0) + int(qs[2]["productive"] or 0)) >= 34
    if lands < 4 and horizon >= 9 and land_ok and spendable >= _b.LAND_COST + 250 and len(orders) < 10:
        orders.append(["BUY_LAND"]); meta["land"] = 1; spendable -= _b.LAND_COST

    # Seed the currently owned idle surface. Wheat compounds the opening quickly;
    # strawberry dominates the midgame footprint, matching frontier replays.
    if not liquidate:
        needs: Dict[str, int] = {}
        active = [1] + ([2] if lands >= 2 else []) + ([3] if lands >= 3 else []) + ([4] if lands >= 4 else [])
        for q in active:
            idle = int(qs[q].get("idle", 0) or 0)
            if q == 3:
                # Reserve 14 Q3 cells for pasture and use the remaining strip as feed crop.
                available_for_feed = max(0, int(qs[q].get("unlocked", 0) or 0) - 4 - 14 - int(qs[q].get("productive", 0) or 0))
                idle = min(idle, available_for_feed)
            crop = _crop_for(day, q, obs)
            needs[crop] = needs.get(crop, 0) + max(0, idle)
        for crop, raw_need in sorted(needs.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            if crop in {"STRAWBERRY", "MELON"} and day > 17:
                continue
            have = int(seeds.get(crop, 0) or 0) + int(meta["seeds"].get(crop, 0) or 0)
            need = max(0, min(30, raw_need + 3 - have))
            affordable = max(0, int(max(0.0, spendable - 200) // _b.SEED_COST[crop]))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy]); meta["seeds"][crop] = buy; spendable -= buy * _b.SEED_COST[crop]

    # Fill Q3 pasture as soon as physical capacity exists. Do not wait for a 12k
    # cash threshold; replay frontier has ~13 animals by day 15.
    if lands >= 3 and day <= 23 and horizon >= 5:
        q3 = qs[3]
        pastures = int(q3.get("pasture", 0) or 0)
        cow_total = animals + int(shed.get("COW", 0) or 0)
        target = 14 if lands == 3 else 18
        capacity = max(0, min(pastures - cow_total, target - cow_total))
        affordable = max(0, int(max(0.0, spendable - 350) // _b.COW_COST))
        buy = min(4, capacity, affordable)
        if buy > 0 and len(orders) < 10:
            orders.append(["BUY_ANIMAL", "COW", buy]); meta["cows"] = buy; spendable -= buy * _b.COW_COST

    # Feed is mandatory survival OPEX; carried wheat counts toward the reserve.
    wheat_total = int(shed.get("WHEAT", 0) or 0) + total_carried_wheat
    feed_need = max(0, animals * 3 - wheat_total)
    if feed_need > 0 and len(orders) < 10:
        buy = min(feed_need, max(0, int(max(0.0, spendable - 100) // 25)))
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy]); meta["feed"] = buy

    return orders[:10], meta


# V33.5 already patches maturity-gated harvest and inventory return into the
# independent V33 router. Replace only crop choice and capital allocation.
_b._crop_for = _crop_for
_b._capital_allocator = _capital_allocator


def reset_state(): return _b.reset_state()
def reset_telemetry(): return _b.reset_telemetry()
def get_telemetry(clear: bool=False): return _b.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any=None): return _b.agent(observation, configuration)
