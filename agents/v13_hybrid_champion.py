"""V13 conservative hybrid Kaggriculture candidate.

V10 remains the default policy because it is the strongest validated repository
agent. V13 switches permanently to V12 only when public state shows a material
melon-glut regime. The switch is deliberately one-way to avoid policy thrashing.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any, Dict, Mapping
import time

from agents.v10_market_front_runner import agent as v10_agent
from agents.v12_agent import agent as v12_agent

TELEMETRY_SCHEMA_VERSION = "v13.1"
_MAX_RECORDS = 2048
_RECORDS = deque(maxlen=_MAX_RECORDS)
_MODE = "v10"
_LAST_STEP = -1


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _obs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: Dict[str, Any] = {}
    for key in ("player", "day", "hour", "farms", "market", "town", "private"):
        try:
            result[key] = getattr(value, key)
        except Exception:
            pass
    return result


def _crop_counts(tiles: Any) -> Counter:
    counts: Counter = Counter()
    if not isinstance(tiles, list):
        return counts
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if isinstance(tile, Mapping):
                kind = str(tile.get("kind", tile.get("type", ""))).upper()
                if kind == "PLANT":
                    counts[str(tile.get("crop", "")).upper()] += 1
    return counts


def _public_regime(obs: Mapping[str, Any]) -> Dict[str, Any]:
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    opponent = _mapping(farms[1 - player]) if isinstance(farms, list) and len(farms) > 1 else {}
    opponent_counts = _crop_counts(opponent.get("tiles", []))
    market = _mapping(obs.get("market"))
    prices = _mapping(market.get("prices"))
    inventory = _mapping(market.get("inventory"))
    melon_price = float(prices.get("MELON", 250) or 250)
    melon_inventory = float(inventory.get("MELON", 10000) or 10000)
    opponent_melons = int(opponent_counts.get("MELON", 0))
    severe_glut = (
        opponent_melons >= 12
        or melon_price <= 120
        or melon_inventory >= 10180
    )
    return {
        "opponent_melons": opponent_melons,
        "melon_price": melon_price,
        "melon_inventory": melon_inventory,
        "severe_glut": severe_glut,
    }


def reset_state() -> None:
    global _MODE, _LAST_STEP
    _MODE = "v10"
    _LAST_STEP = -1
    _RECORDS.clear()
    try:
        from agents import v12_agent
        v12_agent.reset_telemetry()
    except Exception:
        pass


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    records = list(_RECORDS)
    if clear:
        _RECORDS.clear()
    return records


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _MODE, _LAST_STEP
    started = time.perf_counter()
    obs = _obs(observation)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = day * 24 + hour

    # A lower/equal step indicates a new local episode in the same interpreter.
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        _MODE = "v10"
    _LAST_STEP = step

    regime = _public_regime(obs)
    previous_mode = _MODE
    if _MODE == "v10" and regime["severe_glut"]:
        _MODE = "v12"

    chosen = v10_agent if _MODE == "v10" else v12_agent
    action = dict(chosen(obs, configuration))
    legal = {
        "farmer": action.get("farmer", ["PASS"]),
        "hands": action.get("hands", []),
        "market": action.get("market", []),
    }
    _RECORDS.append({
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "step": step,
        "day": day,
        "hour": hour,
        "mode": _MODE,
        "switched_this_turn": previous_mode != _MODE,
        "regime": regime,
        "decision_duration_ms": (time.perf_counter() - started) * 1000.0,
        "action": legal,
    })
    return legal
