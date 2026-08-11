"""V33.8 ROI-balanced industrial allocator.

Independent V33 architecture.  This revision is built around the V33 spec rather
than inherited V19 behaviour: explicit four-district labour allocation, serial
land ROI, Q3 livestock/feed throughput, Q4 late-scale crops, a small operating
reserve and reinvestment-first market ordering.
"""
from __future__ import annotations
from typing import Any, Dict, List, Mapping
from agents import v33_industrial as _b

# Kaggriculture hired hands are cheap recurring capacity in the observed engine.
_b.HIRE_COST = 1


def _crop_for(day: int, district: int, obs: Mapping[str, Any]) -> str:
    # Replay frontier: strawberry-heavy midgame, wheat feed strip in Q3, then
    # short-horizon liquidation crops.  Avoid speculative long-cycle planting late.
    if district == 3:
        return "WHEAT"
    if day <= 20:
        return "STRAWBERRY"
    if day <= 24:
        return "MELON"
    return "WHEAT"


def _roles(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        # 30-ish crop cells need more than token coverage.
        for i in range(1, min(total, 5)):
            roles[i] = "q2"
    if lands >= 3:
        # Q3 gets one pasture builder plus service/feed capacity.  Builder remains
        # unique to prevent the pasture overshoot observed in V33.6.
        if total >= 6:
            roles[-1] = "livestock_builder"
            roles[-2] = "livestock_service"
            roles[-3] = "livestock_service"
            roles[-4] = "feed"
    if lands >= 4:
        # Reserve 3-4 workers for Q4 once unlocked, but never steal the unique Q3 builder.
        q4_need = 3 if hand_count < 14 else 4
        candidates = [i for i in range(5, max(5, total - 4))]
        for i in candidates[:q4_need]:
            roles[i] = "q4"
    return roles


_base_unit_action = _b._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    day = int(obs.get("day", 0) or 0)
    lands = int(stats.get("lands", 0) or 0)
    tiles = farm.get("tiles") or []
    if lands >= 3 and day <= 25 and role in {"livestock_builder", "livestock_service"}:
        q3 = stats["districts"][3]
        q3_cells = int(q3.get("unlocked", 0) or 0)
        active = int(stats.get("animals", 0) or 0)
        # Build only enough pasture to stage the next cow batch.  Preserve 8-10 Q3
        # cells for wheat/feed throughput rather than paving the district with pasture.
        target = 8 if day < 10 else 12 if day < 14 else 14
        target = max(active, target)
        pasture_target = min(target, max(0, q3_cells - 9))
        if role == "livestock_service":
            pasture_target = len(_b._pastures(tiles))
        r = _b._livestock_action(obs, farm, idx, p, reserved, target, pasture_target)
        if r is not None:
            return r
        role = "feed"
    return _base_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


def _capital_allocator(obs, farm, stats):
    day = int(obs.get("day", 0) or 0)
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

    # 1) Monetize realized output immediately.  Keep only feed wheat.
    for item in _b.SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        keep = animals * 4 if item == "WHEAT" and not liquidate else 0
        sell = max(0, qty - keep)
        if sell > 0 and (item in {"MILK", "WOOL", "FERTILIZER"} or sell >= 2 or liquidate):
            orders.append(["SELL", item, sell])
            meta["sell_qty"] += sell
            if len(orders) >= 10:
                return orders, meta

    # 2) Operating reserve = feed + near-term replant + small execution buffer.
    reserve = 250 + animals * 50 + max(0, lands - 1) * 75
    meta["reserve"] = reserve

    # 3) Labour before land setup: frontier replays show large workforces supporting
    # ~60 crops and ~14 animals.  Recurring hire cost is tiny in this environment.
    desired = 7 if lands == 1 else 10 if lands == 2 else 13 if lands == 3 else 16
    if day <= 26:
        missing = max(0, desired - len(hands))
        for _ in range(min(missing, 4, 10 - len(orders))):
            if money <= reserve + 5:
                break
            orders.append(["HIRE"])
            meta["hires"] += 1
            money -= 1

    # 4) Land is productive capital.  Serial early unlocks target Q2/Q3 by ~d6-9;
    # Q4 requires enough horizon and cash for setup, but not an arbitrary 15k gate.
    land_cost = 1000
    earliest = {1: 3, 2: 5, 3: 8}.get(lands, 99)
    setup = {1: 550, 2: 850, 3: 1200}.get(lands, 0)
    cycles_left = horizon // 3
    land_roi_proxy = cycles_left * 18 * 70 - (land_cost + setup)
    meta["ranked"].append(["land", round(land_roi_proxy / max(1, land_cost + setup), 2)])
    if (lands < 4 and day >= earliest and horizon >= 9 and land_roi_proxy > 0
            and money >= land_cost + setup + reserve and len(orders) < 10):
        orders.append(["BUY_LAND"])
        meta["land"] = 1
        money -= land_cost

    # 5) Feed obligation before livestock capex.
    total_wheat = int(shed.get("WHEAT", 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        total_wheat += sum(int(_b._m(x).get("WHEAT", 0) or 0) for x in invs)
    feed_target = animals * 5
    if animals > 0 and total_wheat < feed_target and day < 28 and len(orders) < 10:
        need = min(24, feed_target - total_wheat)
        affordable = max(0, int(max(0.0, money - reserve) // 10))
        buy = min(need, affordable)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy])
            meta["feed"] = buy
            money -= buy * 10

    # 6) Stage livestock only against built pasture capacity.  Target frontier shape:
    # 8 animals early Q3, 12 by d14, 14 thereafter; keep cashflow alive between batches.
    if lands >= 3 and day <= 23 and len(orders) < 10:
        q3 = qs[3]
        pasture = int(q3.get("pasture", 0) or 0)
        in_shed = int(shed.get("COW", 0) or 0)
        target = 8 if day < 10 else 12 if day < 14 else 14
        cow_total = animals + in_shed
        capacity = max(0, min(pasture - cow_total, target - cow_total))
        affordable = max(0, int(max(0.0, money - reserve) // 400))
        buy = min(4, capacity, affordable)
        cow_roi_proxy = max(0, horizon - 2) * 110 - 400
        meta["ranked"].append(["cow", round(cow_roi_proxy / 400.0, 2)])
        if buy > 0 and cow_roi_proxy > 0:
            orders.append(["BUY_ANIMAL", "COW", buy])
            meta["cows"] = buy
            money -= 400 * buy

    # 7) Refill only enough seed inventory to occupy observed idle crop capacity.
    if not liquidate and day <= 26:
        need_by_crop: Dict[str, int] = {}
        for q in range(1, 5):
            z = qs[q]
            if int(z.get("unlocked", 0) or 0) <= 4:
                continue
            idle = int(z.get("idle", 0) or 0)
            if q == 3:
                # Q3 crop strip is residual capacity after the livestock target.
                target_pasture = 8 if day < 10 else 12 if day < 14 else 14
                crop_capacity = max(0, int(z.get("unlocked", 0) or 0) - 4 - target_pasture)
                idle = min(idle, crop_capacity)
            crop = _crop_for(day, q, obs)
            need_by_crop[crop] = need_by_crop.get(crop, 0) + min(20, idle)

        for crop, raw in sorted(need_by_crop.items(), key=lambda kv: -kv[1]):
            if len(orders) >= 10:
                break
            have = int(seeds.get(crop, 0) or 0)
            target_pool = min(36, max(5, raw + 3))
            need = max(0, target_pool - have)
            cost = _b.SEED_COST[crop]
            affordable = max(0, int(max(0.0, money - reserve) // cost))
            buy = min(need, affordable)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                meta["seeds"][crop] = buy
                money -= buy * cost

    return orders[:10], meta


_b._crop_for = _crop_for
_b._roles = _roles
_b._unit_action = _unit_action
_b._capital_allocator = _capital_allocator


def reset_state(): return _b.reset_state()
def reset_telemetry(): return _b.reset_telemetry()
def get_telemetry(clear: bool = False): return _b.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any = None): return _b.agent(observation, configuration)
