"""V34.26 isolated terminal-liquidation experiment.

Single economic mutation on verified V34.23. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand dairy service, late staffing, reserve-pasture
and cow-activation rescue, early strawberry specialization, feed, routing,
harvest and all pre-terminal market behavior.

Only in the terminal window, convert sellable shed inventory to bank cash:
- day 28+: sell all crop/animal outputs already in the shed;
- day 29+: also liquidate remaining WHEAT feed inventory.
Existing SELL orders are consolidated to the full observed shed quantity so the
wrapper never emits duplicate oversell orders for the same resource.

Rationale: Kaggriculture ranks terminal money in the bank, while unsold shed
inventory has no terminal cash value. V34.x already spends labour returning milk
and fertilizer to the shed. This isolates whether stranded endgame inventory is
an unrealized-profit leak without changing production or capacity decisions.
"""
from __future__ import annotations
from typing import Any, Dict, List

from agents import v34_23_earlier_strawberry as _base

SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "MILK", "WOOL", "EGG", "FERTILIZER",
)
OUTPUTS = set(SELLABLE) - {"WHEAT"}
_TRIGGERED = False


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def terminal_liquidation_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _TRIGGERED
    result = dict(_base.agent(observation, configuration))

    v19 = _base._base._v19
    obs = v19._obs(observation)
    day = int(obs.get("day", 0) or 0)
    if day < 28:
        return result

    private = v19._m(obs.get("private"))
    shed = v19._m(private.get("shed"))
    liquidation_set = set(SELLABLE if day >= 29 else OUTPUTS)

    wanted = {
        resource: max(0, int(shed.get(resource, 0) or 0))
        for resource in liquidation_set
    }
    wanted = {k: v for k, v in wanted.items() if v > 0}
    if not wanted:
        return result

    market: List[List[Any]] = []
    inserted = set()
    for raw in result.get("market", []):
        if not isinstance(raw, list) or not raw:
            continue
        order = list(raw)
        if str(order[0]).upper() == "SELL" and len(order) >= 3:
            resource = str(order[1]).upper()
            if resource in wanted:
                if resource not in inserted:
                    market.append(["SELL", resource, wanted[resource]])
                    inserted.add(resource)
                continue
        market.append(order)

    # SELL conversion gets terminal priority, but keep the environment's hard
    # ten-order contract. Existing critical orders retain their relative order;
    # missing liquidation orders fill remaining slots from high-value outputs.
    priority = ("MILK", "WOOL", "STRAWBERRY", "MELON", "EGG",
                "TOMATO", "CARROT", "FERTILIZER", "WHEAT")
    for resource in priority:
        if resource in wanted and resource not in inserted:
            market.insert(0, ["SELL", resource, wanted[resource]])
            inserted.add(resource)

    result["market"] = market[:10]
    _TRIGGERED = True
    return result
