"""V33.78 committed-herd feed buffer over V33.76.

Single mechanism: protect enough wheat for the active + already-purchased herd and
buy a short feed runway before discretionary seed/animal orders. V33.76 is the
current economic parent; land timing, crop mix, mixed cow/sheep targets, worker
roles, pasture construction, sale pacing and Q4 suppression are otherwise
unchanged.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v76 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _committed_herd(farm: Mapping[str, Any], obs: Mapping[str, Any]) -> int:
    active = 0
    tiles = farm.get("tiles") or []
    if isinstance(tiles, list):
        for row in tiles:
            if not isinstance(row, list):
                continue
            for tile in row:
                if isinstance(tile, Mapping) and _b._kind(tile) == "PASTURE":
                    a = str(tile.get("animal", "")).upper()
                    if a in {"COW", "SHEEP"}:
                        active += 1
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    return active + int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0)


def _total_wheat(obs: Mapping[str, Any]) -> int:
    private = _b._m(obs.get("private"))
    shed = _b._m(private.get("shed"))
    total = int(shed.get("WHEAT", 0) or 0)
    inventories = private.get("inventories", [])
    if isinstance(inventories, list):
        total += sum(int(_b._m(inv).get("WHEAT", 0) or 0) for inv in inventories)
    return total


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    orders = [list(o) if isinstance(o, list) else o for o in orders]
    meta = dict(meta)
    day = int(obs.get("day", 0) or 0)
    money = float(farm.get("money", 0) or 0)
    committed = _committed_herd(farm, obs)
    total_wheat = _total_wheat(obs)

    # Five days of feed plus a small logistics buffer. This is deliberately
    # keyed to committed animals, not only animals already placed on pasture.
    floor = 0 if day >= 28 else committed * 5 + (8 if committed else 0)

    # Rewrite only wheat SELL orders so V33.76 cannot liquidate below the feed
    # floor during the compounding window. All other sale pacing is untouched.
    if floor > 0:
        remaining = total_wheat
        rewritten = []
        for o in orders:
            if isinstance(o, list) and len(o) >= 3 and str(o[0]).upper() == "SELL" and str(o[1]).upper() == "WHEAT":
                qty = max(0, int(o[2] or 0))
                safe = max(0, remaining - floor)
                sell = min(qty, safe)
                if sell > 0:
                    rewritten.append(["SELL", "WHEAT", sell])
                    remaining -= sell
                continue
            rewritten.append(o)
        orders = rewritten

    # Top up feed before discretionary seed/animal orders. Do not compete with
    # a land purchase in the same packet; preserve V33.76's capex sequencing.
    has_land = any(isinstance(o, list) and o and str(o[0]).upper() == "BUY_LAND" for o in orders)
    existing_buy = sum(int(o[2] or 0) for o in orders
                       if isinstance(o, list) and len(o) >= 3 and str(o[0]).upper() == "BUY_PRODUCT" and str(o[1]).upper() == "WHEAT")
    projected = total_wheat + existing_buy
    deficit = max(0, floor - projected)
    buy = 0
    if day <= 27 and committed > 0 and deficit > 0 and not has_land:
        price = float(_b._prices(obs).get("WHEAT", 25) or 25)
        reserve = 1000 + 70 * committed
        affordable = max(0, int(max(0.0, money - reserve) // max(1.0, price)))
        buy = min(deficit, affordable, 80)
        if buy > 0:
            # Guarantee a market slot by sacrificing a discretionary seed order,
            # never a sale, land, hire or existing feed order.
            if len(orders) >= 10:
                for j in range(len(orders) - 1, -1, -1):
                    o = orders[j]
                    if isinstance(o, list) and o and str(o[0]).upper() == "BUY_SEED":
                        orders.pop(j)
                        break
            if len(orders) < 10:
                idx = next((i for i, o in enumerate(orders)
                            if isinstance(o, list) and o and str(o[0]).upper() in {"BUY_ANIMAL", "BUY_SEED"}), len(orders))
                orders.insert(idx, ["BUY_PRODUCT", "WHEAT", buy])

    meta["v78_committed_herd"] = committed
    meta["v78_feed_floor"] = floor
    meta["v78_total_wheat"] = total_wheat
    meta["v78_feed_topup"] = buy
    return orders[:10], meta


# Patch allocator globals used by the V33.76 chain.
_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_p._p._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
