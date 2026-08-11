"""V33.30 cash-throughput dairy industrialization.

Independent V33 lineage. V33.28 remains the strongest 24-game industrial base:
4-land operation, ~76 productive tiles, zero invalids and ~64K median reward.
V33.29 proved that fragmenting Q3 into mixed livestock reduces both productive
capital and reward. This candidate therefore returns Q3 to a dense dairy engine,
but removes V33.28's demand-derived herd ceiling and converts milk inventory to
cash more aggressively. The economic hypothesis is that the 8-cow median in
V33.28 underutilizes commissioned Q3 pasture and leaves too much high-ROI animal
capacity idle relative to the known 12+ cow replay regime.

This is not a V19/V32 mutation: execution, districts, allocator and telemetry
remain on the independent V33 architecture.
"""
from __future__ import annotations
from typing import Any, List, Mapping
from agents import v33_industrial_v28 as _v28

_b = _v28._b


def _cow_target(obs: Mapping[str, Any], day: int, active: int) -> int:
    """Front-load a repayable dairy line while respecting terminal horizon.

    Cow first yield is delayed, so new biological capex stops early. We keep a
    12-cow floor in weak milk markets and allow 16 only when recurring absorption
    or live price supports it. Existing animals are never targeted away.
    """
    horizon = max(0, 30 - day)
    if horizon < 9:
        return active
    demand = _v28._daily_demand(obs, "MILK")
    price = float(_b._prices(obs).get("MILK", 160) or 160)
    target = 12
    if demand >= 7 or price >= 115:
        target = 14
    if demand >= 13 and price >= 90:
        target = 16
    if price < 55 and demand <= 1:
        target = 10
    if day >= 19:
        target = min(target, max(active, 14))
    if day >= 21:
        target = active
    return max(active, target)


def _roles(lands: int, hand_count: int) -> List[str]:
    """Operate Q3 as a real production district without starving Q1/Q2/Q4."""
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # 8 operators at industrial staffing; one feed runner; remainder crops.
        crew = min(8, max(5, total // 2))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        fi = total - crew - 1
        if fi >= 1:
            roles[fi] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"
                moved += 1
    return roles


def _sale_qty(obs: Mapping[str, Any], item: str, qty: int, day: int, shed_total: int) -> int:
    """Prioritize cash conversion while retaining limited premium pacing."""
    if qty <= 0:
        return 0
    if day >= 27:
        return qty
    if item == "MILK":
        price = float(_b._prices(obs).get("MILK", 160) or 160)
        demand = _v28._daily_demand(obs, "MILK")
        # Never let dairy working capital pile up behind an over-conservative
        # price gate. Sell at least recurring absorption every market step, and
        # clear faster when price is healthy or inventory pressure is high.
        if price >= 90 or shed_total >= 60:
            return min(qty, max(8, demand * 3))
        return min(qty, max(3, demand))
    return _v28._sale_qty(obs, item, qty, day, shed_total)


# Patch only independent-V33 strategy hooks. V28's allocator and executor use
# their module globals at runtime, so these replacements affect herd sizing,
# district labour and sale pacing without importing any V19/V32 architecture.
_v28._cow_target = _cow_target
_v28._roles = _roles
_v28._sale_qty = _sale_qty
_b._roles = _roles


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
