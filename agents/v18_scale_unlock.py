"""V18 scale-unlock challenger built directly on the frozen V15 champion.

Purpose
-------
V15 has a proven opening/execution engine but two structural ceilings:
1. its first-land gate requires a transient combination of cash + instantaneous
   NW occupancy that rarely occurs after the first harvest;
2. if the melon regime never becomes stressed, V10 stops planting after day 18
   and the farm effectively retires while competitors keep compounding.

V18 changes only those two things:
- remember *historical productive saturation* of the original NW quadrant;
- unlock exactly one additional quadrant when saturation, farm health and cash
  reserve support it;
- switch permanently to V15's own adaptive V12 crop/workload engine on
  expansion, or at day 18 at the latest.

No multi-animal scaling is added in this candidate. V15's one-goose logic is
left untouched so land/crop scaling is tested independently.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, Mapping

from agents import v15_champion as _v15

# First land costs $1,000 under the official environment. Keep substantially
# more than that after purchase for seeds/hands rather than V15's old $12k gate.
LAND_COST_FIRST = 1000
POST_LAND_CASH_RESERVE = 2500
MIN_CASH_TO_EXPAND = LAND_COST_FIRST + POST_LAND_CASH_RESERVE
MIN_PEAK_NW_PRODUCTIVE = 20
EXPAND_MIN_DAY = 10
EXPAND_MAX_DAY = 20
FORCE_ADAPTIVE_DAY = 18
MAX_WEEDS_TO_EXPAND = 4
MAX_DANGER_TO_EXPAND = 2

_LAST_STEP = -1
_PEAK_NW_PRODUCTIVE = 0
_FORCED_ADAPTIVE = False
_RECORDS = deque(maxlen=2048)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        k: getattr(value, k)
        for k in ("player", "step", "day", "hour", "farms", "private", "market", "town")
        if hasattr(value, k)
    }


def _kind(tile: Any) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, Mapping):
        return str(tile.get("kind", tile.get("type", "UNKNOWN"))).upper()
    return "UNKNOWN"


def _farm_health(farm: Mapping[str, Any]) -> Dict[str, int | float]:
    tiles = farm.get("tiles") or []
    unlocked = weeds = danger = productive = 0
    nw_productive = 0
    if not isinstance(tiles, list) or not tiles:
        return {
            "unlocked": 0, "weeds": 0, "danger": 0,
            "productive": 0, "nw_productive": 0, "weed_ratio": 0.0,
        }
    half = len(tiles) // 2
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            kind = _kind(tile)
            if kind == "LOCKED":
                continue
            unlocked += 1
            if kind == "WEED":
                weeds += 1
            if kind in {"PLANT", "COOP", "PASTURE"}:
                productive += 1
                if x < half and y < half:
                    nw_productive += 1
            if kind == "PLANT" and isinstance(tile, Mapping):
                if (not bool(tile.get("watered_today", False)) and
                        int(tile.get("consecutive_unwatered", 0) or 0) >= 1):
                    danger += 1
    return {
        "unlocked": unlocked,
        "weeds": weeds,
        "danger": danger,
        "productive": productive,
        "nw_productive": nw_productive,
        "weed_ratio": weeds / max(1, unlocked),
    }


def reset_state() -> None:
    global _LAST_STEP, _PEAK_NW_PRODUCTIVE, _FORCED_ADAPTIVE
    _LAST_STEP = -1
    _PEAK_NW_PRODUCTIVE = 0
    _FORCED_ADAPTIVE = False
    _RECORDS.clear()
    reset = getattr(_v15, "reset_state", None)
    if callable(reset):
        reset()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    rows = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return rows


def _switch_v15_to_adaptive() -> None:
    # V15's outer controller exposes its current mode in the embedded module.
    # We reuse V15's own V12 crop economics and workload planner rather than
    # adding a second planner here.
    if hasattr(_v15, "_MODE"):
        _v15._MODE = "v12"


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _LAST_STEP, _PEAK_NW_PRODUCTIVE, _FORCED_ADAPTIVE

    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = _m(farms[player])
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = int(obs.get("step", day * 24 + hour) or 0)

    # The tournament harness imports a module once and runs many episodes.
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        reset_state()
    _LAST_STEP = step

    health = _farm_health(farm)
    _PEAK_NW_PRODUCTIVE = max(_PEAK_NW_PRODUCTIVE, int(health["nw_productive"]))
    unlocked = list(farm.get("unlocked_quadrants") or ["NW"])
    money = float(farm.get("money", 0) or 0)

    expansion_eligible = (
        len(unlocked) == 1
        and EXPAND_MIN_DAY <= day <= EXPAND_MAX_DAY
        and _PEAK_NW_PRODUCTIVE >= MIN_PEAK_NW_PRODUCTIVE
        and money >= MIN_CASH_TO_EXPAND
        and int(health["weeds"]) <= MAX_WEEDS_TO_EXPAND
        and int(health["danger"]) <= MAX_DANGER_TO_EXPAND
    )

    # Once scaling starts, V10's fixed one-field melon policy is no longer the
    # right controller. V12 already understands dynamic crops, remaining season
    # and workload-based hiring, so reuse it permanently.
    if expansion_eligible or day >= FORCE_ADAPTIVE_DAY:
        _FORCED_ADAPTIVE = True
    if _FORCED_ADAPTIVE:
        _switch_v15_to_adaptive()

    result = dict(_v15.agent(observation, configuration))
    orders = [list(o) for o in result.get("market", []) if isinstance(o, list)]

    land_injected = False
    if expansion_eligible and not any(o[:1] == ["BUY_LAND"] for o in orders):
        # Land is cheap but future operating cash is valuable. Put the unlock
        # first so it cannot be truncated by the ten-order limit; V15's sells
        # remain immediately behind it.
        orders.insert(0, ["BUY_LAND"])
        land_injected = True

    result["market"] = orders[:10]
    _RECORDS.append({
        "step": step,
        "day": day,
        "hour": hour,
        "money": money,
        "unlocked": list(unlocked),
        "peak_nw_productive": _PEAK_NW_PRODUCTIVE,
        "health": dict(health),
        "expansion_eligible": expansion_eligible,
        "land_injected": land_injected,
        "forced_adaptive": _FORCED_ADAPTIVE,
        "v15_mode": getattr(_v15, "_MODE", None),
    })
    return result
