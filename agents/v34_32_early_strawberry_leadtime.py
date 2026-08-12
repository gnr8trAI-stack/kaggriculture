"""V34.32 isolated early-strawberry lead-time experiment.

Single economic mechanism on verified V34.26. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand dairy service, late staffing, reserve-pasture and
cow-activation rescue, feed, routing, market behavior and terminal liquidation.

Change only the strawberry specialization gate for newly planted eligible crop
slots. V34.26 inherits V34.23's day>=10 / >=8 active cows / >=8000 cash gate.
This candidate moves the gate to day>=4 / no cow prerequisite / >=2500 cash,
with the same farm-health guard.

Economic rationale: STRAWBERRY needs roughly ten in-game days to first yield.
Waiting until day 10 means specialized plantings only begin paying around day 20,
while replay-derived 175k-192k frontier trajectories already sustain large
strawberry books during days 14-20. This test isolates lead time only: no extra
land, labour, livestock, routing, service priority, sell policy or action type.
"""
from __future__ import annotations
from typing import Any, Dict, List

from agents import v34_21_late_strawberry_specialization as _crop_base

MIN_DAY = 4
MIN_ACTIVE_COWS = 0
MIN_CASH = 2500

SELLABLE = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "MILK", "WOOL", "EGG", "FERTILIZER",
)
OUTPUTS = set(SELLABLE) - {"WHEAT"}
_LIQUIDATION_TRIGGERED = False


def _activate_crop_gate() -> None:
    _crop_base.MIN_DAY = MIN_DAY
    _crop_base.MIN_ACTIVE_COWS = MIN_ACTIVE_COWS
    _crop_base.MIN_CASH = MIN_CASH


def reset_state() -> None:
    global _LIQUIDATION_TRIGGERED
    _LIQUIDATION_TRIGGERED = False
    _crop_base.reset_state()
    _activate_crop_gate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _crop_base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_crop_base.strawberry_triggered())


def terminal_liquidation_triggered() -> bool:
    return bool(_LIQUIDATION_TRIGGERED)


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _LIQUIDATION_TRIGGERED
    _activate_crop_gate()
    result = dict(_crop_base.agent(observation, configuration))

    v19 = _crop_base._base._v19()
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

    priority = ("MILK", "WOOL", "STRAWBERRY", "MELON", "EGG",
                "TOMATO", "CARROT", "FERTILIZER", "WHEAT")
    for resource in priority:
        if resource in wanted and resource not in inserted:
            market.insert(0, ["SELL", resource, wanted[resource]])
            inserted.add(resource)

    result["market"] = market[:10]
    _LIQUIDATION_TRIGGERED = True
    return result


_activate_crop_gate()
