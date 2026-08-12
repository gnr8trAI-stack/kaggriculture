"""V34.29 isolated late-hire market-order priority experiment.

Single economic mutation on verified V34.26. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand livestock service, late 9/10 staffing target,
reserve-pasture/activation rescue, early strawberry specialization, feed/routing,
market logic and terminal liquidation. When the existing V34.13 late-staffing
eligibility is true (day>=16, >=10 active cows, >=18k cash, healthy farm) and the
farm still has fewer than 9 hands, guarantee exactly one HIRE order in the market
packet after any wheat survival order.

Rationale: V34.28 proved moving the eligibility day earlier is a 24/24 behavioral
no-op even though its readiness flag fires. This isolates the downstream market
order-capacity hypothesis: the proven late staffing target may be eligible before
its HIRE survives the ten-order packet. No additional headcount target is added;
this only ensures the already-proven first late crop/utility hire can execute.
"""
from __future__ import annotations
from typing import Any, Dict, List

from agents import v34_26_terminal_liquidation as _base

# V34.26 -> V34.23 -> V34.21 -> V34.17 -> V34.16 -> V34.13
_late = _base._base._base._base._base._base
_TRIGGERED = False


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def hire_priority_triggered() -> bool:
    return bool(_TRIGGERED)


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _TRIGGERED
    result = dict(_base.agent(observation, configuration))

    # Use exactly the verified V34.13 late-staffing readiness predicate.
    if not _late._late_crop_hires_ready(observation):
        return result

    v19 = _late._v19()
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = v19._m(farms[player])
    hands = list(farm.get("hands") or [])

    # Only realize the already-proven first late step. Do not raise the target.
    if len(hands) >= _late.LATE_MIN_HANDS:
        return result

    market: List[List[Any]] = [
        list(o) for o in result.get("market", [])
        if isinstance(o, list) and o
    ]
    if any(str(o[0]).upper() == "HIRE" for o in market):
        return result

    # Feed survival keeps absolute priority. Place HIRE immediately after any
    # leading wheat BUY_PRODUCT orders and ahead of optional sales/seed orders.
    insert_at = 0
    while insert_at < len(market):
        o = market[insert_at]
        if (str(o[0]).upper() == "BUY_PRODUCT" and len(o) >= 2
                and str(o[1]).upper() == "WHEAT"):
            insert_at += 1
        else:
            break
    market.insert(insert_at, ["HIRE"])
    result["market"] = market[:10]
    _TRIGGERED = True
    return result
