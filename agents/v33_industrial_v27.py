"""V33.27 balanced four-quadrant compounding.

Independent V33 industrial lineage. V33.25 is the economic control: its
market-aware crop engine was the first V33 to beat V19.2 consistently. This
candidate keeps that engine, caps the serviceable herd, and spends Q3 surplus
on an ROI-positive Q4 crop district instead of waiting for an oversized herd.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v25 as _v25

_b = _v25._b
_base_allocator = _v25._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _base_allocator(obs, farm, stats)
    day = int(obs.get("day", 0) or 0)
    horizon = max(0, 30-day)
    lands = max(1, int(stats.get("lands", 1) or 1))
    money = float(farm.get("money", 0) or 0)
    private = _b._m(obs.get("private")); shed = _b._m(private.get("shed"))
    animals = int(stats.get("animals", 0) or 0)
    total_animals = animals + int(shed.get("COW", 0) or 0)
    qs = stats["districts"]; q3 = qs[3]

    # Seven to eight cows were the stable/economic V33.25 regime. Clamp market
    # purchases rather than paying for a herd the service topology cannot keep
    # productive. Q3 remains the livestock/feed district.
    cleaned = []
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "BUY_ANIMAL" and o[1] == "COW":
            room = max(0, 8-total_animals)
            qty = min(room, int(o[2] or 0))
            if qty > 0:
                cleaned.append(["BUY_ANIMAL", "COW", qty]); total_animals += qty
        else:
            cleaned.append(o)
    orders = cleaned

    # Q4 is a crop-capacity investment, not a reward for first reaching a giant
    # Q3 herd. At D12-D17 it has enough horizon for multiple short crop cycles.
    # Require a commissioned Q3, a live herd, and a post-land operating reserve.
    if lands == 3 and 12 <= day <= 17 and horizon >= 13:
        q3p = int(q3.get("productive", 0) or 0)
        q3a = int(q3.get("animals", 0) or 0)
        q3past = int(q3.get("pasture", 0) or 0)
        land_cost = 4000
        operating_reserve = 1600 + 60*animals
        expected = max(0, horizon-3) * 2600
        roi = (expected-land_cost)/land_cost
        if q3p >= 10 and q3past >= 7 and q3a >= 5 and money-land_cost >= operating_reserve and roi > 0:
            # Do not combine the land event with fresh cows; commission Q4 first.
            orders = [o for o in orders if not (isinstance(o,list) and o and o[0] in {"BUY_LAND","BUY_ANIMAL"})]
            sell_prefix = []
            rest = []
            for o in orders:
                if isinstance(o,list) and o and o[0] == "SELL": sell_prefix.append(o)
                else: rest.append(o)
            orders = sell_prefix + [["BUY_LAND"]] + rest
            meta["land"] = 1; meta["land_cost"] = land_cost
            meta.setdefault("ranked", []).append(["q4_crop_land", round(roi,2)])

    return orders[:10], meta


# Install only the capital policy; V33.25 already supplies demand-aware district
# routing, Q4 crop workers, telemetry, clean executor, and terminal liquidation.
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any=None):
    return _v25.agent(observation, configuration)


def reset_state(): return _v25.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _v25.get_telemetry(clear=clear)
