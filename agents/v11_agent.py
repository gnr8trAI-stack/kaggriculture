"""Submission-safe V11 entry point with bounded local decision telemetry.

Only ``farmer``, ``hands`` and ``market`` are returned to Kaggle. Rich telemetry
is retained in-process for local benchmarks and tests and can be drained between
episodes. The standalone submission builder omits the history buffer.
"""
from collections import Counter, deque
from time import perf_counter
from typing import Any, Deque, Dict, List, Mapping

from agents.v11_adaptive_planner import agent as _planner_agent

TELEMETRY_SCHEMA_VERSION = 1
TELEMETRY_MAX_RECORDS = 2048
LAST_DECISION: Dict[str, Any] = {}
TELEMETRY_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=TELEMETRY_MAX_RECORDS)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _observation(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: Dict[str, Any] = {}
    for key in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            result[key] = getattr(value, key)
        except Exception:
            pass
    return result


def _tile_summary(tiles: Any) -> Dict[str, Any]:
    kinds: Counter = Counter()
    crops: Counter = Counter()
    animals: Counter = Counter()
    at_risk = 0
    harvestable_units = 0
    fertilizer_ready = 0
    if not isinstance(tiles, list):
        tiles = []
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if tile is None:
                kinds["EMPTY"] += 1
                continue
            if tile == "LOCKED":
                kinds["LOCKED"] += 1
                continue
            data = _mapping(tile)
            kind = str(data.get("kind", data.get("type", "UNKNOWN"))).upper()
            kinds[kind] += 1
            harvestable_units += max(0, int(data.get("yield_units", 0) or 0))
            if kind == "PLANT":
                crop = str(data.get("crop", "UNKNOWN")).upper()
                crops[crop] += 1
                if not bool(data.get("watered_today", False)) and int(
                    data.get("consecutive_unwatered", 0) or 0
                ) >= 1:
                    at_risk += 1
            if kind in {"COOP", "PASTURE"}:
                animal = str(data.get("animal", "NONE") or "NONE").upper()
                animals[animal] += 1
                if animal != "NONE" and not bool(data.get("fed_today", False)) and int(
                    data.get("consecutive_unfed", 0) or 0
                ) >= 1:
                    at_risk += 1
                fertilizer_ready += int(bool(data.get("fertilizer_available", False)))
    return {
        "tile_kinds": dict(kinds),
        "crops": dict(crops),
        "animals": dict(animals),
        "at_risk_assets": at_risk,
        "harvestable_units": harvestable_units,
        "fertilizer_ready": fertilizer_ready,
    }


def _inventory(value: Any) -> Dict[str, int]:
    return {
        str(key).upper(): max(0, int(quantity or 0))
        for key, quantity in _mapping(value).items()
        if int(quantity or 0) != 0
    }


def _action_counts(action: Mapping[str, Any]) -> Dict[str, int]:
    counts: Counter = Counter()
    unit_actions: List[Any] = [action.get("farmer", ["PASS"])]
    hands = action.get("hands", [])
    if isinstance(hands, list):
        unit_actions.extend(hands)
    for item in unit_actions:
        if isinstance(item, list) and item:
            counts[str(item[0]).upper()] += 1
        else:
            counts["MALFORMED_UNIT_ACTION"] += 1
    market = action.get("market", [])
    if isinstance(market, list):
        for order in market:
            if isinstance(order, list) and order:
                counts[f"MARKET_{str(order[0]).upper()}"] += 1
            else:
                counts["MALFORMED_MARKET_ORDER"] += 1
    return dict(counts)


def _enrich_telemetry(
    observation: Any,
    action: Mapping[str, Any],
    planner: Mapping[str, Any],
    duration_ms: float,
) -> Dict[str, Any]:
    obs = _observation(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    own = _mapping(farms[player]) if isinstance(farms, list) and player < len(farms) else {}
    opponent_index = 1 - player
    opponent = (
        _mapping(farms[opponent_index])
        if isinstance(farms, list) and opponent_index < len(farms)
        else {}
    )
    private = _mapping(obs.get("private"))
    inventories = private.get("inventories", [])
    if not isinstance(inventories, list):
        inventories = []
    market = _mapping(obs.get("market"))
    town = _mapping(obs.get("town"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    record = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "step": day * 24 + hour,
        "day": day,
        "hour": hour,
        "player": player,
        "decision_duration_ms": round(duration_ms, 4),
        "money": float(own.get("money", 0) or 0),
        "opponent_money": float(opponent.get("money", 0) or 0),
        "money_delta": float(own.get("money", 0) or 0)
        - float(opponent.get("money", 0) or 0),
        "hands": len(own.get("hands", []) if isinstance(own.get("hands", []), list) else []),
        "hires_today": int(own.get("hires_today", 0) or 0),
        "unlocked_quadrants": list(own.get("unlocked_quadrants", []) or []),
        "own_farm": _tile_summary(own.get("tiles", [])),
        "opponent_farm": _tile_summary(opponent.get("tiles", [])),
        "shed": _inventory(private.get("shed")),
        "seeds": _inventory(private.get("seeds")),
        "unit_inventories": [_inventory(item) for item in inventories],
        "market_prices": _inventory(market.get("prices")),
        "market_inventory": _inventory(market.get("inventory")),
        "unlocked_shops": list(town.get("unlocked_shops", []) or []),
        "planner": dict(planner),
        "action": {
            "farmer": action.get("farmer", ["PASS"]),
            "hands": action.get("hands", []),
            "market": action.get("market", []),
            "counts": _action_counts(action),
        },
    }
    return record


def reset_telemetry() -> None:
    """Clear episode telemetry and the last decision snapshot."""
    global LAST_DECISION
    LAST_DECISION = {}
    TELEMETRY_BUFFER.clear()


def get_telemetry(clear: bool = False) -> List[Dict[str, Any]]:
    """Return a copy of buffered telemetry, optionally draining the buffer."""
    records = list(TELEMETRY_BUFFER)
    if clear:
        TELEMETRY_BUFFER.clear()
    return records


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    """Return only fields accepted by the Kaggriculture action schema."""
    global LAST_DECISION
    started = perf_counter()
    raw = dict(_planner_agent(observation, configuration))
    planner = raw.pop("_telemetry", None)
    action = {
        "farmer": raw.get("farmer", ["PASS"]),
        "hands": raw.get("hands", []),
        "market": raw.get("market", []),
    }
    elapsed_ms = (perf_counter() - started) * 1000.0
    record = _enrich_telemetry(
        observation,
        action,
        planner if isinstance(planner, Mapping) else {},
        elapsed_ms,
    )
    LAST_DECISION = record
    TELEMETRY_BUFFER.append(record)
    return action
