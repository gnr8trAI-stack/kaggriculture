"""Frozen strong melon monocrop baseline used only for local evaluation."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

from agents.v8_melon_optimizer import (
    CROP,
    SEED_COST,
    SELLABLE,
    Position,
    _assign,
    _empties,
    _mapping,
    _obs,
    _position,
    _targets,
)

STOP_DAY = 15
TARGET_HANDS = 5


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, list) or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = _mapping(farms[player])
    tiles = farm.get("tiles", [])
    hands = list(farm.get("hands", []))
    result: Dict[str, Any] = {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in hands],
        "market": [],
    }
    if not isinstance(tiles, list) or not tiles:
        return result

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    seed_map = _mapping(private.get("seeds"))
    seeds = int(seed_map.get(CROP, 0) or 0)

    targets = _targets(tiles, day)
    empties = _empties(tiles)
    positions = [_position(farm.get("farmer", [0, 0]))] + [
        _position(hand) for hand in hands
    ]
    reserved: Set[Position] = set()
    remaining = seeds
    assigned: List[List[Any]] = []

    for position in positions:
        action = _assign(
            tiles,
            position,
            targets,
            empties,
            reserved,
            day <= STOP_DAY and remaining > 0,
        )
        if action[:1] == ["PLANT"]:
            remaining -= 1
        assigned.append(action)

    orders: List[List[Any]] = []
    for item in SELLABLE:
        quantity = int(shed.get(item, 0) or 0)
        if quantity > 0:
            orders.append(["SELL", item, quantity])

    liquidate = day >= 29 or (day == 28 and hour >= 18)
    if not liquidate:
        for _ in range(max(0, TARGET_HANDS - len(hands))):
            if len(orders) >= 9:
                break
            orders.append(["HIRE"])

    if not liquidate and day <= STOP_DAY and empties and len(orders) < 10:
        desired = min(len(empties), max(12, len(positions) * 2))
        buy = max(0, desired - seeds)
        affordable = max(0, int(float(farm.get("money", 0) or 0) // SEED_COST))
        buy = min(buy, affordable)
        if buy > 0:
            orders.append(["BUY_SEED", CROP, buy])

    result["farmer"] = assigned[0]
    result["hands"] = assigned[1:]
    result["market"] = orders[:10]
    return result
