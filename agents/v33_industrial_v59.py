"""V33.59 dairy-first four-district industrial allocator.

V33.58 finally commissioned Q3 reliably, but 24-game telemetry still plateaued
near 32k: only five geese were active, Q4 never opened, and ~60 owned tiles were
idle at peak. V33.59 changes the production mechanism rather than another cash
threshold tweak:

* keep V58's fast Q1/Q2 liquidity bridge and proven zero-invalid executor;
* commission pasture capacity before coop capacity in Q3/Q4;
* prefer cows (higher steady-state revenue/tile than geese) while runway is long;
* treat Q4 as productive capital once the crop engine can finance it, rather
  than waiting for Q3 biological output to mature first;
* retain operating/feed reserve and stage biological capex to avoid starvation.

V19/V32 remain reference controls only; this is still the independent V33 line.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v58 as _p
from agents import v33_industrial_v45 as _core

_b = _p._b
_parent_allocator = _p._capital_allocator
_parent_livestock = _core._livestock_action


def _pending(obs: Mapping[str, Any], item: str) -> int:
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    n = int(shed.get(item, 0) or 0)
    invs = private.get("inventories", [])
    if isinstance(invs, list):
        n += sum(int(_b._m(inv).get(item, 0) or 0) for inv in invs)
    return n


def _quoted_sales(obs, orders):
    prices = _b._prices(obs); total = 0.0
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            item = str(o[1]).upper()
            total += int(o[2]) * float(prices.get(item, _b.VALUE.get(item, 1)) or _b.VALUE.get(item, 1))
    return total


def _land_packet(orders):
    out = [list(o) for o in orders if isinstance(o, list) and o and o[0] == "SELL"]
    out.append(["BUY_LAND"])
    return out[:10]


def _nearest_empty(tiles, district, reserved):
    goals = _b._empty_targets(tiles, {district}, reserved)
    if not goals: return None
    best = None
    for g in goals:
        rr = _b._route(tiles, g if False else (0,0), g)  # never used; preserve import contract
        # actual routing is chosen by the parent helper below
        break
    return goals


def _livestock_action(obs, farm, idx, p, stats, reserved, district: int):
    """Pasture-first commissioning before delegating to the proven service loop."""
    day = int(obs.get("day", 0) or 0); tiles = farm.get("tiles") or []
    q = stats["districts"][district]
    past = int(q.get("pasture", 0) or 0); coops = int(q.get("coop", 0) or 0)
    # Industrial dairy footprint: Q3 14 pasture + 8 coop, Q4 10 pasture + 10 coop.
    pasture_target = 14 if district == 3 else 10
    if day <= 18 and past < pasture_target:
        goals = _b._empty_targets(tiles, {district}, reserved)
        best = None
        for g in goals:
            rr = _b._route(tiles, p, g)
            if rr is None: continue
            cand = (rr[0], g[1], g[0], g, rr[1])
            if best is None or cand < best: best = cand
        if best is not None:
            g = best[3]; reserved.add(g)
            if p == g: return ["BUILD_PASTURE"], "build_pasture_v59"
            return [best[4]], "move_build_pasture_v59"
    return _parent_livestock(obs, farm, idx, p, stats, reserved, district)


# Patch the executing core module; wrappers ultimately delegate into this module.
_core._livestock_action = _livestock_action
_b._livestock_action = _livestock_action


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats); meta = dict(meta)
    day = int(obs.get("day", 0) or 0); horizon = max(0, 30-day)
    lands = max(1, int(stats.get("lands", 1) or 1)); money = float(farm.get("money", 0) or 0)
    hands = len(list(farm.get("hands") or [])); qs = stats["districts"]
    q1,q2,q3,q4 = (qs[i] for i in (1,2,3,4))
    prod12 = int(q1.get("productive",0) or 0) + int(q2.get("productive",0) or 0)
    idle12 = int(q1.get("idle",0) or 0) + int(q2.get("idle",0) or 0)
    animals = int(stats.get("animals",0) or 0)
    clean = [list(o) for o in orders if isinstance(o,list) and o and o[0] not in {"BUY_LAND","BUY_ANIMAL"}][:10]
    realizable = money + 0.90*_quoted_sales(obs, clean)
    reserve = 300 + 45*animals
    meta["allocator_v59"] = {"lands":lands,"prod12":prod12,"idle12":idle12,"hands":hands,
                             "animals":animals,"realizable":round(realizable,1),"reserve":reserve,"horizon":horizon}

    # Preserve V58's proven Q3 liquidity bridge.
    if lands == 2 and 5 <= day <= 18 and horizon >= 12:
        need = 2000 + reserve
        roi_proxy = horizon*(max(0,prod12)*22.0 + 650.0)
        if prod12 >= 24 and idle12 <= 24 and realizable >= need and roi_proxy >= need*4:
            meta["district_commission_v59"]={"district":3,"required":round(need,1),"realizable":round(realizable,1),"roi_proxy":round(roi_proxy,1)}
            return _land_packet(clean), meta

    # Q4 is judged as land ROI, not gated on slow biological maturity. Once Q1/Q2
    # are still healthy and the 4k purchase leaves feed reserve, buy the district.
    if lands == 3 and 10 <= day <= 22 and horizon >= 8:
        need = 4000 + reserve + 350
        q3_prod = int(q3.get("productive",0) or 0)
        roi_proxy = horizon*(max(0,prod12)*18.0 + max(0,q3_prod)*42.0 + 700.0)
        if prod12 >= 24 and q3_prod >= 8 and hands >= 7 and realizable >= need and roi_proxy >= need*2.5:
            meta["district_commission_v59"]={"district":4,"required":round(need,1),"realizable":round(realizable,1),
                                              "q3_productive":q3_prod,"roi_proxy":round(roi_proxy,1)}
            return _land_packet(clean), meta

    if lands < 3 or day >= 24:
        return orders[:10], meta

    private = _b._m(obs.get("private")); prices = _b._prices(obs)
    q3_past = int(q3.get("pasture",0) or 0); q4_past = int(q4.get("pasture",0) or 0) if lands >= 4 else 0
    cow_total = int(stats.get("cows",0) or 0) + _pending(obs,"COW")
    goose_total = int(stats.get("geese",0) or 0) + _pending(obs,"GOOSE")
    cow_free = max(0, q3_past + q4_past - cow_total)

    # Stage dairy aggressively enough to matter, but never consume the crop/feed reserve.
    target_cows = 0
    if prod12 >= 24 and idle12 <= 22:
        target_cows = 6 if lands == 3 else 10
        if day <= 16 and hands >= 9: target_cows = 12 if lands == 3 else 18
        if lands == 4 and prod12 >= 30 and hands >= 10 and day <= 18: target_cows = 22

    committed = 0.0
    for o in clean:
        if len(o) < 3: continue
        if o[0] == "BUY_SEED": committed += _core.SEED_COST.get(str(o[1]).upper(),0)*int(o[2])
        elif o[:2] == ["BUY_PRODUCT","WHEAT"]: committed += float(prices.get("WHEAT",25) or 25)*int(o[2])
    spendable = max(0.0, realizable-reserve-committed)
    buy_cows = min(3, cow_free, max(0,target_cows-cow_total), max(0,int(spendable//400)))
    if buy_cows > 0 and len(clean) < 10:
        i=0
        while i < len(clean) and clean[i][0] == "SELL": i += 1
        clean.insert(i,["BUY_ANIMAL","COW",buy_cows]); clean=clean[:10]
        spendable -= 400*buy_cows
        meta["dairy_stage_v59"]={"target":target_cows,"buy":buy_cows,"capacity":q3_past+q4_past,"spendable_after":round(spendable,1)}

    # Keep a small goose tranche only after dairy is operating; it diversifies daily
    # cash without consuming pasture capacity.
    coop_capacity = int(q3.get("coop",0) or 0) + (int(q4.get("coop",0) or 0) if lands >= 4 else 0)
    goose_free = max(0, coop_capacity-goose_total)
    if cow_total >= 6 and goose_free > 0 and day <= 18 and spendable >= 300 and len(clean) < 10:
        clean.append(["BUY_ANIMAL","GOOSE",1])
        meta["goose_sidecar_v59"]={"buy":1,"capacity":coop_capacity}

    # Five-day feed runway for the staged herd.
    shed = _b._m(private.get("shed")); invs = private.get("inventories",[])
    wheat = int(shed.get("WHEAT",0) or 0)
    if isinstance(invs,list): wheat += sum(int(_b._m(x).get("WHEAT",0) or 0) for x in invs)
    projected_animals = animals + buy_cows + (1 if "goose_sidecar_v59" in meta else 0)
    desired_feed = projected_animals*5
    already = sum(int(o[2]) for o in clean if len(o)>=3 and o[:2]==["BUY_PRODUCT","WHEAT"])
    gap=max(0,desired_feed-wheat-already)
    if gap>0 and len(clean)<10:
        wp=float(prices.get("WHEAT",25) or 25)
        affordable=max(0,int(max(0.0,realizable-committed-reserve)//max(1.0,wp)))
        qty=min(50,gap,affordable)
        if qty>0: clean.append(["BUY_PRODUCT","WHEAT",qty]); meta["feed_topup_v59"]=qty

    return clean[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None): return _p.agent(observation, configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
def industrial_peaks(): return _p.industrial_peaks()
