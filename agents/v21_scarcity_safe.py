"""V21 scarcity-safe challenger.

Single mutation on top of V19: preserve V19 farm/land/livestock/hiring/routing
exactly, and only throttle deeply depressed premium SELL orders when doing so
cannot starve working capital or overflow the shed.

Unlike the rejected alpha1 this file does NOT change expansion timing, cow
count, worker count, feed logic, or task routing.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from agents import v19_livestock_compound as _v19

BASE_PRICE = {
    "STRAWBERRY": 120,
    "MELON": 250,
    "MILK": 160,
    "WOOL": 200,
}
PREMIUM = set(BASE_PRICE)
LIQUIDITY_FLOOR = 7000
SHED_FORCE_SELL = 60
FINAL_RELAX_DAY = 27
FINAL_LIQUIDATE_DAY = 29
DEEP_GLUT_RATIO = 0.35
MID_GLUT_RATIO = 0.60


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        k: getattr(value, k)
        for k in ("player", "step", "day", "hour", "farms", "private", "market", "town")
        if hasattr(value, k)
    }


def reset_state() -> None:
    fn = getattr(_v19, "reset_state", None)
    if callable(fn):
        fn()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    fn = getattr(_v19, "get_telemetry", None)
    if callable(fn):
        try:
            return fn(clear=clear)
        except TypeError:
            return fn()
    return []


def _shed_load(obs: Mapping[str, Any]) -> int:
    shed = _m(_m(obs.get("private")).get("shed"))
    total = 0
    for value in shed.values():
        try:
            total += max(0, int(value or 0))
        except Exception:
            pass
    return total


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    result = dict(_v19.agent(observation, configuration))

    day = int(obs.get("day", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    farm = _m(farms[player]) if isinstance(farms, list) and player < len(farms) else {}
    money = float(farm.get("money", 0) or 0)

    # Never throttle if liquidity is constrained, shed occupancy is already high,
    # or the season is ending. These guards preserve V19's financing loop and
    # prevent DROP overflow from destroying held output.
    if day >= FINAL_LIQUIDATE_DAY or money < LIQUIDITY_FLOOR or _shed_load(obs) >= SHED_FORCE_SELL:
        return result

    market = _m(obs.get("market"))
    prices = _m(market.get("prices"))
    orders = []
    for raw in result.get("market", []) or []:
        if not isinstance(raw, list) or len(raw) < 3 or str(raw[0]).upper() != "SELL":
            orders.append(raw)
            continue

        resource = str(raw[1]).upper()
        if resource not in PREMIUM or day >= FINAL_RELAX_DAY:
            orders.append(raw)
            continue

        try:
            qty = max(0, int(raw[2] or 0))
            price = float(prices.get(resource, BASE_PRICE[resource]) or 0)
        except Exception:
            orders.append(raw)
            continue

        base = float(BASE_PRICE[resource])
        ratio = price / max(1.0, base)
        if ratio < DEEP_GLUT_RATIO:
            qty = min(qty, 2)
        elif ratio < MID_GLUT_RATIO:
            qty = min(qty, max(3, (qty + 1) // 2))

        if qty > 0:
            orders.append(["SELL", resource, qty])

    result["market"] = orders[:10]
    return result
